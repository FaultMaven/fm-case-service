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


class CaseCategory(str, Enum):
    """Case category types."""
    PERFORMANCE = "performance"
    ERROR = "error"
    CONFIGURATION = "configuration"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    OTHER = "other"


class CaseCreateRequest(BaseModel):
    """Request to create a new case."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(default="")
    priority: CasePriority = Field(default=CasePriority.MEDIUM)
    category: CaseCategory = Field(default=CaseCategory.OTHER)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    initial_message: Optional[str] = None


class CaseUpdateRequest(BaseModel):
    """Request to update a case."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[CaseStatus] = None
    priority: Optional[CasePriority] = None
    category: Optional[CaseCategory] = None
    metadata: Optional[Dict[str, Any]] = None


class CaseStatusUpdateRequest(BaseModel):
    """Request to update case status."""

    status: CaseStatus


class CaseResponse(BaseModel):
    """Response containing a single case."""

    case_id: str
    owner_id: str
    title: str
    description: str
    status: str
    priority: Optional[str] = None
    category: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    message_count: Optional[int] = None

    @classmethod
    def from_case(cls, case: Case) -> "CaseResponse":
        """Convert Case model to response."""
        priority = case.metadata.get("priority", "medium")
        category = case.metadata.get("category", "other")

        # Filter out priority and category from metadata
        response_metadata = {k: v for k, v in case.metadata.items()
                           if k not in ("priority", "category")}

        message_count = len(case.turn_history) if case.turn_history else None

        return cls(
            case_id=case.case_id,
            owner_id=case.user_id,
            title=case.title,
            description=case.description,
            status=case.status.value,
            priority=priority,
            category=category,
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
