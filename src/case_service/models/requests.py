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
    """Request to create a new case.

    Supports both frontend (priority) and backend (severity) field names.
    Frontend sends: title, priority, metadata, initial_message
    """

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(default="")
    session_id: Optional[str] = None
    priority: Optional[CaseSeverity] = None  # Frontend uses priority
    severity: Optional[CaseSeverity] = None  # Legacy backend field
    category: CaseCategory = Field(default=CaseCategory.OTHER)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    initial_message: Optional[str] = None  # Frontend sends initial query message

    @property
    def effective_severity(self) -> CaseSeverity:
        """Get effective severity, preferring priority over severity."""
        return self.priority or self.severity or CaseSeverity.MEDIUM


class CaseUpdateRequest(BaseModel):
    """Request to update a case.

    Supports both frontend (priority) and backend (severity) field names.
    """

    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[CaseStatus] = None
    priority: Optional[CaseSeverity] = None  # Frontend uses priority
    severity: Optional[CaseSeverity] = None  # Legacy backend field
    category: Optional[CaseCategory] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

    @property
    def effective_severity(self) -> Optional[CaseSeverity]:
        """Get effective severity, preferring priority over severity."""
        return self.priority or self.severity


class CaseStatusUpdateRequest(BaseModel):
    """Request to update case status."""

    status: CaseStatus


class CaseResponse(BaseModel):
    """Response containing a single case.

    Matches frontend UserCase interface expectations:
    - owner_id: Required field (mapped from user_id)
    - priority: Optional field (mapped from severity in metadata)
    - message_count: Optional field (number of turns)
    """

    case_id: str
    owner_id: str  # Frontend expects owner_id (mapped from user_id)
    session_id: Optional[str] = None  # Deprecated, kept for backward compatibility
    title: str
    description: str
    status: str
    priority: Optional[str] = None  # Frontend uses priority (mapped from severity)
    severity: Optional[str] = None  # Legacy field for backward compatibility
    category: Optional[str] = None  # Legacy field for backward compatibility
    metadata: Dict[str, Any]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    message_count: Optional[int] = None  # Number of messages/turns in the case

    @classmethod
    def from_case(cls, case: Case) -> "CaseResponse":
        """Convert Case model to response."""
        # Extract severity and category from metadata field
        # Provide defaults for backward compatibility
        severity = case.metadata.get("severity", "medium")
        category = case.metadata.get("category", "other")

        # Filter out severity and category from metadata for API response
        # to avoid duplication (they're exposed as top-level fields)
        response_metadata = {k: v for k, v in case.metadata.items()
                           if k not in ("severity", "category")}

        # Calculate message count from turn history
        message_count = len(case.turn_history) if case.turn_history else None

        return cls(
            case_id=case.case_id,
            owner_id=case.user_id,  # Map user_id to owner_id for frontend
            session_id=None,  # No longer used
            title=case.title,
            description=case.description,
            status=case.status.value,
            priority=severity,  # Map severity to priority for frontend
            severity=severity,  # Keep for backward compatibility
            category=category,
            metadata=response_metadata,
            tags=[],  # fm-core-lib Case doesn't have top-level tags
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
