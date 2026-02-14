"""Approval state management activity functions.

Encapsulates Cosmos DB operations for approval workflow persistence.
In local development these return simulated responses; in production
they use the Dapr state store or direct Cosmos DB SDK.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def create_approval_record(
    approval_id: str,
    action_type: str,
    employee_id: str,
    approver_chain: List[str],
    sla_hours: int,
    context: str = "",
) -> Dict[str, Any]:
    """Persist a new approval request to the state store.

    Args:
        approval_id: Unique approval identifier.
        action_type: Type of action requiring approval.
        employee_id: Employee the approval relates to.
        approver_chain: Ordered list of approver emails.
        sla_hours: SLA deadline in hours.
        context: Additional context for the approver.

    Returns:
        The created approval record.
    """
    logger.info("Creating approval record %s", approval_id)
    return {
        "approval_id": approval_id,
        "action_type": action_type,
        "employee_id": employee_id,
        "approver_chain": approver_chain,
        "current_approver": approver_chain[0] if approver_chain else None,
        "sla_hours": sla_hours,
        "context": context,
        "status": "pending",
        "history": [],
    }


async def get_approval_record(approval_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an approval record from the state store.

    Args:
        approval_id: Unique approval identifier.

    Returns:
        The approval record or None if not found.
    """
    logger.info("Retrieving approval record %s", approval_id)
    return {
        "approval_id": approval_id,
        "status": "pending",
        "current_approver": "manager@contoso.com",
        "history": [],
    }


async def update_approval_status(
    approval_id: str,
    status: str,
    approver: Optional[str] = None,
    comments: str = "",
) -> Dict[str, Any]:
    """Update approval status and append to history.

    Args:
        approval_id: Unique approval identifier.
        status: New status (approved, rejected, escalated, timed_out, cancelled).
        approver: Email of the approver who made the decision.
        comments: Optional comments from the approver.

    Returns:
        Updated approval record.
    """
    logger.info("Updating approval %s to status %s", approval_id, status)
    return {
        "approval_id": approval_id,
        "status": status,
        "approver": approver,
        "comments": comments,
    }


async def get_approval_audit_trail(approval_id: str) -> List[Dict[str, Any]]:
    """Retrieve the full audit trail for an approval workflow.

    Args:
        approval_id: Unique approval identifier.

    Returns:
        List of audit events in chronological order.
    """
    logger.info("Retrieving audit trail for %s", approval_id)
    return [
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
            "details": "Notification sent to first approver",
        },
    ]


async def cancel_approval_record(
    approval_id: str, reason: str = "Request withdrawn"
) -> Dict[str, Any]:
    """Mark an approval as cancelled.

    Args:
        approval_id: Unique approval identifier.
        reason: Cancellation reason.

    Returns:
        Updated approval record.
    """
    logger.info("Cancelling approval %s: %s", approval_id, reason)
    return {
        "approval_id": approval_id,
        "status": "cancelled",
        "reason": reason,
    }
