"""IT Provisioning MCP Server — Azure Function App.

Manages hardware provisioning (ServiceNow), software deployment (Intune),
VPN configuration, MFA setup, device wipe, and asset return tracking.
"""

import logging
import sys
from pathlib import Path

import azure.functions as func
import azure.durable_functions as df
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.models import error_response, success_response  # noqa: E402

logger = logging.getLogger(__name__)

mcp = FastMCP("IT Provisioning MCP Server")

# ---------------------------------------------------------------------------
# Onboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def provision_laptop(
    employee_name: str,
    employee_email: str,
    laptop_model: str = "Surface Laptop 6",
    os_image: str = "Windows 11 Enterprise",
) -> str:
    """Create a ServiceNow hardware request and track through fulfillment.

    Triggers a Durable Functions orchestrator that monitors the ServiceNow
    ticket until the laptop is shipped and received.
    """
    try:
        ticket_id = f"RITM-{hash(f'{employee_name}{laptop_model}') % 100000:05d}"
        details = {
            "ticket_id": ticket_id,
            "employee_name": employee_name,
            "employee_email": employee_email,
            "laptop_model": laptop_model,
            "os_image": os_image,
            "estimated_delivery": "3-5 business days",
            "status": "Requested",
        }
        return success_response(
            action="Laptop Provisioning Requested",
            details=details,
            summary=f"ServiceNow ticket {ticket_id} created for {laptop_model} for {employee_name}.",
        )
    except Exception as exc:
        return error_response("Provision Laptop", str(exc), "ServiceNow")


@mcp.tool()
async def install_software_bundle(
    employee_email: str,
    role_profile: str = "Standard Employee",
) -> str:
    """Push Intune software deployment policy based on role profile."""
    try:
        bundles = {
            "Standard Employee": [
                "Microsoft 365 Apps",
                "Microsoft Teams",
                "OneDrive",
                "Edge Browser",
                "Company Portal",
            ],
            "Developer": [
                "Microsoft 365 Apps",
                "Visual Studio Code",
                "Git",
                "Docker Desktop",
                "Azure CLI",
                "Python 3.12",
            ],
            "Designer": [
                "Microsoft 365 Apps",
                "Adobe Creative Cloud",
                "Figma",
                "Edge Browser",
            ],
        }
        apps = bundles.get(role_profile, bundles["Standard Employee"])
        details = {
            "employee_email": employee_email,
            "role_profile": role_profile,
            "applications": apps,
            "deployment_method": "Intune Required Assignment",
            "status": "Deployment Initiated",
        }
        return success_response(
            action="Software Bundle Deployed",
            details=details,
            summary=f"Deployed {len(apps)} apps to {employee_email} via Intune ({role_profile} profile).",
        )
    except Exception as exc:
        return error_response("Install Software Bundle", str(exc), "Intune")


@mcp.tool()
async def create_vpn_profile(
    employee_email: str,
    vpn_type: str = "Always-On",
) -> str:
    """Configure Always-On VPN or per-app VPN through Intune."""
    try:
        details = {
            "employee_email": employee_email,
            "vpn_type": vpn_type,
            "vpn_server": "vpn.contoso.com",
            "authentication": "Certificate-based",
            "split_tunnel": True,
            "status": "Profile Created",
        }
        return success_response(
            action="VPN Profile Created",
            details=details,
            summary=f"{vpn_type} VPN profile configured for {employee_email}.",
        )
    except Exception as exc:
        return error_response("Create VPN Profile", str(exc), "Intune")


@mcp.tool()
async def setup_mfa(
    employee_email: str,
    mfa_method: str = "Microsoft Authenticator",
) -> str:
    """Register user for passwordless authentication (FIDO2 or Authenticator)."""
    try:
        details = {
            "employee_email": employee_email,
            "mfa_method": mfa_method,
            "registration_link": f"https://aka.ms/mfasetup?user={employee_email}",
            "status": "Registration Link Sent",
        }
        return success_response(
            action="MFA Setup Initiated",
            details=details,
            summary=f"MFA registration link sent to {employee_email} for {mfa_method}.",
        )
    except Exception as exc:
        return error_response("Setup MFA", str(exc), "Entra ID / Security")


# ---------------------------------------------------------------------------
# Offboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def request_asset_return(
    employee_name: str,
    employee_email: str,
    assets: str = "Laptop, Monitor, Headset",
) -> str:
    """Create a ServiceNow asset return ticket with prepaid shipping label.

    Triggers a Durable Functions orchestrator that tracks return receipt.
    """
    try:
        ticket_id = f"RITM-{hash(f'{employee_name}return') % 100000:05d}"
        asset_list = [a.strip() for a in assets.split(",")]
        details = {
            "ticket_id": ticket_id,
            "employee_name": employee_name,
            "employee_email": employee_email,
            "assets_to_return": asset_list,
            "shipping_label": "Prepaid UPS label attached",
            "return_deadline": "14 days from notification",
            "status": "Return Requested",
        }
        return success_response(
            action="Asset Return Requested",
            details=details,
            summary=f"Asset return ticket {ticket_id} created for {employee_name} ({len(asset_list)} items).",
        )
    except Exception as exc:
        return error_response("Request Asset Return", str(exc), "ServiceNow")


@mcp.tool()
async def wipe_device(
    employee_email: str,
    wipe_type: str = "selective",
) -> str:
    """Trigger Intune selective or full wipe on all enrolled devices."""
    try:
        details = {
            "employee_email": employee_email,
            "wipe_type": wipe_type,
            "devices_targeted": 2,
            "status": "Wipe Initiated",
        }
        return success_response(
            action="Device Wipe Initiated",
            details=details,
            summary=f"{wipe_type.capitalize()} wipe initiated on 2 device(s) for {employee_email}.",
        )
    except Exception as exc:
        return error_response("Wipe Device", str(exc), "Intune")


@mcp.tool()
async def revoke_vpn_access(employee_email: str) -> str:
    """Remove VPN profile and block network access."""
    try:
        details = {
            "employee_email": employee_email,
            "vpn_profile_removed": True,
            "network_access_blocked": True,
            "status": "VPN Access Revoked",
        }
        return success_response(
            action="VPN Access Revoked",
            details=details,
            summary=f"VPN access revoked for {employee_email}.",
        )
    except Exception as exc:
        return error_response("Revoke VPN Access", str(exc), "Intune")


@mcp.tool()
async def revoke_app_access(employee_email: str) -> str:
    """Remove app assignments and enterprise app consent."""
    try:
        details = {
            "employee_email": employee_email,
            "app_assignments_removed": 8,
            "enterprise_app_consent_revoked": True,
            "oauth_grants_removed": 5,
            "status": "App Access Revoked",
        }
        return success_response(
            action="App Access Revoked",
            details=details,
            summary=f"Removed 8 app assignments and 5 OAuth grants for {employee_email}.",
        )
    except Exception as exc:
        return error_response("Revoke App Access", str(exc), "Entra ID / Intune")


@mcp.tool()
async def generate_asset_report(employee_email: str) -> str:
    """List all assets assigned to the employee with serial numbers."""
    try:
        details = {
            "employee_email": employee_email,
            "assets": [
                {"type": "Laptop", "model": "Surface Laptop 6", "serial": "SN-LP-2024-001", "condition": "Good"},
                {"type": "Monitor", "model": "Dell U2723QE", "serial": "SN-MN-2024-002", "condition": "Good"},
                {"type": "Headset", "model": "Jabra Evolve2 85", "serial": "SN-HS-2024-003", "condition": "Good"},
                {"type": "Docking Station", "model": "Surface Thunderbolt 4", "serial": "SN-DS-2024-004", "condition": "Good"},
            ],
            "total_assets": 4,
            "status": "Report Generated",
        }
        return success_response(
            action="Asset Report Generated",
            details=details,
            summary=f"Asset report generated for {employee_email}: 4 items assigned.",
        )
    except Exception as exc:
        return error_response("Generate Asset Report", str(exc), "ServiceNow / CMDB")


# ---------------------------------------------------------------------------
# Durable Functions orchestrators
# ---------------------------------------------------------------------------

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.orchestration_trigger(context_name="context")
def laptop_provision_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator: track ServiceNow laptop fulfillment."""
    import datetime

    input_data = context.get_input()
    ticket_id = input_data["ticket_id"]

    # Poll ServiceNow every 6 hours, timeout after 10 days
    expiry = context.current_utc_datetime + datetime.timedelta(days=10)

    while context.current_utc_datetime < expiry:
        status = yield context.call_activity("poll_servicenow_ticket", ticket_id)
        if status in ("fulfilled", "cancelled"):
            return {"ticket_id": ticket_id, "result": status}

        next_check = context.current_utc_datetime + datetime.timedelta(hours=6)
        yield context.create_timer(next_check)

    return {"ticket_id": ticket_id, "result": "timed_out"}


@app.orchestration_trigger(context_name="context")
def asset_return_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator: track asset return shipping."""
    import datetime

    input_data = context.get_input()
    ticket_id = input_data["ticket_id"]

    # Send shipping label
    yield context.call_activity("send_shipping_label", input_data)

    # Poll daily for 14 days
    expiry = context.current_utc_datetime + datetime.timedelta(days=14)
    while context.current_utc_datetime < expiry:
        status = yield context.call_activity("poll_asset_return_status", ticket_id)
        if status == "received":
            yield context.call_activity("process_returned_assets", input_data)
            return {"ticket_id": ticket_id, "result": "received"}

        next_check = context.current_utc_datetime + datetime.timedelta(days=1)
        yield context.create_timer(next_check)

    return {"ticket_id": ticket_id, "result": "overdue"}


@app.activity_trigger(input_name="ticketId")
def poll_servicenow_ticket(ticketId: str) -> str:
    logger.info("Polling ServiceNow ticket %s", ticketId)
    return "fulfilled"


@app.activity_trigger(input_name="data")
def send_shipping_label(data: dict) -> str:
    logger.info("Sending shipping label for %s", data.get("ticket_id"))
    return "sent"


@app.activity_trigger(input_name="ticketId")
def poll_asset_return_status(ticketId: str) -> str:
    logger.info("Polling asset return status for %s", ticketId)
    return "received"


@app.activity_trigger(input_name="data")
def process_returned_assets(data: dict) -> str:
    logger.info("Processing returned assets for %s", data.get("ticket_id"))
    return "processed"


# ---------------------------------------------------------------------------
# HTTP trigger
# ---------------------------------------------------------------------------


@app.route(route="mcp/{*path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    from fastmcp.server.http import create_http_handler

    handler = create_http_handler(mcp)
    return await handler(req)
