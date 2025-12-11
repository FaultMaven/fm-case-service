"""API request and response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from fm_core_lib.models import Case, CaseStatus

from enum import Enum


class CasePriority(str, Enum):
    """Case priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseCreateRequest(BaseModel):
    """Request to create a new case."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(default="")
    priority: CasePriority = Field(default=CasePriority.MEDIUM)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CaseUpdateRequest(BaseModel):
    """Request to update a case."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[CaseStatus] = None
    priority: Optional[CasePriority] = None
    metadata: Optional[Dict[str, Any]] = None


class CaseStatusUpdateRequest(BaseModel):
    """Request to update case status."""

    status: CaseStatus


class CaseResponse(BaseModel):
    """Response containing a single case."""

    case_id: str
    owner_id: str
    user_id: str  # Internal services need this
    organization_id: str  # Internal services need this
    title: str
    description: str
    status: str
    priority: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    message_count: int = 0  # Default to 0, not Optional

    @classmethod
    def from_case(cls, case: Case) -> "CaseResponse":
        """Convert Case model to response."""
        priority = case.metadata.get("priority", "medium")

        # Filter out priority from metadata (it's exposed as top-level field)
        response_metadata = {k: v for k, v in case.metadata.items()
                           if k != "priority"}

        message_count = len(case.turn_history) if case.turn_history else 0

        return cls(
            case_id=case.case_id,
            owner_id=case.user_id,  # For frontend compatibility
            user_id=case.user_id,  # For internal services
            organization_id=case.organization_id,  # For internal services
            title=case.title,
            description=case.description,
            status=case.status.value,
            priority=priority,
            metadata=response_metadata,
            created_at=case.created_at,
            updated_at=case.updated_at,
            resolved_at=case.resolved_at,
            message_count=message_count,
        )


class CaseListResponse(BaseModel):
    """Response containing a list of cases."""

    cases: List[CaseResponse]
    total: int
    page: int
    page_size: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    database: str
