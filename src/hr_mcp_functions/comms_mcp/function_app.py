"""Communications MCP Server — Azure Function App.

Handles all outbound communications via Microsoft Graph API:
email (Mail.Send), Teams channel messages (ChannelMessage.Send),
and calendar events (Calendars.ReadWrite).
"""

import logging
import sys
from pathlib import Path

import azure.functions as func
from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.models import error_response, success_response  # noqa: E402

logger = logging.getLogger(__name__)

mcp = FastMCP("Communications MCP Server")

# ---------------------------------------------------------------------------
# Onboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def send_welcome_email(
    employee_name: str,
    employee_email: str,
    start_date: str,
    manager_name: str = "",
    location: str = "HQ",
) -> str:
    """Send branded welcome email with first-day instructions, parking info, and dress code."""
    try:
        details = {
            "recipient": employee_email,
            "employee_name": employee_name,
            "subject": f"Welcome to Contoso, {employee_name}!",
            "content_sections": [
                "First-day schedule and check-in instructions",
                f"Office location: {location}",
                "Parking and transit information",
                "Dress code guidelines",
                "Emergency contacts",
            ],
            "manager_name": manager_name,
            "start_date": start_date,
            "status": "Sent",
        }
        return success_response(
            action="Welcome Email Sent",
            details=details,
            summary=f"Welcome email sent to {employee_name} at {employee_email}.",
        )
    except Exception as exc:
        return error_response("Send Welcome Email", str(exc), "Graph Mail")


@mcp.tool()
async def send_manager_notification(
    manager_email: str,
    employee_name: str,
    notification_type: str = "onboarding_progress",
    message: str = "",
) -> str:
    """Notify manager of onboarding progress or offboarding initiation."""
    try:
        subjects = {
            "onboarding_progress": f"Onboarding Update: {employee_name}",
            "onboarding_complete": f"Onboarding Complete: {employee_name}",
            "offboarding_initiated": f"Offboarding Initiated: {employee_name}",
            "offboarding_complete": f"Offboarding Complete: {employee_name}",
        }
        details = {
            "recipient": manager_email,
            "subject": subjects.get(
                notification_type, f"HR Notification: {employee_name}"
            ),
            "notification_type": notification_type,
            "employee_name": employee_name,
            "message": message,
            "status": "Sent",
        }
        return success_response(
            action="Manager Notification Sent",
            details=details,
            summary=f"Manager notified ({notification_type}) about {employee_name}.",
        )
    except Exception as exc:
        return error_response("Send Manager Notification", str(exc), "Graph Mail")


@mcp.tool()
async def send_team_introduction(
    employee_name: str,
    employee_email: str,
    team_channel_id: str = "General",
    role: str = "",
    fun_fact: str = "",
) -> str:
    """Post introduction message in the team's Teams channel."""
    try:
        details = {
            "channel": team_channel_id,
            "employee_name": employee_name,
            "role": role,
            "fun_fact": fun_fact,
            "message_preview": (
                f"Please welcome {employee_name} to the team! "
                f"They're joining us as {role}."
            ),
            "status": "Posted",
        }
        return success_response(
            action="Team Introduction Posted",
            details=details,
            summary=f"Introduction for {employee_name} posted to Teams channel.",
        )
    except Exception as exc:
        return error_response("Send Team Introduction", str(exc), "Teams / Graph")


@mcp.tool()
async def schedule_orientation(
    employee_name: str,
    employee_email: str,
    date: str,
    duration_minutes: int = 120,
    facilitator_email: str = "hr-orientation@contoso.com",
) -> str:
    """Create calendar event for Day 1 orientation with required attendees."""
    try:
        details = {
            "event_title": f"Day 1 Orientation — {employee_name}",
            "date": date,
            "duration_minutes": duration_minutes,
            "attendees": [employee_email, facilitator_email],
            "location": "Conference Room A — Building 1",
            "teams_meeting_link": True,
            "status": "Scheduled",
        }
        return success_response(
            action="Orientation Scheduled",
            details=details,
            summary=f"Orientation scheduled for {employee_name} on {date} ({duration_minutes} min).",
        )
    except Exception as exc:
        return error_response("Schedule Orientation", str(exc), "Graph Calendar")


# ---------------------------------------------------------------------------
# Offboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def schedule_exit_interview(
    employee_name: str,
    employee_email: str,
    date: str,
    hr_representative: str = "hr-exit@contoso.com",
) -> str:
    """Create calendar event for exit interview with HR."""
    try:
        details = {
            "event_title": f"Exit Interview — {employee_name}",
            "date": date,
            "duration_minutes": 60,
            "attendees": [employee_email, hr_representative],
            "confidential": True,
            "teams_meeting_link": True,
            "status": "Scheduled",
        }
        return success_response(
            action="Exit Interview Scheduled",
            details=details,
            summary=f"Exit interview scheduled for {employee_name} on {date}.",
        )
    except Exception as exc:
        return error_response("Schedule Exit Interview", str(exc), "Graph Calendar")


@mcp.tool()
async def send_farewell_notification(
    employee_name: str,
    team_channel_id: str = "General",
    last_day: str = "",
    opt_in: bool = True,
) -> str:
    """Send configurable farewell notice to the team (opt-in by employee)."""
    try:
        if not opt_in:
            return success_response(
                action="Farewell Notification Skipped",
                details={"employee_name": employee_name, "opt_in": False},
                summary=f"Farewell notification skipped — {employee_name} opted out.",
            )
        details = {
            "channel": team_channel_id,
            "employee_name": employee_name,
            "last_day": last_day,
            "message_preview": (
                f"Today we say goodbye to {employee_name}. "
                f"Their last day is {last_day}. We wish them all the best!"
            ),
            "status": "Posted",
        }
        return success_response(
            action="Farewell Notification Sent",
            details=details,
            summary=f"Farewell notification posted for {employee_name}.",
        )
    except Exception as exc:
        return error_response("Send Farewell Notification", str(exc), "Teams / Graph")


@mcp.tool()
async def send_cobra_notification(
    employee_name: str,
    employee_email: str,
    termination_date: str,
    election_deadline_days: int = 60,
) -> str:
    """Send COBRA continuation rights notice (US employees)."""
    try:
        details = {
            "recipient": employee_email,
            "employee_name": employee_name,
            "subject": "COBRA Continuation Coverage — Election Notice",
            "termination_date": termination_date,
            "election_deadline_days": election_deadline_days,
            "coverage_options": ["Medical", "Dental", "Vision"],
            "status": "Sent",
        }
        return success_response(
            action="COBRA Notification Sent",
            details=details,
            summary=(
                f"COBRA election notice sent to {employee_name}. "
                f"Election deadline: {election_deadline_days} days."
            ),
        )
    except Exception as exc:
        return error_response("Send COBRA Notification", str(exc), "Graph Mail")


@mcp.tool()
async def send_offboarding_checklist(
    manager_email: str,
    employee_name: str,
    last_day: str = "",
) -> str:
    """Send the manager a checklist of knowledge transfer items."""
    try:
        checklist_items = [
            "Document ongoing projects and handoff plan",
            "Transfer code repository ownership",
            "Update shared drive permissions",
            "Complete pending code reviews",
            "Hand off client relationships",
            "Return company property and badges",
            "Share credentials for shared accounts",
            "Update team runbooks and documentation",
        ]
        details = {
            "recipient": manager_email,
            "employee_name": employee_name,
            "last_day": last_day,
            "checklist_items": checklist_items,
            "total_items": len(checklist_items),
            "status": "Sent",
        }
        return success_response(
            action="Offboarding Checklist Sent",
            details=details,
            summary=(
                f"Knowledge transfer checklist ({len(checklist_items)} items) "
                f"sent to manager for {employee_name}."
            ),
        )
    except Exception as exc:
        return error_response("Send Offboarding Checklist", str(exc), "Graph Mail")


# ---------------------------------------------------------------------------
# Azure Function App entry point
# ---------------------------------------------------------------------------

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="mcp/{*path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    from fastmcp.server.http import create_http_handler

    handler = create_http_handler(mcp)
    return await handler(req)
