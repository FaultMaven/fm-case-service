"""Case business logic manager - Repository Pattern."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fm_core_lib.models import Case, CaseStatus

from case_service.infrastructure.persistence import CaseRepository
from case_service.models import (
    CaseCreateRequest,
    CaseUpdateRequest,
)

logger = logging.getLogger(__name__)


class CaseManager:
    """Business logic for case management operations.

    This class implements the service layer using the Repository pattern.
    It handles business logic while delegating persistence to CaseRepository.
    """

    def __init__(self, repository: CaseRepository):
        """Initialize case manager with repository.

        Args:
            repository: CaseRepository implementation (InMemory, PostgreSQL, or Hybrid)
        """
        self.repository = repository

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
            Created case with generated ID
        """
        # Auto-generate title if not provided
        title = request.title
        if not title or not title.strip():
            # Generate title: Case-MMDD-N
            now = datetime.now(timezone.utc)
            date_suffix = now.strftime("%m%d")

            # Count today's cases for sequence number
            # TODO: Implement count_cases_by_user_today in repository
            sequence = 1
            title = f"Case-{date_suffix}-{sequence}"

        # Create Case domain model (from fm-core-lib)
        case = Case(
            case_id=f"case_{uuid4().hex[:12]}",
            user_id=user_id,
            organization_id="default",  # TODO: Get from user context
            title=title.strip(),
            description=request.description or "",
            status=CaseStatus.CONSULTING,  # Per design spec (not ACTIVE)
            current_turn=0,
            turns_without_progress=0,
            evidence=[],
            hypotheses={},
            solutions=[],
            uploaded_files=[],
            turn_history=[],
            status_history=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_activity_at=datetime.now(timezone.utc),
        )

        # Save via repository
        saved_case = await self.repository.save(case)

        logger.info(f"Created case {saved_case.case_id} for user {user_id}")

        return saved_case

    async def get_case(
        self,
        case_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Case]:
        """Get a case by ID with optional access control.

        Args:
            case_id: Case identifier
            user_id: Optional user ID for access control

        Returns:
            Case if found and accessible, None otherwise
        """
        case = await self.repository.get(case_id)

        if not case:
            return None

        # Access control: users can only see their own cases
        if user_id and case.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to access case {case_id} "
                f"owned by {case.user_id}"
            )
            return None

        return case

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
            Updated case or None if not found/unauthorized
        """
        # Get case with authorization check
        case = await self.get_case(case_id, user_id)
        if not case:
            return None

        # Apply updates
        if request.title is not None:
            case.title = request.title.strip()
        if request.description is not None:
            case.description = request.description
        if request.status is not None:
            case.status = request.status
            if request.status in [CaseStatus.RESOLVED, CaseStatus.CLOSED]:
                case.resolved_at = datetime.now(timezone.utc)
                case.closed_at = datetime.now(timezone.utc)

        # Update metadata
        if hasattr(request, 'metadata') and request.metadata is not None:
            # Store in consulting data or custom field
            # TODO: Map to proper Case fields based on design
            pass

        if hasattr(request, 'tags') and request.tags is not None:
            # TODO: Map to proper Case fields
            pass

        case.updated_at = datetime.now(timezone.utc)
        case.last_activity_at = datetime.now(timezone.utc)

        # Save via repository
        updated_case = await self.repository.save(case)

        logger.info(f"Updated case {case_id}")

        return updated_case

    async def delete_case(self, case_id: str, user_id: str) -> bool:
        """Delete a case.

        Args:
            case_id: Case identifier
            user_id: User ID for authorization

        Returns:
            True if deleted, False if not found/unauthorized
        """
        # Check authorization first
        case = await self.get_case(case_id, user_id)
        if not case:
            return False

        # Delete via repository
        deleted = await self.repository.delete(case_id)

        if deleted:
            logger.info(f"Deleted case {case_id}")

        return deleted

    async def list_cases(
        self,
        user_id: str,
        status: Optional[CaseStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[Case], int]:
        """List cases for a user.

        Args:
            user_id: User ID to filter by
            status: Optional status filter
            limit: Maximum number of cases to return
            offset: Offset for pagination

        Returns:
            Tuple of (cases, total_count)
        """
        # Use repository list method
        cases, total = await self.repository.list(
            user_id=user_id,
            status=status.value if status else None,
            limit=limit,
            offset=offset,
        )

        return cases, total

    async def get_cases_by_session(self, session_id: str) -> List[Case]:
        """Get all cases for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of cases for the session
        """
        # TODO: Add session_id filter to repository.list()
        # For now, get all cases and filter in memory
        all_cases, _ = await self.repository.list(limit=1000)

        # Filter by session_id (stored in consulting data or as field)
        session_cases = []
        for case in all_cases:
            # TODO: Check proper field based on design
            # if case.consulting and case.consulting.session_id == session_id:
            #     session_cases.append(case)
            pass

        return session_cases
