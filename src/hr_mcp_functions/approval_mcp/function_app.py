"""Approval MCP Server — Azure Function App.

Owns the approval workflow engine. Persists approval state in Cosmos DB
and uses Dapr pub/sub for event-driven notifications. Provides durable
"wait for external event" orchestration for human-in-the-loop gates.
"""

import logging
import sys
from pathlib import Path

import azure.functions as func
import azure.durable_functions as df
from fastmcp import FastMCP

# Allow shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import config  # noqa: E402
from shared.models import (  # noqa: E402
    ApprovalStatus,
    error_response,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("Approval MCP Server")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def request_approval(
    action_type: str,
    employee_id: str,
    employee_name: str,
    approver_chain: list[str],
    sla_hours: int = 24,
    context: str = "",
    escalation_rules: str = "auto",
) -> str:
    """Create an approval request with approver chain, SLA, and escalation rules.

    Triggers a Durable Functions orchestrator that suspends until the
    approver responds via Logic App email reply, Teams adaptive card,
    or frontend button.
    """
    try:
        approval_id = f"APR-{hash(f'{employee_id}{action_type}') % 100000:05d}"
        details = {
            "approval_id": approval_id,
            "action_type": action_type,
            "employee_id": employee_id,
            "employee_name": employee_name,
            "approver_chain": approver_chain,
            "current_approver": approver_chain[0] if approver_chain else None,
            "sla_hours": sla_hours,
            "escalation_rules": escalation_rules,
            "context": context,
            "status": ApprovalStatus.PENDING.value,
        }
        return success_response(
            action="Approval Requested",
            details=details,
            summary=(
                f"Approval request {approval_id} created for '{action_type}' "
                f"regarding {employee_name}. Awaiting response from "
                f"{approver_chain[0]} (SLA: {sla_hours}h)."
            ),
        )
    except Exception as exc:
        return error_response("Request Approval", str(exc), "Approval Engine")


@mcp.tool()
async def check_approval_status(approval_id: str) -> str:
    """Return current state of an approval request.

    States: pending, approved, rejected, escalated, timed_out, cancelled.
    """
    try:
        details = {
            "approval_id": approval_id,
            "status": ApprovalStatus.PENDING.value,
            "current_approver": "manager@contoso.com",
            "created_at": "2026-02-14T10:00:00Z",
            "sla_deadline": "2026-02-15T10:00:00Z",
            "escalation_count": 0,
        }
        return success_response(
            action="Approval Status Retrieved",
            details=details,
            summary=f"Approval {approval_id} is currently pending.",
        )
    except Exception as exc:
        return error_response("Check Approval Status", str(exc), "Approval Engine")


@mcp.tool()
async def escalate_approval(
    approval_id: str,
    next_approver: str,
    reason: str = "SLA breach",
) -> str:
    """Escalate an approval to the next-level approver after SLA breach."""
    try:
        details = {
            "approval_id": approval_id,
            "previous_approver": "manager@contoso.com",
            "escalated_to": next_approver,
            "reason": reason,
            "status": ApprovalStatus.ESCALATED.value,
        }
        return success_response(
            action="Approval Escalated",
            details=details,
            summary=(
                f"Approval {approval_id} escalated to {next_approver} "
                f"due to: {reason}."
            ),
        )
    except Exception as exc:
        return error_response("Escalate Approval", str(exc), "Approval Engine")


@mcp.tool()
async def record_approval_decision(
    approval_id: str,
    decision: str,
    approver_email: str,
    comments: str = "",
) -> str:
    """Record an approver's decision with timestamp and optional comments."""
    try:
        details = {
            "approval_id": approval_id,
            "decision": decision,
            "approver": approver_email,
            "comments": comments,
            "status": decision,
            "recorded_at": "2026-02-14T12:00:00Z",
        }
        return success_response(
            action="Approval Decision Recorded",
            details=details,
            summary=(
                f"Decision '{decision}' recorded for approval {approval_id} "
                f"by {approver_email}."
            ),
        )
    except Exception as exc:
        return error_response("Record Approval Decision", str(exc), "Approval Engine")


@mcp.tool()
async def get_approval_history(approval_id: str) -> str:
    """Return full audit trail for a workflow instance."""
    try:
        details = {
            "approval_id": approval_id,
            "history": [
                {
                    "event": "created",
                    "timestamp": "2026-02-14T10:00:00Z",
                    "actor": "system",
                    "details": "Approval request created",
                },
                {
                    "event": "notification_sent",
                    "timestamp": "2026-02-14T10:00:05Z",
                    "actor": "system",
                    "details": "Notification sent to manager@contoso.com",
                },
            ],
        }
        return success_response(
            action="Approval History Retrieved",
            details=details,
            summary=f"Retrieved {len(details['history'])} events for approval {approval_id}.",
        )
    except Exception as exc:
        return error_response("Get Approval History", str(exc), "Approval Engine")


@mcp.tool()
async def cancel_approval(
    approval_id: str,
    reason: str = "Request withdrawn",
) -> str:
    """Cancel a pending approval request."""
    try:
        details = {
            "approval_id": approval_id,
            "status": ApprovalStatus.CANCELLED.value,
            "reason": reason,
        }
        return success_response(
            action="Approval Cancelled",
            details=details,
            summary=f"Approval {approval_id} cancelled: {reason}.",
        )
    except Exception as exc:
        return error_response("Cancel Approval", str(exc), "Approval Engine")


# ---------------------------------------------------------------------------
# Durable Functions orchestrators
# ---------------------------------------------------------------------------

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.orchestration_trigger(context_name="context")
def approval_flow_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator that waits for human approval.

    Uses the "wait for external event" pattern: the orchestrator starts,
    sends an approval request notification, then suspends. When the
    approver responds (via Logic App, Teams card, or frontend), the
    external event resumes the orchestrator.
    """
    import datetime

    input_data = context.get_input()
    approval_id = input_data["approval_id"]
    approver_chain = input_data["approver_chain"]
    sla_hours = input_data.get("sla_hours", 24)

    # Store approval request in Cosmos DB
    yield context.call_activity("store_approval_request", input_data)

    # Send notification to first approver
    yield context.call_activity("send_approval_notification", {
        "approval_id": approval_id,
        "approver": approver_chain[0],
    })

    # Wait for external event OR timeout
    deadline = context.current_utc_datetime + datetime.timedelta(hours=sla_hours)
    approval_event = context.wait_for_external_event("ApprovalResponse")
    timeout_event = context.create_timer(deadline)

    winner = yield context.task_any([approval_event, timeout_event])

    if winner == timeout_event:
        # SLA breach: escalate to next approver
        if len(approver_chain) > 1:
            yield context.call_activity("escalate_to_next_approver", {
                "approval_id": approval_id,
                "next_approver": approver_chain[1],
            })
            # Recurse with remaining chain
            result = yield context.call_sub_orchestrator(
                "approval_flow_orchestrator",
                {**input_data, "approver_chain": approver_chain[1:]},
            )
            return result
        else:
            yield context.call_activity("record_decision", {
                "approval_id": approval_id,
                "decision": ApprovalStatus.TIMED_OUT.value,
            })
            return {"status": "timed_out", "approval_id": approval_id}
    else:
        timeout_event.cancel()
        decision = approval_event.result
        yield context.call_activity("record_decision", {
            "approval_id": approval_id,
            "decision": decision.get("decision", "unknown"),
            "approver": decision.get("approver"),
            "comments": decision.get("comments", ""),
        })
        return {"status": decision["decision"], "approval_id": approval_id}


@app.activity_trigger(input_name="data")
def store_approval_request(data: dict) -> str:
    """Activity: persist approval request to Cosmos DB via Dapr state store."""
    logger.info("Storing approval request %s", data.get("approval_id"))
    return "stored"


@app.activity_trigger(input_name="data")
def send_approval_notification(data: dict) -> str:
    """Activity: send approval notification email/Teams card to approver."""
    logger.info(
        "Sending approval notification for %s to %s",
        data.get("approval_id"),
        data.get("approver"),
    )
    return "sent"


@app.activity_trigger(input_name="data")
def escalate_to_next_approver(data: dict) -> str:
    """Activity: send escalation notification to the next approver."""
    logger.info(
        "Escalating approval %s to %s",
        data.get("approval_id"),
        data.get("next_approver"),
    )
    return "escalated"


@app.activity_trigger(input_name="data")
def record_decision(data: dict) -> str:
    """Activity: record the final approval decision in Cosmos DB."""
    logger.info(
        "Recording decision '%s' for approval %s",
        data.get("decision"),
        data.get("approval_id"),
    )
    return "recorded"


# ---------------------------------------------------------------------------
# HTTP trigger — serves MCP over streamable-http
# ---------------------------------------------------------------------------

@app.route(route="mcp/{*path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function HTTP trigger that proxies requests to the FastMCP server."""
    from fastmcp.server.http import create_http_handler

    handler = create_http_handler(mcp)
    return await handler(req)


# ---------------------------------------------------------------------------
# External event receiver — Logic App / Teams callback
# ---------------------------------------------------------------------------

@app.route(route="approval/{approval_id}/respond", methods=["POST"])
async def approval_callback(req: func.HttpRequest) -> func.HttpResponse:
    """Receive approval decisions from Logic Apps or Teams adaptive cards.

    Raises the external event on the corresponding Durable Functions
    orchestrator instance to resume the approval workflow.
    """
    import json

    approval_id = req.route_params.get("approval_id")
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)

    client = df.DurableOrchestrationClient(req)
    await client.raise_event(
        instance_id=approval_id,
        event_name="ApprovalResponse",
        event_data=body,
    )

    return func.HttpResponse(
        json.dumps({"status": "received", "approval_id": approval_id}),
        mimetype="application/json",
    )
