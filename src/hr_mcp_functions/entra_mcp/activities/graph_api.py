"""Microsoft Graph API activity functions for Entra ID operations.

Each function wraps a single Graph API call.  Simulated in local
development; production uses real Graph API with Managed Identity.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def create_user(
    first_name: str,
    last_name: str,
    department: str,
    usage_location: str = "US",
) -> Dict[str, Any]:
    """POST /users — create an Entra ID user."""
    upn = f"{first_name.lower()}.{last_name.lower()}@contoso.com"
    logger.info("Graph API: Creating user %s", upn)
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "userPrincipalName": upn,
        "displayName": f"{first_name} {last_name}",
        "accountEnabled": True,
    }


async def assign_license(upn: str, sku_ids: List[str]) -> Dict[str, Any]:
    """POST /users/{upn}/assignLicense — assign M365 licenses."""
    logger.info("Graph API: Assigning %d license(s) to %s", len(sku_ids), upn)
    return {"upn": upn, "addLicenses": sku_ids, "status": "assigned"}


async def add_to_group(upn: str, group_id: str) -> Dict[str, Any]:
    """POST /groups/{group_id}/members/$ref — add user to security group."""
    logger.info("Graph API: Adding %s to group %s", upn, group_id)
    return {"upn": upn, "groupId": group_id, "status": "added"}


async def set_manager(upn: str, manager_upn: str) -> Dict[str, Any]:
    """PUT /users/{upn}/manager/$ref — set manager relationship."""
    logger.info("Graph API: Setting manager of %s to %s", upn, manager_upn)
    return {"upn": upn, "manager": manager_upn, "status": "set"}


async def disable_user(upn: str) -> Dict[str, Any]:
    """PATCH /users/{upn} — disable sign-in."""
    logger.info("Graph API: Disabling user %s", upn)
    return {"upn": upn, "accountEnabled": False, "status": "disabled"}


async def revoke_sessions(upn: str) -> Dict[str, Any]:
    """POST /users/{upn}/revokeSignInSessions — revoke all sessions."""
    logger.info("Graph API: Revoking sessions for %s", upn)
    return {"upn": upn, "sessionsRevoked": True}


async def remove_all_licenses(upn: str) -> Dict[str, Any]:
    """POST /users/{upn}/assignLicense — remove all licenses."""
    logger.info("Graph API: Removing all licenses from %s", upn)
    return {"upn": upn, "removeLicenses": "all", "status": "removed"}


async def remove_from_all_groups(upn: str) -> Dict[str, Any]:
    """GET memberOf + DELETE for each — remove from all groups."""
    logger.info("Graph API: Removing %s from all groups", upn)
    return {"upn": upn, "groupsRemoved": 12, "status": "removed"}


async def convert_mailbox(
    upn: str, delegate: Optional[str] = None
) -> Dict[str, Any]:
    """Exchange Online: convert to shared mailbox via Graph/PowerShell."""
    logger.info("Graph API: Converting mailbox for %s to shared", upn)
    return {"upn": upn, "type": "shared", "delegate": delegate, "status": "converted"}


async def set_forwarding(
    upn: str, forward_to: str, days: int = 90
) -> Dict[str, Any]:
    """PATCH /users/{upn}/mailboxSettings — set auto-forward rule."""
    logger.info("Graph API: Setting forwarding for %s to %s", upn, forward_to)
    return {
        "upn": upn,
        "forwardTo": forward_to,
        "durationDays": days,
        "status": "enabled",
    }


async def transfer_onedrive(upn: str, new_owner: str) -> Dict[str, Any]:
    """SharePoint Admin API: initiate OneDrive site collection transfer."""
    logger.info(
        "Graph API: Transferring OneDrive from %s to %s", upn, new_owner
    )
    return {"upn": upn, "newOwner": new_owner, "status": "initiated"}


async def get_sign_in_logs(
    upn: str, days: int = 30
) -> Dict[str, Any]:
    """GET /auditLogs/signIns — retrieve sign-in activity."""
    logger.info("Graph API: Fetching %d-day sign-in logs for %s", days, upn)
    return {
        "upn": upn,
        "periodDays": days,
        "totalSignIns": 142,
        "failedSignIns": 3,
        "riskySignIns": 0,
    }
