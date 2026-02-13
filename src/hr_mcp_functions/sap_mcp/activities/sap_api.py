"""SAP SuccessFactors API activity functions.

Each function encapsulates a single SAP OData call.  In local development
these return simulated responses; in production they call the real SAP
SuccessFactors OData v2 / v4 endpoints via the SAP BTP Destination Service.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def create_employee_in_sap(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST /EmpEmployment to create a new employment record.

    Args:
        payload: Employee data aligned with SAP EC schema.

    Returns:
        SAP response with the created employee ID and status.
    """
    logger.info(
        "SAP API: Creating employee %s %s",
        payload.get("first_name"),
        payload.get("last_name"),
    )
    # Simulated response
    return {
        "d": {
            "personIdExternal": payload.get("employee_id", "EMP-00001"),
            "userId": payload.get("upn", "jsmith@contoso.com"),
            "status": "created",
        }
    }


async def get_employee_from_sap(employee_id: str) -> Dict[str, Any]:
    """GET /EmpEmployment('{employee_id}') to retrieve employee data.

    Args:
        employee_id: SAP employee external ID.

    Returns:
        Full employee profile from SAP EC.
    """
    logger.info("SAP API: Retrieving employee %s", employee_id)
    return {
        "d": {
            "personIdExternal": employee_id,
            "firstName": "Jessica",
            "lastName": "Smith",
            "department": "Engineering",
            "jobTitle": "Software Engineer",
            "employmentStatus": "active",
        }
    }


async def update_employment_status(
    employee_id: str,
    status: str,
    effective_date: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """PATCH /EmpEmployment to update employment status.

    Args:
        employee_id: SAP employee external ID.
        status: New status code.
        effective_date: ISO-8601 date string.
        reason: Optional termination reason code.

    Returns:
        SAP response confirming the status update.
    """
    logger.info(
        "SAP API: Updating employee %s status to %s", employee_id, status
    )
    return {
        "d": {
            "personIdExternal": employee_id,
            "employmentStatus": status,
            "effectiveDate": effective_date,
            "reason": reason,
        }
    }


async def get_org_unit(position_id: str) -> Dict[str, Any]:
    """GET /Position('{position_id}')/parentOrg to fetch org hierarchy.

    Args:
        position_id: SAP position ID.

    Returns:
        Org structure with reporting chain.
    """
    logger.info("SAP API: Fetching org structure for position %s", position_id)
    return {
        "d": {
            "positionId": position_id,
            "orgUnit": "OU-Engineering",
            "costCenter": "CC-2000",
            "parentPosition": "POS-MGR-001",
        }
    }


async def initiate_bgv(employee_id: str, check_type: str) -> Dict[str, Any]:
    """POST /BackgroundCheck to initiate a background verification.

    Args:
        employee_id: SAP employee external ID.
        check_type: Standard | Enhanced | Executive.

    Returns:
        BGV check ID and estimated completion time.
    """
    logger.info(
        "SAP API: Initiating %s background check for %s", check_type, employee_id
    )
    return {
        "checkId": f"BGV-{hash(f'{employee_id}{check_type}') % 100000:05d}",
        "status": "initiated",
        "estimatedDays": 5,
    }


async def poll_bgv(check_id: str) -> str:
    """GET /BackgroundCheck('{check_id}')/status to poll BGV status.

    Args:
        check_id: BGV check identifier.

    Returns:
        Status string: initiated | in_progress | completed | failed.
    """
    logger.info("SAP API: Polling BGV status for %s", check_id)
    return "completed"


async def calculate_settlement(
    employee_id: str,
    last_date: str,
    pto_hours: float,
    severance: bool,
) -> Dict[str, Any]:
    """Compute final settlement via SAP Payroll simulation.

    Args:
        employee_id: SAP employee external ID.
        last_date: Last working date (ISO-8601).
        pto_hours: Remaining PTO balance in hours.
        severance: Whether severance applies.

    Returns:
        Settlement breakdown with amounts.
    """
    logger.info("SAP API: Calculating final settlement for %s", employee_id)
    pto_payout = round(pto_hours * 55.0, 2)
    severance_amt = 10000.00 if severance else 0.0
    return {
        "employee_id": employee_id,
        "pto_payout": pto_payout,
        "severance": severance_amt,
        "final_gross": round(8500.00 + pto_payout + severance_amt, 2),
    }
