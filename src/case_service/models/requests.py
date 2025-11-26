"""API request and response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .case import Case, CaseStatus, CaseSeverity, CaseCategory


class CaseCreateRequest(BaseModel):
    """Request to create a new case."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(default="")
    session_id: Optional[str] = None
    severity: CaseSeverity = Field(default=CaseSeverity.MEDIUM)
    category: CaseCategory = Field(default=CaseCategory.OTHER)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class CaseUpdateRequest(BaseModel):
    """Request to update a case."""

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[CaseStatus] = None
    severity: Optional[CaseSeverity] = None
    category: Optional[CaseCategory] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class CaseStatusUpdateRequest(BaseModel):
    """Request to update case status."""

    status: CaseStatus


class CaseResponse(BaseModel):
    """Response containing a single case."""

    case_id: str
    user_id: str
    # NOTE: session_id removed - fm-core-lib Case model doesn't have this field
    # Sessions are for authentication only, not stored in cases
    title: str
    description: str
    status: str
    severity: str
    category: str
    metadata: Dict[str, Any]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]

    @classmethod
    def from_case(cls, case: Case) -> "CaseResponse":
        """Convert Case model to response."""
        return cls(
            case_id=case.case_id,
            user_id=case.user_id,
            # session_id removed - not in fm-core-lib Case model
            title=case.title,
            description=case.description,
            status=case.status.value,
            severity=case.severity.value,
            category=case.category.value,
            metadata=case.metadata,
            tags=case.tags,
            created_at=case.created_at,
            updated_at=case.updated_at,
            resolved_at=case.resolved_at,
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
