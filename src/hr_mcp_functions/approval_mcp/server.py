"""Standalone entry point for running the Approval MCP Server as a container.

This module wraps the FastMCP tools from function_app.py and serves them
over streamable-http without the Azure Functions runtime, suitable for
deployment as a Container App.
"""

import logging
import sys
from pathlib import Path

# Allow shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP

from shared.config import config  # noqa: E402
from shared.models import (  # noqa: E402
    ApprovalStatus,
    error_response,
    success_response,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Approval MCP Server")


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
    """Create an approval request with approver chain, SLA, and escalation rules."""
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
    """Return current state of an approval request."""
    try:
        details = {
            "approval_id": approval_id,
            "status": ApprovalStatus.PENDING.value,
            "current_approver": "justinjoy@microsoft.com",
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
            "previous_approver": "justinjoy@microsoft.com",
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
                    "details": "Notification sent to justinjoy@microsoft.com",
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
