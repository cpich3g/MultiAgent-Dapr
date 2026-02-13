"""Payroll MCP Server — Azure Function App.

Manages compensation setup, benefits enrollment, final paycheck
processing, direct deposit, and tax document generation.
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

mcp = FastMCP("Payroll MCP Server")

# ---------------------------------------------------------------------------
# Onboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def setup_payroll(
    employee_name: str,
    employee_id: str,
    salary: str = "As per contract",
    pay_frequency: str = "Bi-weekly",
    currency: str = "USD",
    tax_filing_status: str = "Single",
    federal_allowances: int = 1,
    state: str = "WA",
) -> str:
    """Configure pay frequency, tax withholding, and direct deposit."""
    try:
        details = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "salary": salary,
            "pay_frequency": pay_frequency,
            "currency": currency,
            "tax_withholding": {
                "filing_status": tax_filing_status,
                "federal_allowances": federal_allowances,
                "state": state,
                "state_tax": "Exempt" if state == "WA" else "Standard",
            },
            "next_pay_date": "Next scheduled pay cycle",
            "status": "Payroll Setup Complete",
        }
        return success_response(
            action="Payroll Setup",
            details=details,
            summary=f"Payroll configured for {employee_name} ({pay_frequency}, {currency}).",
        )
    except Exception as exc:
        return error_response("Setup Payroll", str(exc), "Payroll System")


@mcp.tool()
async def enroll_benefits(
    employee_name: str,
    employee_id: str,
    medical_plan: str = "PPO Gold",
    dental_plan: str = "Dental Plus",
    vision_plan: str = "Vision Standard",
    life_insurance: str = "2x salary",
    retirement_contribution: str = "6%",
) -> str:
    """Initiate benefits enrollment window with plan options."""
    try:
        details = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "elections": {
                "medical": medical_plan,
                "dental": dental_plan,
                "vision": vision_plan,
                "life_insurance": life_insurance,
                "retirement_401k": retirement_contribution,
            },
            "enrollment_window": "30 days from start date",
            "effective_date": "First of month following start date",
            "status": "Enrollment Initiated",
        }
        return success_response(
            action="Benefits Enrollment Initiated",
            details=details,
            summary=(
                f"Benefits enrollment initiated for {employee_name}: "
                f"{medical_plan}, {dental_plan}, {vision_plan}, "
                f"401k at {retirement_contribution}."
            ),
        )
    except Exception as exc:
        return error_response("Enroll Benefits", str(exc), "Benefits System")


# ---------------------------------------------------------------------------
# Offboarding tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def process_final_paycheck(
    employee_id: str,
    employee_name: str,
    last_working_date: str,
    pto_payout_hours: float = 0.0,
    severance_eligible: bool = False,
    bonus_proration: bool = True,
) -> str:
    """Calculate and schedule final paycheck with PTO payout.

    Triggers a Durable Functions orchestrator for calculation, approval,
    and scheduled disbursement.
    """
    try:
        hourly_pto_rate = 55.00
        pto_amount = round(pto_payout_hours * hourly_pto_rate, 2)
        severance = 10000.00 if severance_eligible else 0.0
        prorated_bonus = 2500.00 if bonus_proration else 0.0
        base_final = 4250.00  # Half of bi-weekly pay
        total_gross = round(base_final + pto_amount + severance + prorated_bonus, 2)

        details = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "last_working_date": last_working_date,
            "breakdown": {
                "base_final_pay": base_final,
                "pto_payout": pto_amount,
                "pto_hours": pto_payout_hours,
                "severance": severance,
                "prorated_bonus": prorated_bonus,
            },
            "total_gross": total_gross,
            "payment_method": "Direct Deposit",
            "scheduled_date": "Next regular pay cycle",
            "status": "Calculated — Pending Disbursement",
        }
        return success_response(
            action="Final Paycheck Processed",
            details=details,
            summary=(
                f"Final paycheck for {employee_name}: gross ${total_gross} "
                f"(base ${base_final} + PTO ${pto_amount} + "
                f"severance ${severance} + bonus ${prorated_bonus})."
            ),
        )
    except Exception as exc:
        return error_response("Process Final Paycheck", str(exc), "Payroll System")


@mcp.tool()
async def terminate_direct_deposit(
    employee_id: str,
    employee_name: str,
) -> str:
    """Issue final deposit and close direct deposit linkage."""
    try:
        details = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "final_deposit_scheduled": True,
            "bank_linkage_closed": True,
            "paper_check_fallback": "Available upon request",
            "status": "Direct Deposit Terminated",
        }
        return success_response(
            action="Direct Deposit Terminated",
            details=details,
            summary=f"Direct deposit for {employee_name} terminated after final disbursement.",
        )
    except Exception as exc:
        return error_response("Terminate Direct Deposit", str(exc), "Payroll System")


@mcp.tool()
async def generate_tax_documents(
    employee_id: str,
    employee_name: str,
    tax_year: str = "2026",
    document_type: str = "W-2",
) -> str:
    """Trigger generation of final W-2 or regional equivalent.

    Triggers a Durable Functions orchestrator that generates and delivers
    the tax document via secure email.
    """
    try:
        details = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "tax_year": tax_year,
            "document_type": document_type,
            "delivery_method": "Secure email + Employee self-service portal",
            "estimated_delivery": "January of following tax year",
            "status": "Generation Queued",
        }
        return success_response(
            action="Tax Documents Queued",
            details=details,
            summary=(
                f"{document_type} generation queued for {employee_name} "
                f"(tax year {tax_year})."
            ),
        )
    except Exception as exc:
        return error_response("Generate Tax Documents", str(exc), "Payroll / Tax")


# ---------------------------------------------------------------------------
# Durable Functions orchestrators
# ---------------------------------------------------------------------------

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.orchestration_trigger(context_name="context")
def final_paycheck_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator: calculate, approve, and disburse final paycheck."""
    input_data = context.get_input()
    employee_id = input_data["employee_id"]

    # Step 1: Calculate final amounts
    calculation = yield context.call_activity("calculate_final_amounts", input_data)

    # Step 2: Request payroll manager approval
    yield context.call_activity("request_payroll_approval", {
        **input_data,
        "calculation": calculation,
    })

    # Step 3: Wait for approval (external event from Logic App)
    import datetime
    deadline = context.current_utc_datetime + datetime.timedelta(hours=48)
    approval = context.wait_for_external_event("PayrollApproval")
    timeout = context.create_timer(deadline)

    winner = yield context.task_any([approval, timeout])

    if winner == timeout:
        return {"employee_id": employee_id, "status": "approval_timed_out"}

    timeout.cancel()
    if approval.result.get("decision") != "approved":
        return {"employee_id": employee_id, "status": "rejected"}

    # Step 4: Schedule disbursement
    yield context.call_activity("schedule_disbursement", {
        **input_data,
        "calculation": calculation,
    })

    return {"employee_id": employee_id, "status": "disbursement_scheduled"}


@app.orchestration_trigger(context_name="context")
def tax_document_orchestrator(context: df.DurableOrchestrationContext):
    """Durable orchestrator: generate and deliver tax documents."""
    input_data = context.get_input()

    yield context.call_activity("generate_tax_doc", input_data)
    yield context.call_activity("deliver_tax_doc", input_data)

    return {"employee_id": input_data["employee_id"], "status": "delivered"}


@app.activity_trigger(input_name="data")
def calculate_final_amounts(data: dict) -> dict:
    logger.info("Calculating final amounts for %s", data.get("employee_id"))
    return {"base": 4250.00, "pto": 0.0, "severance": 0.0, "total": 4250.00}


@app.activity_trigger(input_name="data")
def request_payroll_approval(data: dict) -> str:
    logger.info("Requesting payroll approval for %s", data.get("employee_id"))
    return "approval_requested"


@app.activity_trigger(input_name="data")
def schedule_disbursement(data: dict) -> str:
    logger.info("Scheduling disbursement for %s", data.get("employee_id"))
    return "scheduled"


@app.activity_trigger(input_name="data")
def generate_tax_doc(data: dict) -> str:
    logger.info("Generating tax doc for %s", data.get("employee_id"))
    return "generated"


@app.activity_trigger(input_name="data")
def deliver_tax_doc(data: dict) -> str:
    logger.info("Delivering tax doc for %s", data.get("employee_id"))
    return "delivered"


# ---------------------------------------------------------------------------
# HTTP trigger
# ---------------------------------------------------------------------------


@app.route(route="mcp/{*path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mcp_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    from fastmcp.server.http import create_http_handler

    handler = create_http_handler(mcp)
    return await handler(req)
