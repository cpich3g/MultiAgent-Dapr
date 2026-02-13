"""Payroll system API activity functions.

Each function wraps a single payroll system API call. Simulated in local
development; production calls SAP Payroll or ADP Workforce Now APIs.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def setup_payroll_record(
    employee_id: str,
    salary: str,
    pay_frequency: str,
    currency: str,
    tax_info: Dict[str, Any],
) -> Dict[str, Any]:
    """Create payroll record in the payroll system."""
    logger.info("Payroll API: Setting up payroll for %s", employee_id)
    return {
        "employee_id": employee_id,
        "payroll_id": f"PAY-{hash(employee_id) % 100000:05d}",
        "status": "active",
    }


async def enroll_in_benefits(
    employee_id: str,
    elections: Dict[str, str],
) -> Dict[str, Any]:
    """Submit benefits enrollment elections to the benefits provider."""
    logger.info("Benefits API: Enrolling %s in %d plans", employee_id, len(elections))
    return {
        "employee_id": employee_id,
        "enrollment_id": f"BEN-{hash(employee_id) % 100000:05d}",
        "plans": list(elections.keys()),
        "status": "enrolled",
    }


async def calculate_final_pay(
    employee_id: str,
    last_working_date: str,
    pto_hours: float,
    severance_eligible: bool,
) -> Dict[str, Any]:
    """Calculate final paycheck amounts through the payroll engine."""
    logger.info("Payroll API: Calculating final pay for %s", employee_id)
    hourly_rate = 55.00
    base = 4250.00
    pto_payout = round(pto_hours * hourly_rate, 2)
    severance = 10000.00 if severance_eligible else 0.0
    return {
        "employee_id": employee_id,
        "base": base,
        "pto_payout": pto_payout,
        "severance": severance,
        "total_gross": round(base + pto_payout + severance, 2),
    }


async def close_direct_deposit(employee_id: str) -> Dict[str, Any]:
    """Close direct deposit linkage after final disbursement."""
    logger.info("Payroll API: Closing direct deposit for %s", employee_id)
    return {"employee_id": employee_id, "direct_deposit": "closed"}


async def generate_tax_document(
    employee_id: str,
    tax_year: str,
    document_type: str = "W-2",
) -> Dict[str, Any]:
    """Generate year-end tax document (W-2 or equivalent)."""
    logger.info(
        "Payroll API: Generating %s for %s (year %s)",
        document_type, employee_id, tax_year,
    )
    return {
        "employee_id": employee_id,
        "document_type": document_type,
        "tax_year": tax_year,
        "document_id": f"TAX-{hash(f'{employee_id}{tax_year}') % 100000:05d}",
        "status": "generated",
    }
