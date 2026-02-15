"""Orchestration manager (agent_framework version) handling multi-agent Magentic workflow creation and execution."""

import asyncio
import logging
import os
import uuid
from typing import List, Optional

# agent_framework imports
from agent_framework_azure_ai import AzureAIAgentClient
from agent_framework import (
    ChatMessage,
    WorkflowOutputEvent,
    MagenticBuilder,
    InMemoryCheckpointStorage,
    MagenticOrchestratorMessageEvent,
    MagenticAgentDeltaEvent,
    MagenticAgentMessageEvent,
    MagenticFinalResultEvent,
)

from common.config.app_config import config
from common.models.messages_af import (
    TeamConfiguration,
    AgentMessageData,
    AgentMessageType,
    PlanStatus,
)

from common.database.database_base import DatabaseBase
from common.database.database_factory import DatabaseFactory

from v4.common.services.team_service import TeamService
from v4.callbacks.response_handlers import (
    agent_response_callback,
    streaming_agent_response_callback,
)
from v4.config.settings import connection_config, orchestration_config
from v4.models.messages import WebsocketMessageType
from v4.orchestration.human_approval_manager import HumanApprovalMagenticManager
from v4.magentic_agents.magentic_agent_factory import MagenticAgentFactory


class OrchestrationManager:
    """Manager for handling orchestration logic using agent_framework Magentic workflow."""

    logger = logging.getLogger(f"{__name__}.OrchestrationManager")

    def __init__(self):
        self.user_id: Optional[str] = None
        self.logger = self.__class__.logger

    # ---------------------------
    # Orchestration construction
    # ---------------------------
    @classmethod
    async def init_orchestration(
        cls,
        agents: List,
        team_config: TeamConfiguration,
        memory_store: DatabaseBase,
        user_id: str | None = None,
    ):
        """
        Initialize a Magentic workflow with:
          - Provided agents (participants)
          - HumanApprovalMagenticManager as orchestrator manager
          - AzureAIAgentClient as the underlying chat client
          - Event-based callbacks for streaming and final responses
        - Uses same deployment, endpoint, and credentials
        - Applies same execution settings (temperature, max_tokens)
        - Maintains same human approval workflow
        """
        if not user_id:
            raise ValueError("user_id is required to initialize orchestration")

        # Get credential from config (same as old version)
        credential = config.get_azure_credential(client_id=config.AZURE_CLIENT_ID)

        # Create Azure AI Agent client for orchestration using config
        # This replaces AzureChatCompletion from SK
        agent_name = team_config.name if team_config.name else "OrchestratorAgent"

        try:
            chat_client = AzureAIAgentClient(
                project_endpoint=config.AZURE_AI_PROJECT_ENDPOINT,
                model_deployment_name=team_config.deployment_name,
                agent_name=agent_name,
                async_credential=credential,
            )

            cls.logger.info(
                "Created AzureAIAgentClient for orchestration with model '%s' at endpoint '%s'",
                team_config.deployment_name,
                config.AZURE_AI_PROJECT_ENDPOINT,
            )
        except Exception as e:
            cls.logger.error("Failed to create AzureAIAgentClient: %s", e)
            raise

        # Create HumanApprovalMagenticManager with the chat client
        # Execution settings (temperature=0.1, max_tokens=4000) are configured via
        # orchestration_config.create_execution_settings() which matches old SK version
        try:
            manager = HumanApprovalMagenticManager(
                user_id=user_id,
                chat_client=chat_client,
                instructions=None,  # Orchestrator system instructions (optional)
                max_round_count=orchestration_config.max_rounds,
            )
            cls.logger.info(
                "Created HumanApprovalMagenticManager for user '%s' with max_rounds=%d",
                user_id,
                orchestration_config.max_rounds,
            )
        except Exception as e:
            cls.logger.error("Failed to create manager: %s", e)
            raise

        # Build participant map: use each agent's name as key
        participants = {}
        for ag in agents:
            name = getattr(ag, "agent_name", None) or getattr(ag, "name", None)
            if not name:
                name = f"agent_{len(participants) + 1}"

            # Extract the inner ChatAgent for wrapper templates
            # FoundryAgentTemplate wrap a ChatAgent in self._agent
            # ProxyAgent directly extends BaseAgent and can be used as-is
            if hasattr(ag, "_agent") and ag._agent is not None:
                # This is a wrapper (FoundryAgentTemplate)
                # Use the inner ChatAgent which implements AgentProtocol
                participants[name] = ag._agent
                cls.logger.debug("Added participant '%s' (extracted inner agent)", name)
            else:
                # This is already an agent (like ProxyAgent extending BaseAgent)
                participants[name] = ag
                cls.logger.debug("Added participant '%s'", name)

        # Assemble workflow with callback
        storage = InMemoryCheckpointStorage()
        builder = (
            MagenticBuilder()
            .participants(**participants)
            .with_standard_manager(
                manager=manager,
                max_round_count=orchestration_config.max_rounds,
                max_stall_count=0,
            )
            .with_checkpointing(storage)
        )

        # Build workflow
        workflow = builder.build()
        cls.logger.info(
            "Built Magentic workflow with %d participants and event callbacks",
            len(participants),
        )

        return workflow

    # ---------------------------
    # Orchestration retrieval
    # ---------------------------
    @classmethod
    async def get_current_or_new_orchestration(
        cls,
        user_id: str,
        team_config: TeamConfiguration,
        team_switched: bool,
        team_service: TeamService = None,
    ):
        """
        Return an existing workflow for the user or create a new one if:
          - None exists
          - Team switched flag is True
        """
        current = orchestration_config.get_current_orchestration(user_id)
        if current is None or team_switched:
            if current is not None and team_switched:
                cls.logger.info(
                    "Team switched, closing previous agents for user '%s'", user_id
                )
                # Close prior agents (same logic as old version)
                for agent in getattr(current, "_participants", {}).values():
                    agent_name = getattr(
                        agent, "agent_name", getattr(agent, "name", "")
                    )
                    if agent_name != "ProxyAgent":
                        close_coro = getattr(agent, "close", None)
                        if callable(close_coro):
                            try:
                                await close_coro()
                                cls.logger.debug("Closed agent '%s'", agent_name)
                            except Exception as e:
                                cls.logger.error("Error closing agent: %s", e)

            factory = MagenticAgentFactory(team_service=team_service)
            try:
                agents = await factory.get_agents(
                    user_id=user_id,
                    team_config_input=team_config,
                    memory_store=team_service.memory_context,
                )
                cls.logger.info("Created %d agents for user '%s'", len(agents), user_id)
            except Exception as e:
                cls.logger.error(
                    "Failed to create agents for user '%s': %s", user_id, e
                )
                print(f"Failed to create agents for user '{user_id}': {e}")
                raise
            try:
                cls.logger.info("Initializing new orchestration for user '%s'", user_id)
                orchestration_config.orchestrations[user_id] = (
                    await cls.init_orchestration(
                        agents, team_config, team_service.memory_context, user_id
                    )
                )
            except Exception as e:
                cls.logger.error(
                    "Failed to initialize orchestration for user '%s': %s", user_id, e
                )
                print(f"Failed to initialize orchestration for user '{user_id}': {e}")
                raise
        return orchestration_config.get_current_orchestration(user_id)

    # ---------------------------
    # Execution
    # ---------------------------
    async def run_orchestration(
        self,
        user_id: str,
        input_task,
        plan_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """
        Execute the Magentic workflow for the provided user and task description.
        """
        job_id = str(uuid.uuid4())
        orchestration_config.set_approval_pending(job_id)
        self.logger.warning(
            "=== ORCHESTRATION START === job=%s user=%s plan_id=%s", job_id, user_id, plan_id
        )

        workflow = orchestration_config.get_current_orchestration(user_id)
        if workflow is None:
            raise ValueError("Orchestration not initialized for user.")
        # Fresh thread per participant to avoid cross-run state bleed
        executors = getattr(workflow, "executors", {})
        self.logger.debug("Executor keys at run start: %s", list(executors.keys()))

        for exec_key, executor in executors.items():
            try:
                if exec_key == "magentic_orchestrator":
                    # Orchestrator path
                    if hasattr(executor, "_conversation"):
                        conv = getattr(executor, "_conversation")
                        # Support list-like or custom container with clear()
                        if hasattr(conv, "clear") and callable(conv.clear):
                            conv.clear()
                            self.logger.debug(
                                "Cleared orchestrator conversation (%s)", exec_key
                            )
                        elif isinstance(conv, list):
                            conv[:] = []
                            self.logger.debug(
                                "Emptied orchestrator conversation list (%s)", exec_key
                            )
                        else:
                            self.logger.debug(
                                "Orchestrator conversation not clearable type (%s): %s",
                                exec_key,
                                type(conv),
                            )
                    else:
                        self.logger.debug(
                            "Orchestrator has no _conversation attribute (%s)", exec_key
                        )
                else:
                    # Agent path
                    if hasattr(executor, "_chat_history"):
                        hist = getattr(executor, "_chat_history")
                        if hasattr(hist, "clear") and callable(hist.clear):
                            hist.clear()
                            self.logger.debug(
                                "Cleared agent chat history (%s)", exec_key
                            )
                        elif isinstance(hist, list):
                            hist[:] = []
                            self.logger.debug(
                                "Emptied agent chat history list (%s)", exec_key
                            )
                        else:
                            self.logger.debug(
                                "Agent chat history not clearable type (%s): %s",
                                exec_key,
                                type(hist),
                            )
                    else:
                        self.logger.debug(
                            "Agent executor has no _chat_history attribute (%s)",
                            exec_key,
                        )
            except Exception as e:
                self.logger.warning(
                    "Failed clearing state for executor %s: %s", exec_key, e
                )
        # --- END NEW BLOCK ---

        # Build task from input (same as old version)
        task_text = getattr(input_task, "description", str(input_task))
        self.logger.debug("Task: %s", task_text)

        # Resolve plan_id if not provided — find latest in_progress plan for user
        if not plan_id:
            try:
                db = await DatabaseFactory.get_database(user_id=user_id)
                query = (
                    "SELECT TOP 1 * FROM c "
                    "WHERE c.data_type='plan' AND c.user_id=@uid "
                    "AND c.overall_status='in_progress' "
                    "ORDER BY c.timestamp DESC"
                )
                results = list(
                    db.container.query_items(
                        query=query,
                        parameters=[{"name": "@uid", "value": user_id}],
                        enable_cross_partition_query=True,
                    )
                )
                if results:
                    plan_id = results[0].get("plan_id")
                    session_id = session_id or results[0].get("session_id")
                    self.logger.info("Resolved plan_id=%s for user %s", plan_id, user_id)
            except Exception as e:
                self.logger.warning("Could not resolve plan_id: %s", e)

        try:
            final_output: str | None = None
            event_count = 0
            agent_messages_count = 0
            MAX_WORKFLOW_TIMEOUT = int(os.environ.get("WORKFLOW_TIMEOUT_SECONDS", "600"))

            self.logger.warning("=== WORKFLOW EXECUTION STARTING === timeout=%ds", MAX_WORKFLOW_TIMEOUT)

            async def _run_stream_with_logging():
                nonlocal final_output, event_count, agent_messages_count
                async for event in workflow.run_stream(task_text):
                    event_count += 1
                    try:
                        event_type = type(event).__name__
                        if isinstance(event, MagenticOrchestratorMessageEvent):
                            message_text = getattr(event.message, "text", "")
                            self.logger.warning("[ORCHESTRATOR:%s] %s", event.kind, message_text[:200])

                        elif isinstance(event, MagenticAgentDeltaEvent):
                            try:
                                await streaming_agent_response_callback(
                                    event.agent_id, event, False, user_id,
                                )
                            except Exception as e:
                                self.logger.error(f"Streaming callback error for {event.agent_id}: {e}")

                        elif isinstance(event, MagenticAgentMessageEvent):
                            agent_messages_count += 1
                            self.logger.warning(
                                "Agent message #%d from %s (event #%d)",
                                agent_messages_count, event.agent_id, event_count,
                            )
                            if event.message:
                                try:
                                    agent_response_callback(event.agent_id, event.message, user_id)
                                except Exception as e:
                                    self.logger.error(f"Agent callback error for {event.agent_id}: {e}")
                                # Persist agent message to Cosmos DB
                                if plan_id:
                                    try:
                                        from v4.callbacks.response_handlers import clean_citations
                                        msg_text = ""
                                        if isinstance(event.message, ChatMessage):
                                            msg_text = event.message.text or ""
                                        else:
                                            msg_text = str(getattr(event.message, "text", ""))
                                        msg_text = clean_citations(msg_text)
                                        if msg_text:
                                            agent_msg = AgentMessageData(
                                                plan_id=plan_id,
                                                session_id=session_id or "",
                                                user_id=user_id,
                                                agent=event.agent_id or "unknown",
                                                agent_type=AgentMessageType.AI_AGENT,
                                                content=msg_text,
                                                raw_data=msg_text,
                                            )
                                            db = await DatabaseFactory.get_database(user_id=user_id)
                                            await db.add_agent_message(agent_msg)
                                            self.logger.warning(
                                                "Persisted agent message: agent=%s len=%d",
                                                event.agent_id, len(msg_text),
                                            )
                                    except Exception as persist_err:
                                        self.logger.error("Failed to persist agent message: %s", persist_err)

                        elif isinstance(event, MagenticFinalResultEvent):
                            final_text = getattr(event.message, "text", "")
                            self.logger.warning(f"[FINAL RESULT] Length: {len(final_text)} chars")

                        elif isinstance(event, WorkflowOutputEvent):
                            output_data = event.data
                            if isinstance(output_data, ChatMessage):
                                final_output = getattr(output_data, "text", None) or str(output_data)
                            else:
                                final_output = str(output_data)
                            self.logger.warning("Received workflow output event")

                        else:
                            self.logger.warning("Unknown event type: %s (#%d)", event_type, event_count)

                    except Exception as e:
                        self.logger.error(
                            f"Error processing event {type(event).__name__}: {e}",
                            exc_info=True,
                        )

            try:
                await asyncio.wait_for(_run_stream_with_logging(), timeout=MAX_WORKFLOW_TIMEOUT)
            except asyncio.TimeoutError:
                self.logger.error(
                    "=== WORKFLOW TIMED OUT after %ds === events=%d agent_msgs=%d",
                    MAX_WORKFLOW_TIMEOUT, event_count, agent_messages_count,
                )
                # Still proceed to mark plan with partial results

            final_text = final_output if final_output else ""

            self.logger.warning(
                "=== ORCHESTRATION COMPLETE === result_len=%d events=%d agent_msgs=%d",
                len(final_text), event_count, agent_messages_count,
            )

            # Update plan status to completed in Cosmos DB
            if plan_id:
                try:
                    db = await DatabaseFactory.get_database(user_id=user_id)
                    query_str = (
                        "SELECT * FROM c WHERE c.plan_id=@pid AND c.data_type='plan'"
                    )
                    plans = list(
                        db.container.query_items(
                            query=query_str,
                            parameters=[{"name": "@pid", "value": plan_id}],
                            enable_cross_partition_query=True,
                        )
                    )
                    if plans:
                        plan_doc = plans[0]
                        plan_doc["overall_status"] = PlanStatus.completed.value
                        plan_doc["summary"] = final_text[:500] if final_text else f"Completed ({agent_messages_count} agent responses)"
                        db.container.upsert_item(plan_doc)
                        self.logger.warning("Plan %s marked as completed", plan_id)
                except Exception as e:
                    self.logger.warning("Failed to update plan status: %s", e)

            # Send final result via WebSocket
            await connection_config.send_status_update_async(
                {
                    "type": WebsocketMessageType.FINAL_RESULT_MESSAGE,
                    "data": {
                        "content": final_text,
                        "status": "completed",
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                },
                user_id,
                message_type=WebsocketMessageType.FINAL_RESULT_MESSAGE,
            )
            self.logger.info("Final result sent via WebSocket to user '%s'", user_id)

        except Exception as e:
            # Error handling
            self.logger.error("Unexpected orchestration error: %s", e, exc_info=True)
            self.logger.error("Error type: %s", type(e).__name__)
            if hasattr(e, "__dict__"):
                self.logger.error("Error attributes: %s", e.__dict__)
            self.logger.info("=" * 50)

            # Update plan status to failed
            if plan_id:
                try:
                    db = await DatabaseFactory.get_database(user_id=user_id)
                    query = (
                        "SELECT * FROM c WHERE c.plan_id=@pid AND c.data_type='plan'"
                    )
                    plans = list(
                        db.container.query_items(
                            query=query,
                            parameters=[{"name": "@pid", "value": plan_id}],
                            enable_cross_partition_query=True,
                        )
                    )
                    if plans:
                        plan_doc = plans[0]
                        plan_doc["overall_status"] = "failed"
                        plan_doc["summary"] = f"Error: {str(e)[:300]}"
                        db.container.upsert_item(plan_doc)
                except Exception:
                    pass

            # Send error status to user
            try:
                await connection_config.send_status_update_async(
                    {
                        "type": WebsocketMessageType.FINAL_RESULT_MESSAGE,
                        "data": {
                            "content": f"Error during orchestration: {str(e)}",
                            "status": "error",
                            "timestamp": asyncio.get_event_loop().time(),
                        },
                    },
                    user_id,
                    message_type=WebsocketMessageType.FINAL_RESULT_MESSAGE,
                )
            except Exception as send_error:
                self.logger.error("Failed to send error status: %s", send_error)
            raise
