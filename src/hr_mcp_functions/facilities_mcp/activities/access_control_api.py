"""Physical access control API activity functions for Facilities."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def create_badge_request(
    employee_name: str,
    building: str,
    floors: list[str],
) -> Dict[str, Any]:
    """Submit badge request to Lenel/HID access control system."""
    logger.info("Access Control: Badge request for %s at %s", employee_name, building)
    return {
        "badge_id": f"BDG-{hash(f'{employee_name}{building}') % 100000:05d}",
        "status": "submitted",
        "estimated_production": "2-3 business days",
    }


async def get_badge_status(badge_id: str) -> str:
    """Poll badge production status."""
    logger.info("Access Control: Polling badge %s", badge_id)
    return "printed"


async def activate_badge_in_system(badge_id: str, building: str) -> Dict[str, Any]:
    """Activate badge in the access control system."""
    logger.info("Access Control: Activating badge %s for %s", badge_id, building)
    return {"badge_id": badge_id, "building": building, "status": "activated"}


async def deactivate_badge_in_system(badge_id: str) -> Dict[str, Any]:
    """Deactivate badge in the access control system."""
    logger.info("Access Control: Deactivating badge %s", badge_id)
    return {"badge_id": badge_id, "status": "deactivated", "all_access_revoked": True}
