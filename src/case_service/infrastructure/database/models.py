"""SQLAlchemy database models."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Enum, String, Text
from sqlalchemy.ext.declarative import declarative_base

from case_service.models.case import CaseStatus, CaseSeverity, CaseCategory

Base = declarative_base()


class CaseDB(Base):
    """SQLAlchemy model for cases table."""

    __tablename__ = "cases"

    case_id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), nullable=True, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")

    status = Column(
        Enum(CaseStatus),
        nullable=False,
        default=CaseStatus.ACTIVE,
        index=True,
    )
    severity = Column(
        Enum(CaseSeverity),
        nullable=False,
        default=CaseSeverity.MEDIUM,
    )
    category = Column(
        Enum(CaseCategory),
        nullable=False,
        default=CaseCategory.OTHER,
    )

    case_metadata = Column("metadata", JSON, nullable=False, default=dict)
    tags = Column(JSON, nullable=False, default=list)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
