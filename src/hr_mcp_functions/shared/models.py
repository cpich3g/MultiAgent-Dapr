"""Shared data models for HR MCP Function Apps."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EmploymentStatus(str, Enum):
    """SAP-aligned employment status codes."""

    PRE_HIRE = "pre_hire"
    ACTIVE = "active"
    ON_NOTICE = "on_notice"
    TERMINATED = "terminated"
    RETIRED = "retired"
    SUSPENDED = "suspended"


class TerminationType(str, Enum):
    """Classification of employment termination."""

    VOLUNTARY = "voluntary"
    INVOLUNTARY = "involuntary"
    RETIREMENT = "retirement"
    CONTRACT_END = "contract_end"


class ApprovalStatus(str, Enum):
    """Approval workflow states."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class AssetCondition(str, Enum):
    """Condition of returned assets."""

    GOOD = "good"
    DAMAGED = "damaged"
    MISSING = "missing"


# ---------------------------------------------------------------------------
# Employee models
# ---------------------------------------------------------------------------

class Employee(BaseModel):
    """Core employee record aligned with SAP SuccessFactors schema."""

    employee_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    first_name: str
    last_name: str
    email: Optional[str] = None
    upn: Optional[str] = None
    department: str = "General"
    role: str = "Individual Contributor"
    manager_email: Optional[str] = None
    manager_name: Optional[str] = None
    cost_center: Optional[str] = None
    location: str = "HQ"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    salary_band: Optional[str] = None
    status: EmploymentStatus = EmploymentStatus.PRE_HIRE
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TerminationRequest(BaseModel):
    """Termination request payload."""

    employee_id: str
    termination_type: TerminationType
    effective_date: str
    reason: str = ""
    manager_email: Optional[str] = None


# ---------------------------------------------------------------------------
# Tool response helpers
# ---------------------------------------------------------------------------

class ToolResponse(BaseModel):
    """Standardised tool response envelope."""

    success: bool
    action: str
    details: dict = Field(default_factory=dict)
    summary: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_success_str(self) -> str:
        """Serialise as a success string for MCP tool return."""
        return self.model_dump_json(indent=2)


def success_response(action: str, details: dict, summary: str) -> str:
    """Build a success response string."""
    return ToolResponse(
        success=True, action=action, details=details, summary=summary
    ).to_success_str()


def error_response(action: str, error_message: str, context: str = "") -> str:
    """Build an error response string."""
    return ToolResponse(
        success=False,
        action=action,
        details={"error": error_message, "context": context},
        summary=f"Error during {action}: {error_message}",
    ).to_success_str()
