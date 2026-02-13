"""SAP SuccessFactors MCP Server — Azure Function App.

Exposes employee master record operations, background checks, benefits
management, and final settlement tools through the FastMCP protocol
over an Azure Functions HTTP trigger.
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
    EmploymentStatus,
    error_response,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("SAP SuccessFactors MCP Server")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def create_employee_record(
    first_name: str,
    last_name: str,
    department: str,
    role: str,
    manager_email: str,
    start_date: str,
    cost_center: str = "CC-1000",
    location: str = "HQ",
    salary_band: str = "L5",
) -> str:
    """Create a new employee master record in SAP SuccessFactors.

    Provisions personal data, org assignment, job info, and initial
    compensation in the SAP Employment Central module.
    """
    try:
        employee_id = f"EMP-{hash(f'{first_name}{last_name}{start_date}') % 100000:05d}"
        details = {
            "employee_id": employee_id,
            "first_name": first_name,
            "last_name": last_name,
            "department": department,
            "role": role,
            "manager_email": manager_email,
            "start_date": start_date,
            "cost_center": cost_center,
            "location": location,
            "salary_band": salary_band,
            "sap_status": EmploymentStatus.PRE_HIRE.value,
            "company_id": config.sap_company_id,
        }
        return success_response(
            action="Employee Record Created",
            details=details,
            summary=(
                f"Employee record created for {first_name} {last_name} "
                f"(ID: {employee_id}) in SAP SuccessFactors."
            ),
        )
    except Exception as exc:
        return error_response("Create Employee Record", str(exc), "SAP EC")


@mcp.tool()
async def get_employee_by_id(employee_id: str) -> str:
    """Retrieve the full employee profile from SAP SuccessFactors."""
    try:
        details = {
            "employee_id": employee_id,
            "first_name": "Jessica",
            "last_name": "Smith",
            "department": "Engineering",
            "role": "Software Engineer",
            "status": EmploymentStatus.ACTIVE.value,
            "cost_center": "CC-2000",
            "location": "Redmond",
            "manager_email": "manager@contoso.com",
            "company_id": config.sap_company_id,
        }
        return success_response(
            action="Employee Retrieved",
            details=details,
            summary=f"Retrieved employee profile for {employee_id}.",
        )
    except Exception as exc:
        return error_response("Get Employee", str(exc), "SAP EC")


@mcp.tool()
async def update_employee_status(
    employee_id: str,
    new_status: str,
    effective_date: str,
    reason: str = "",
) -> str:
    """Update employment status in SAP (e.g. Active, On Notice, Terminated)."""
    try:
        details = {
            "employee_id": employee_id,
            "previous_status": "active",
            "new_status": new_status,
            "effective_date": effective_date,
            "reason": reason,
        }
        return success_response(
            action="Employee Status Updated",
            details=details,
            summary=(
                f"Employee {employee_id} status changed to '{new_status}' "
                f"effective {effective_date}."
            ),
        )
    except Exception as exc:
        return error_response("Update Employee Status", str(exc), "SAP EC")


@mcp.tool()
async def get_org_structure(position_id: str) -> str:
    """Return reporting hierarchy, cost center, and org unit for a position."""
    try:
        details = {
            "position_id": position_id,
            "org_unit": "OU-Engineering",
            "cost_center": "CC-2000",
            "reporting_chain": [
                {"level": 1, "name": "Jane Manager", "position": "Engineering Manager"},
                {"level": 2, "name": "John Director", "position": "Engineering Director"},
                {"level": 3, "name": "Alice VP", "position": "VP Engineering"},
            ],
        }
        return success_response(
            action="Org Structure Retrieved",
            details=details,
            summary=f"Retrieved org structure for position {position_id}.",
        )
    except Exception as exc:
        return error_response("Get Org Structure", str(exc), "SAP EC")


@mcp.tool()
async def initiate_background_check(
    employee_id: str,
    employee_name: str,
    check_type: str = "Standard",
) -> str:
    """Trigger SAP Background Verification integration.

    Returns a check ID. In production this triggers a Durable Functions
    orchestrator that polls SAP for completion status.
    """
    try:
        check_id = f"BGV-{hash(f'{employee_id}{check_type}') % 100000:05d}"
        details = {
            "check_id": check_id,
            "employee_id": employee_id,
            "employee_name": employee_name,
            "check_type": check_type,
            "estimated_completion": "3-5 business days",
            "status": "Initiated",
        }
        return success_response(
            action="Background Check Initiated",
            details=details,
            summary=(
                f"Background check {check_id} initiated for {employee_name} "
                f"({check_type}). Estimated completion: 3-5 business days."
            ),
        )
    except Exception as exc:
        return error_response("Initiate Background Check", str(exc), "SAP BGV")


@mcp.tool()
async def calculate_final_settlement(
    employee_id: str,
    last_working_date: str,
    pto_balance_hours: float = 0.0,
    severance_eligible: bool = False,
) -> str:
    """Compute final paycheck, PTO payout, and severance per company policy."""
    try:
        pto_payout = round(pto_balance_hours * 55.0, 2)  # Simulated rate
        severance = 10000.00 if severance_eligible else 0.0
        details = {
            "employee_id": employee_id,
            "last_working_date": last_working_date,
            "pto_balance_hours": pto_balance_hours,
            "pto_payout_amount": pto_payout,
            "severance_amount": severance,
            "final_gross": round(8500.00 + pto_payout + severance, 2),
            "currency": "USD",
            "status": "Calculated",
        }
        return success_response(
            action="Final Settlement Calculated",
            details=details,
            summary=(
                f"Final settlement for {employee_id}: "
                f"PTO payout ${pto_payout}, severance ${severance}, "
                f"total gross ${details['final_gross']}."
            ),
        )
    except Exception as exc:
        return error_response("Calculate Final Settlement", str(exc), "SAP Payroll")


@mcp.tool()
async def get_benefits_enrollment(employee_id: str) -> str:
    """Retrieve current benefits elections for an employee from SAP."""
    try:
        details = {
            "employee_id": employee_id,
            "medical": {"plan": "PPO Gold", "coverage": "Employee + Family"},
            "dental": {"plan": "Dental Plus", "coverage": "Employee + Spouse"},
            "vision": {"plan": "Vision Standard", "coverage": "Employee Only"},
            "life_insurance": {"coverage": "2x salary"},
            "401k_contribution": "8%",
            "status": "Active",
        }
        return success_response(
            action="Benefits Enrollment Retrieved",
            details=details,
            summary=f"Retrieved benefits enrollment for {employee_id}.",
        )
    except Exception as exc:
        return error_response("Get Benefits Enrollment", str(exc), "SAP Benefits")


@mcp.tool()
async def terminate_benefits(
    employee_id: str,
    termination_date: str,
    cobra_eligible: bool = True,
) -> str:
    """Schedule COBRA notification and set benefit end dates in SAP.

    In production this triggers a Durable Functions orchestrator that
    manages the COBRA notification timeline (60-day election window).
    """
    try:
        details = {
            "employee_id": employee_id,
            "termination_date": termination_date,
            "benefits_end_date": termination_date,
            "cobra_eligible": cobra_eligible,
            "cobra_election_deadline": "60 days from notification",
            "cobra_notification_status": "Scheduled" if cobra_eligible else "N/A",
            "status": "Benefits Termination Scheduled",
        }
        return success_response(
            action="Benefits Terminated",
            details=details,
            summary=(
                f"Benefits termination scheduled for {employee_id} "
                f"effective {termination_date}. "
                f"COBRA notification {'scheduled' if cobra_eligible else 'not applicable'}."
            ),
        )
    except Exception as exc:
        return error_response("Terminate Benefits", str(exc), "SAP Benefits")


@mcp.tool()
async def create_position_requisition(
    employee_id: str,
    position_title: str,
    department: str,
    justification: str = "Backfill for departing employee",
) -> str:
    """Open a backfill requisition in SAP Recruiting for the departing employee's position."""
    try:
        req_id = f"REQ-{hash(f'{employee_id}{position_title}') % 100000:05d}"
        details = {
            "requisition_id": req_id,
            "source_employee_id": employee_id,
            "position_title": position_title,
            "department": department,
            "justification": justification,
            "status": "Open",
            "approval_required": True,
        }
        return success_response(
            action="Position Requisition Created",
            details=details,
            summary=(
                f"Backfill requisition {req_id} opened for '{position_title}' "
                f"in {department}."
            ),
        )
    except Exception as exc:
        return error_response("Create Position Requisition", str(exc), "SAP Recruiting")


# ---------------------------------------------------------------------------
# Durable Functions orchestrators
# ---------------------------------------------------------------------------

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.orchestration_trigger(context_name="context")
def background_check_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator that polls SAP BGV status until completion."""
    import datetime

    input_data = context.get_input()
    check_id = input_data["check_id"]

    # Poll every 4 hours, timeout after 7 days
    expiry = context.current_utc_datetime + datetime.timedelta(days=7)

    while context.current_utc_datetime < expiry:
        status = yield context.call_activity("poll_bgv_status", check_id)
        if status in ("completed", "failed"):
            return {"check_id": check_id, "result": status}

        next_check = context.current_utc_datetime + datetime.timedelta(hours=4)
        yield context.create_timer(next_check)

    return {"check_id": check_id, "result": "timed_out"}


@app.activity_trigger(input_name="checkId")
def poll_bgv_status(checkId: str) -> str:
    """Activity: poll SAP BGV API for check status."""
    # Simulated — real implementation calls SAP BGV API
    logger.info("Polling BGV status for %s", checkId)
    return "completed"


@app.orchestration_trigger(context_name="context")
def benefits_termination_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator for COBRA notification timeline."""
    import datetime

    input_data = context.get_input()
    employee_id = input_data["employee_id"]

    # Step 1: Send initial COBRA notification
    yield context.call_activity("send_cobra_notice", input_data)

    # Step 2: Wait 44 days, then send reminder
    reminder_date = context.current_utc_datetime + datetime.timedelta(days=44)
    yield context.create_timer(reminder_date)
    yield context.call_activity("send_cobra_reminder", input_data)

    # Step 3: Wait until day 60 election deadline
    deadline = context.current_utc_datetime + datetime.timedelta(days=16)
    election_event = context.wait_for_external_event("CobraElectionResponse")
    timeout_event = context.create_timer(deadline)

    winner = yield context.task_any([election_event, timeout_event])

    if winner == timeout_event:
        return {"employee_id": employee_id, "cobra": "election_expired"}
    else:
        timeout_event.cancel()
        return {"employee_id": employee_id, "cobra": election_event.result}


@app.activity_trigger(input_name="data")
def send_cobra_notice(data: dict) -> str:
    """Activity: send initial COBRA election notice."""
    logger.info("Sending COBRA notice for %s", data.get("employee_id"))
    return "sent"


@app.activity_trigger(input_name="data")
def send_cobra_reminder(data: dict) -> str:
    """Activity: send COBRA election reminder at day 44."""
    logger.info("Sending COBRA reminder for %s", data.get("employee_id"))
    return "sent"


# ---------------------------------------------------------------------------
# HTTP trigger — serves MCP over streamable-http
# ---------------------------------------------------------------------------

@app.route(route="mcp/{*path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function HTTP trigger that proxies requests to the FastMCP server."""
    from fastmcp.server.http import create_http_handler

    handler = create_http_handler(mcp)
    return await handler(req)
