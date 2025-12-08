"""API request and response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from fm_core_lib.models import Case, CaseStatus

# Legacy enums for backward-compatible API (will be moved to metadata)
from enum import Enum


class CaseSeverity(str, Enum):
    """Legacy severity levels (stored in metadata)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseCategory(str, Enum):
    """Legacy category types (stored in metadata)."""
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
    session_id: Optional[str] = None  # Deprecated, kept for backward compatibility
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
        # Extract severity and category from metadata for backward compatibility
        severity = case.metadata.get("severity", "medium")
        category = case.metadata.get("category", "other")

        return cls(
            case_id=case.case_id,
            user_id=case.user_id,
            session_id=None,  # No longer used
            title=case.title,
            description=case.description,
            status=case.status.value,
            severity=severity,
            category=category,
            metadata=case.metadata,
            tags=[],  # fm-core-lib Case doesn't have top-level tags
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
