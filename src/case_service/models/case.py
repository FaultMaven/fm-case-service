"""Case data models for fm-case-service.

Simplified version of FaultMaven case models for microservice deployment.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class CaseStatus(str, Enum):
    """Case lifecycle status."""

    ACTIVE = "active"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    ARCHIVED = "archived"
    CLOSED = "closed"


class CaseSeverity(str, Enum):
    """Case severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseCategory(str, Enum):
    """Case categories."""

    PERFORMANCE = "performance"
    ERROR = "error"
    CONFIGURATION = "configuration"
    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    OTHER = "other"


class Case(BaseModel):
    """Case domain model."""

    case_id: str = Field(default_factory=lambda: f"case_{uuid4().hex[:12]}")
    user_id: str = Field(description="Owner user ID")
    session_id: Optional[str] = Field(default=None, description="Associated session ID")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="")

    status: CaseStatus = Field(default=CaseStatus.ACTIVE)
    severity: CaseSeverity = Field(default=CaseSeverity.MEDIUM)
    category: CaseCategory = Field(default=CaseCategory.OTHER)

    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True
