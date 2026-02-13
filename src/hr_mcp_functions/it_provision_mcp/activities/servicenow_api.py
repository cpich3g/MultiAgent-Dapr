"""ServiceNow and Intune API activity functions for IT Provisioning."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def create_hardware_request(
    employee_name: str,
    model: str,
    os_image: str,
) -> Dict[str, Any]:
    """POST /api/sn_sc/servicecatalog/items/{item_id}/order_now — ServiceNow."""
    logger.info("ServiceNow: Creating hardware request for %s", employee_name)
    return {
        "result": {
            "number": f"RITM-{hash(f'{employee_name}{model}') % 100000:05d}",
            "state": "open",
            "short_description": f"Laptop provisioning: {model}",
        }
    }


async def get_ticket_status(ticket_id: str) -> str:
    """GET /api/now/table/sc_req_item/{ticket_id} — poll ServiceNow."""
    logger.info("ServiceNow: Polling ticket %s", ticket_id)
    return "fulfilled"


async def deploy_intune_apps(
    upn: str, app_ids: list[str]
) -> Dict[str, Any]:
    """POST /deviceAppManagement/mobileApps/{app_id}/assign — Intune."""
    logger.info("Intune: Deploying %d apps to %s", len(app_ids), upn)
    return {"upn": upn, "deployedApps": len(app_ids), "status": "deploying"}


async def create_vpn_configuration(
    upn: str, vpn_type: str
) -> Dict[str, Any]:
    """POST /deviceManagement/deviceConfigurations — Intune VPN profile."""
    logger.info("Intune: Creating %s VPN profile for %s", vpn_type, upn)
    return {"upn": upn, "vpnType": vpn_type, "status": "created"}


async def wipe_managed_device(
    device_id: str, wipe_type: str = "selective"
) -> Dict[str, Any]:
    """POST /deviceManagement/managedDevices/{id}/wipe — Intune device wipe."""
    logger.info("Intune: %s wipe on device %s", wipe_type, device_id)
    return {"deviceId": device_id, "wipeType": wipe_type, "status": "initiated"}


async def create_asset_return_ticket(
    employee_name: str, assets: list[str]
) -> Dict[str, Any]:
    """POST /api/now/table/sc_req_item — ServiceNow asset return."""
    logger.info("ServiceNow: Creating asset return for %s", employee_name)
    return {
        "result": {
            "number": f"RITM-{hash(f'{employee_name}return') % 100000:05d}",
            "state": "open",
            "assets": assets,
        }
    }
