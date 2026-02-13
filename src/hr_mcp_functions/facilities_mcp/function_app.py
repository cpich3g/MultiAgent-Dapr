"""Facilities MCP Server — Azure Function App.

Manages physical access badges, workspace allocation, parking
assignments, and security escort scheduling.
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

mcp = FastMCP("Facilities MCP Server")

# ---------------------------------------------------------------------------
# Onboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def provision_badge(
    employee_name: str,
    employee_email: str,
    building: str = "Building 1",
    floor_access: str = "1,2,3",
    start_date: str = "",
) -> str:
    """Request a physical access badge with building and floor access levels.

    Triggers a Durable Functions orchestrator that tracks badge printing
    and activation with the access control system.
    """
    try:
        badge_id = f"BDG-{hash(f'{employee_name}{building}') % 100000:05d}"
        floors = [f.strip() for f in floor_access.split(",")]
        details = {
            "badge_id": badge_id,
            "employee_name": employee_name,
            "employee_email": employee_email,
            "building": building,
            "floor_access": floors,
            "activation_date": start_date or "Employee start date",
            "pickup_location": "Reception Desk — Building 1",
            "status": "Requested",
        }
        return success_response(
            action="Badge Provisioning Requested",
            details=details,
            summary=f"Badge {badge_id} requested for {employee_name} ({building}, floors {floor_access}).",
        )
    except Exception as exc:
        return error_response("Provision Badge", str(exc), "Access Control")


@mcp.tool()
async def assign_workspace(
    employee_name: str,
    department: str,
    building: str = "Building 1",
    hybrid_schedule: str = "Mon,Tue,Wed",
) -> str:
    """Reserve desk or office based on team location and hybrid schedule."""
    try:
        workspace_id = f"WS-{hash(f'{employee_name}{building}') % 10000:04d}"
        details = {
            "workspace_id": workspace_id,
            "employee_name": employee_name,
            "department": department,
            "building": building,
            "floor": 3,
            "zone": "A",
            "desk_number": f"3A-{hash(employee_name) % 50 + 1:02d}",
            "hybrid_days": [d.strip() for d in hybrid_schedule.split(",")],
            "status": "Assigned",
        }
        return success_response(
            action="Workspace Assigned",
            details=details,
            summary=f"Workspace {details['desk_number']} assigned to {employee_name} in {building}.",
        )
    except Exception as exc:
        return error_response("Assign Workspace", str(exc), "Facilities")


@mcp.tool()
async def provision_parking(
    employee_name: str,
    location: str = "HQ",
    vehicle_type: str = "Standard",
) -> str:
    """Assign a parking spot based on office location."""
    try:
        spot_id = f"PKG-{hash(f'{employee_name}{location}') % 1000:03d}"
        details = {
            "spot_id": spot_id,
            "employee_name": employee_name,
            "location": location,
            "lot": "Garage A" if vehicle_type == "Standard" else "Garage B — EV Charging",
            "vehicle_type": vehicle_type,
            "status": "Assigned",
        }
        return success_response(
            action="Parking Assigned",
            details=details,
            summary=f"Parking spot {spot_id} assigned to {employee_name} at {details['lot']}.",
        )
    except Exception as exc:
        return error_response("Provision Parking", str(exc), "Facilities")


# ---------------------------------------------------------------------------
# Offboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def deactivate_badge(
    employee_name: str,
    badge_id: str = "",
    immediate: bool = True,
) -> str:
    """Immediately deactivate physical access badge."""
    try:
        details = {
            "employee_name": employee_name,
            "badge_id": badge_id or "auto-resolved",
            "deactivation_time": "Immediate" if immediate else "End of last day",
            "all_buildings_revoked": True,
            "status": "Deactivated",
        }
        return success_response(
            action="Badge Deactivated",
            details=details,
            summary=f"Badge for {employee_name} deactivated {'immediately' if immediate else 'at end of day'}.",
        )
    except Exception as exc:
        return error_response("Deactivate Badge", str(exc), "Access Control")


@mcp.tool()
async def release_workspace(
    employee_name: str,
    workspace_id: str = "",
) -> str:
    """Mark workspace as available for reassignment."""
    try:
        details = {
            "employee_name": employee_name,
            "workspace_id": workspace_id or "auto-resolved",
            "status": "Released",
        }
        return success_response(
            action="Workspace Released",
            details=details,
            summary=f"Workspace for {employee_name} released and available for reassignment.",
        )
    except Exception as exc:
        return error_response("Release Workspace", str(exc), "Facilities")


@mcp.tool()
async def revoke_parking(
    employee_name: str,
    spot_id: str = "",
) -> str:
    """Release parking assignment."""
    try:
        details = {
            "employee_name": employee_name,
            "spot_id": spot_id or "auto-resolved",
            "status": "Revoked",
        }
        return success_response(
            action="Parking Revoked",
            details=details,
            summary=f"Parking assignment for {employee_name} revoked.",
        )
    except Exception as exc:
        return error_response("Revoke Parking", str(exc), "Facilities")


@mcp.tool()
async def schedule_escort(
    employee_name: str,
    date: str,
    time: str = "17:00",
    building: str = "Building 1",
) -> str:
    """Schedule security escort for final day (involuntary terminations)."""
    try:
        details = {
            "employee_name": employee_name,
            "date": date,
            "time": time,
            "building": building,
            "security_team_notified": True,
            "status": "Scheduled",
        }
        return success_response(
            action="Security Escort Scheduled",
            details=details,
            summary=f"Security escort scheduled for {employee_name} on {date} at {time}.",
        )
    except Exception as exc:
        return error_response("Schedule Escort", str(exc), "Security")


# ---------------------------------------------------------------------------
# Durable Functions orchestrators
# ---------------------------------------------------------------------------

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.orchestration_trigger(context_name="context")
def badge_provision_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator: badge printing and activation tracking."""
    import datetime

    input_data = context.get_input()
    badge_id = input_data["badge_id"]

    # Request badge printing
    yield context.call_activity("request_badge_printing", input_data)

    # Poll printing status every 4 hours, timeout after 5 days
    expiry = context.current_utc_datetime + datetime.timedelta(days=5)
    while context.current_utc_datetime < expiry:
        status = yield context.call_activity("poll_badge_status", badge_id)
        if status == "printed":
            yield context.call_activity("activate_badge", input_data)
            return {"badge_id": badge_id, "result": "activated"}

        next_check = context.current_utc_datetime + datetime.timedelta(hours=4)
        yield context.create_timer(next_check)

    return {"badge_id": badge_id, "result": "timed_out"}


@app.activity_trigger(input_name="data")
def request_badge_printing(data: dict) -> str:
    logger.info("Requesting badge printing for %s", data.get("badge_id"))
    return "submitted"


@app.activity_trigger(input_name="badgeId")
def poll_badge_status(badgeId: str) -> str:
    logger.info("Polling badge status for %s", badgeId)
    return "printed"


@app.activity_trigger(input_name="data")
def activate_badge(data: dict) -> str:
    logger.info("Activating badge %s", data.get("badge_id"))
    return "activated"


# ---------------------------------------------------------------------------
# HTTP trigger
# ---------------------------------------------------------------------------


@app.route(route="mcp/{*path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    from fastmcp.server.http import create_http_handler

    handler = create_http_handler(mcp)
    return await handler(req)
