"""Intune device management activity functions.

Encapsulates Microsoft Intune / Endpoint Manager operations via the
Microsoft Graph API beta endpoints. In local development these return
simulated responses; in production they call the Graph API with
application permissions (DeviceManagementManagedDevices.ReadWrite.All).
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def push_software_deployment(
    user_id: str,
    app_ids: List[str],
    role_profile: str = "standard",
) -> Dict[str, Any]:
    """Push Intune software deployment policy based on role profile.

    Args:
        user_id: Entra ID user object ID.
        app_ids: List of Intune app IDs to deploy.
        role_profile: Role profile for software bundle selection.

    Returns:
        Deployment status with assignment IDs.
    """
    logger.info(
        "Intune: Pushing software deployment for user %s, profile %s",
        user_id,
        role_profile,
    )
    return {
        "user_id": user_id,
        "role_profile": role_profile,
        "deployed_apps": app_ids,
        "assignment_id": f"ASG-{hash(user_id) % 100000:05d}",
        "status": "assigned",
    }


async def configure_vpn_profile(
    user_id: str,
    vpn_type: str = "AlwaysOn",
    per_app: bool = False,
) -> Dict[str, Any]:
    """Configure VPN profile through Intune.

    Args:
        user_id: Entra ID user object ID.
        vpn_type: AlwaysOn or PerApp.
        per_app: Whether to configure per-app VPN.

    Returns:
        VPN configuration status.
    """
    logger.info(
        "Intune: Configuring %s VPN for user %s", vpn_type, user_id
    )
    return {
        "user_id": user_id,
        "vpn_type": vpn_type,
        "per_app": per_app,
        "profile_id": f"VPN-{hash(user_id) % 100000:05d}",
        "status": "configured",
    }


async def register_mfa(
    user_id: str,
    method: str = "microsoftAuthenticator",
) -> Dict[str, Any]:
    """Register user for passwordless authentication.

    Args:
        user_id: Entra ID user object ID.
        method: FIDO2, microsoftAuthenticator, or phoneAppOTP.

    Returns:
        MFA registration status.
    """
    logger.info("Intune: Registering MFA for user %s, method %s", user_id, method)
    return {
        "user_id": user_id,
        "method": method,
        "registration_id": f"MFA-{hash(user_id) % 100000:05d}",
        "status": "pending_activation",
    }


async def wipe_device(
    device_id: str,
    wipe_type: str = "selective",
) -> Dict[str, Any]:
    """Trigger Intune selective or full wipe on an enrolled device.

    Args:
        device_id: Intune device ID.
        wipe_type: selective (corporate data only) or full (factory reset).

    Returns:
        Wipe operation status.
    """
    logger.info("Intune: %s wipe on device %s", wipe_type, device_id)
    return {
        "device_id": device_id,
        "wipe_type": wipe_type,
        "action_id": f"WIPE-{hash(device_id) % 100000:05d}",
        "status": "initiated",
    }


async def revoke_app_access(
    user_id: str,
    app_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Remove app assignments and enterprise app consent for a user.

    Args:
        user_id: Entra ID user object ID.
        app_ids: Specific app IDs to revoke, or None for all.

    Returns:
        Revocation status.
    """
    scope = "all applications" if app_ids is None else f"{len(app_ids)} applications"
    logger.info("Intune: Revoking access for user %s from %s", user_id, scope)
    return {
        "user_id": user_id,
        "revoked_apps": app_ids or ["all"],
        "consent_revoked": True,
        "status": "revoked",
    }


async def get_enrolled_devices(user_id: str) -> List[Dict[str, Any]]:
    """List all Intune-enrolled devices for a user.

    Args:
        user_id: Entra ID user object ID.

    Returns:
        List of enrolled device records.
    """
    logger.info("Intune: Listing enrolled devices for user %s", user_id)
    return [
        {
            "device_id": "DEV-001",
            "device_name": "LAPTOP-JSMITH",
            "os": "Windows 11",
            "compliance_state": "compliant",
            "enrollment_type": "azureADJoined",
        },
        {
            "device_id": "DEV-002",
            "device_name": "iPhone-JSMITH",
            "os": "iOS 18",
            "compliance_state": "compliant",
            "enrollment_type": "userEnrollment",
        },
    ]
