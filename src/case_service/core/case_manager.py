"""Case business logic manager."""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from case_service.infrastructure.database.models import CaseDB
from case_service.models import (
    Case,
    CaseStatus,
    CaseSeverity,
    CaseCategory,
    CaseCreateRequest,
    CaseUpdateRequest,
)

logger = logging.getLogger(__name__)


class CaseManager:
    """Business logic for case management operations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize case manager with database session.

        Args:
            db_session: SQLAlchemy async session
        """
        self.db = db_session

    async def create_case(
        self,
        user_id: str,
        request: CaseCreateRequest,
    ) -> Case:
        """Create a new case.

        Args:
            user_id: User ID from gateway headers
            request: Case creation request

        Returns:
            Created case
        """
        # Auto-generate title if not provided
        title = request.title
        if not title or not title.strip():
            now = datetime.now(timezone.utc)
            date_suffix = now.strftime("%m%d")

            # Count today's cases for sequence number
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = select(func.count()).select_from(CaseDB).where(
                and_(
                    CaseDB.user_id == user_id,
                    CaseDB.created_at >= today_start
                )
            )
            result = await self.db.execute(stmt)
            today_count = result.scalar() or 0

            sequence = today_count + 1
            title = f"Case-{date_suffix}-{sequence}"

        # Create database record
        db_case = CaseDB(
            case_id=f"case_{uuid4().hex[:12]}",
            user_id=user_id,
            session_id=request.session_id,
            title=title.strip(),
            description=request.description,
            status=CaseStatus.ACTIVE,
            severity=request.severity,
            category=request.category,
            case_metadata=request.metadata,
            tags=request.tags,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.db.add(db_case)
        await self.db.commit()
        await self.db.refresh(db_case)

        logger.info(f"Created case {db_case.case_id} for user {user_id}")

        return self._to_domain_model(db_case)

    async def get_case(self, case_id: str, user_id: Optional[str] = None) -> Optional[Case]:
        """Get a case by ID with optional access control.

        Args:
            case_id: Case identifier
            user_id: Optional user ID for access control

        Returns:
            Case if found and accessible, None otherwise
        """
        stmt = select(CaseDB).where(CaseDB.case_id == case_id)

        if user_id:
            stmt = stmt.where(CaseDB.user_id == user_id)

        result = await self.db.execute(stmt)
        db_case = result.scalar_one_or_none()

        if not db_case:
            return None

        return self._to_domain_model(db_case)

    async def update_case(
        self,
        case_id: str,
        user_id: str,
        request: CaseUpdateRequest,
    ) -> Optional[Case]:
        """Update a case.

        Args:
            case_id: Case identifier
            user_id: User ID for authorization
            request: Update request

        Returns:
            Updated case or None if not found
        """
        # Get case with authorization check
        stmt = select(CaseDB).where(
            and_(
                CaseDB.case_id == case_id,
                CaseDB.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        db_case = result.scalar_one_or_none()

        if not db_case:
            return None

        # Apply updates
        if request.title is not None:
            db_case.title = request.title.strip()
        if request.description is not None:
            db_case.description = request.description
        if request.status is not None:
            db_case.status = request.status
            if request.status in [CaseStatus.RESOLVED, CaseStatus.CLOSED]:
                db_case.resolved_at = datetime.now(timezone.utc)
        if request.severity is not None:
            db_case.severity = request.severity
        if request.category is not None:
            db_case.category = request.category
        if request.metadata is not None:
            db_case.case_metadata = request.metadata
        if request.tags is not None:
            db_case.tags = request.tags

        db_case.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(db_case)

        logger.info(f"Updated case {case_id}")

        return self._to_domain_model(db_case)

    async def delete_case(self, case_id: str, user_id: str) -> bool:
        """Delete a case.

        Args:
            case_id: Case identifier
            user_id: User ID for authorization

        Returns:
            True if deleted, False if not found
        """
        stmt = select(CaseDB).where(
            and_(
                CaseDB.case_id == case_id,
                CaseDB.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        db_case = result.scalar_one_or_none()

        if not db_case:
            return False

        await self.db.delete(db_case)
        await self.db.commit()

        logger.info(f"Deleted case {case_id}")

        return True

    async def list_cases(
        self,
        user_id: str,
        status: Optional[CaseStatus] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[Case], int]:
        """List cases for a user.

        Args:
            user_id: User ID
            status: Optional status filter
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (cases, total_count)
        """
        # Build query
        stmt = select(CaseDB).where(CaseDB.user_id == user_id)

        if status:
            stmt = stmt.where(CaseDB.status == status)

        # Count total
        count_stmt = select(func.count()).select_from(CaseDB).where(CaseDB.user_id == user_id)
        if status:
            count_stmt = count_stmt.where(CaseDB.status == status)

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated results
        stmt = stmt.order_by(CaseDB.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        db_cases = result.scalars().all()

        cases = [self._to_domain_model(db_case) for db_case in db_cases]

        return cases, total

    async def list_cases_by_session(
        self,
        session_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[Case], int]:
        """List cases for a session.

        Args:
            session_id: Session ID
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (cases, total_count)
        """
        # Build query
        stmt = select(CaseDB).where(CaseDB.session_id == session_id)

        # Count total
        count_stmt = select(func.count()).select_from(CaseDB).where(
            CaseDB.session_id == session_id
        )

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get paginated results
        stmt = stmt.order_by(CaseDB.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        db_cases = result.scalars().all()

        cases = [self._to_domain_model(db_case) for db_case in db_cases]

        return cases, total

    async def update_status(
        self,
        case_id: str,
        user_id: str,
        status: CaseStatus,
    ) -> Optional[Case]:
        """Update case status.

        Args:
            case_id: Case identifier
            user_id: User ID for authorization
            status: New status

        Returns:
            Updated case or None if not found
        """
        stmt = select(CaseDB).where(
            and_(
                CaseDB.case_id == case_id,
                CaseDB.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        db_case = result.scalar_one_or_none()

        if not db_case:
            return None

        db_case.status = status
        db_case.updated_at = datetime.now(timezone.utc)

        if status in [CaseStatus.RESOLVED, CaseStatus.CLOSED]:
            db_case.resolved_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(db_case)

        logger.info(f"Updated case {case_id} status to {status.value}")

        return self._to_domain_model(db_case)

    def _to_domain_model(self, db_case: CaseDB) -> Case:
        """Convert database model to domain model.

        Args:
            db_case: SQLAlchemy model instance

        Returns:
            Pydantic domain model
        """
        return Case(
            case_id=db_case.case_id,
            user_id=db_case.user_id,
            session_id=db_case.session_id,
            title=db_case.title,
            description=db_case.description,
            status=db_case.status,
            severity=db_case.severity,
            category=db_case.category,
            metadata=db_case.case_metadata or {},
            tags=db_case.tags or [],
            created_at=db_case.created_at,
            updated_at=db_case.updated_at,
            resolved_at=db_case.resolved_at,
        )
