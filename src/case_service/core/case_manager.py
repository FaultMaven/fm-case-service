"""Case business logic manager - Repository Pattern."""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
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

        # Prepare metadata with priority and category
        metadata = request.metadata.copy()
        metadata["priority"] = request.priority.value
        metadata["category"] = request.category.value

        # Create Case using fm-core-lib model
        case = Case(
            case_id=f"case_{uuid4().hex[:12]}",
            user_id=user_id,
            organization_id="default",  # TODO: Extract from X-Organization-Id header when available
            title=title.strip(),
            description=request.description or "",
            status=CaseStatus.CONSULTING,  # Start in consulting phase
            metadata=metadata,
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

    # =========================================================================
    # Phase 4: Evidence and Data Management
    # =========================================================================

    async def add_evidence(
        self, case_id: str, user_id: str, evidence_data: dict
    ) -> Optional[Case]:
        """Add evidence to a case."""
        case = await self.repository.get(case_id)
        if not case or case.user_id != user_id:
            return None

        # Create evidence object from dict and append to case
        from fm_core_lib.models import Evidence
        from datetime import datetime, timezone
        from uuid import uuid4

        evidence = Evidence(
            evidence_id=f"evidence_{uuid4().hex[:12]}",
            content=evidence_data.get("content", ""),
            source=evidence_data.get("source", "user"),
            category=evidence_data.get("category", "observation"),
            collected_at=datetime.now(timezone.utc),
        )
        case.evidence.append(evidence)
        return await self.repository.save(case)

    async def get_evidence(
        self, case_id: str, evidence_id: str, user_id: str
    ) -> Optional[dict]:
        """Get specific evidence from a case."""
        case = await self.repository.get(case_id)
        if not case or case.user_id != user_id:
            return None

        for evidence in case.evidence:
            if evidence.evidence_id == evidence_id:
                return evidence.model_dump()
        return None

    async def get_uploaded_files(
        self, case_id: str, user_id: str
    ) -> Optional[list]:
        """Get uploaded files for a case."""
        case = await self.repository.get(case_id)
        if not case or case.user_id != user_id:
            return None

        return [f.model_dump() for f in case.uploaded_files]

    async def close_case(
        self, case_id: str, user_id: str, close_data: Optional[dict] = None
    ) -> Optional[Case]:
        """Close a case."""
        from fm_core_lib.models import CaseStatus
        from datetime import datetime, timezone

        case = await self.repository.get(case_id)
        if not case or case.user_id != user_id:
            return None

        case.status = CaseStatus.CLOSED
        case.updated_at = datetime.now(timezone.utc)

        if close_data:
            # Store close metadata in metadata field
            if "reason" in close_data:
                case.metadata["close_reason"] = close_data["reason"]
            if "resolution_notes" in close_data:
                case.metadata["resolution_notes"] = close_data["resolution_notes"]

        return await self.repository.save(case)

    async def search_cases(
        self, user_id: str, search_params: dict
    ) -> Tuple[List[Case], int]:
        """Search cases with filters."""
        # For now, implement basic search using list endpoint
        # TODO: Implement full-text search when needed
        all_cases = await self.repository.list(
            user_id=user_id,
            limit=search_params.get("limit", 100)
        )

        # Apply basic filters
        filtered = all_cases
        if "query" in search_params:
            query = search_params["query"].lower()
            filtered = [
                c for c in filtered
                if query in c.title.lower() or query in c.description.lower()
            ]

        if "status" in search_params:
            statuses = search_params["status"]
            filtered = [c for c in filtered if c.status.value in statuses]

        if "severity" in search_params:
            severities = search_params["severity"]
            filtered = [c for c in filtered if c.severity in severities]

        return filtered, len(filtered)

    # =========================================================================
    # Phase 6.3: Hypothesis Management
    # =========================================================================

    async def add_hypothesis(
        self, case_id: str, user_id: str, hypothesis_data: dict
    ) -> Optional[Case]:
        """Add hypothesis to case."""
        case = await self.repository.get(case_id)
        if not case or case.user_id != user_id:
            return None

        from fm_core_lib.models import Hypothesis, HypothesisStatus
        from datetime import datetime, timezone
        from uuid import uuid4

        hypothesis = Hypothesis(
            hypothesis_id=f"hypothesis_{uuid4().hex[:12]}",
            description=hypothesis_data.get("description", ""),
            category=hypothesis_data.get("category", "root_cause"),
            status=HypothesisStatus.PROPOSED,
            confidence=hypothesis_data.get("confidence", 0.5),
            generated_at=datetime.now(timezone.utc),
        )
        
        # Add to case hypotheses dict
        case.hypotheses[hypothesis.hypothesis_id] = hypothesis
        return await self.repository.save(case)

    async def update_hypothesis(
        self, case_id: str, hypothesis_id: str, user_id: str, updates: dict
    ) -> Optional[dict]:
        """Update existing hypothesis."""
        case = await self.repository.get(case_id)
        if not case or case.user_id != user_id:
            return None

        if hypothesis_id not in case.hypotheses:
            return None

        hypothesis = case.hypotheses[hypothesis_id]
        
        # Update fields
        if "status" in updates:
            from fm_core_lib.models import HypothesisStatus
            hypothesis.status = HypothesisStatus(updates["status"])
        if "confidence" in updates:
            hypothesis.confidence = updates["confidence"]
        if "validation_notes" in updates:
            hypothesis.validation_notes = updates["validation_notes"]

        await self.repository.save(case)
        return hypothesis.model_dump()

    async def get_case_queries(
        self, case_id: str, user_id: str
    ) -> Optional[list]:
        """Get query history for a case."""
        case = await self.repository.get(case_id)
        if not case or case.user_id != user_id:
            return None

        # Extract user messages from turn history
        queries = []
        for turn in case.turn_history:
            if hasattr(turn, 'user_message') and turn.user_message:
                queries.append({
                    "turn_number": turn.turn_number,
                    "message": turn.user_message,
                    "timestamp": turn.turn_started_at.isoformat() if hasattr(turn, 'turn_started_at') else None,
                })
        
        return queries

    async def get_analytics_summary(self, user_id: str) -> dict:
        """Get analytics summary for user's cases."""
        all_cases = await self.repository.list(user_id=user_id, limit=1000)
        
        from fm_core_lib.models import CaseStatus
        
        summary = {
            "total_cases": len(all_cases),
            "by_status": {},
            "by_severity": {},
            "avg_resolution_time_hours": None,
            "total_evidence_collected": 0,
            "total_hypotheses_generated": 0,
        }
        
        # Count by status
        for case in all_cases:
            status_key = case.status.value
            summary["by_status"][status_key] = summary["by_status"].get(status_key, 0) + 1
            
            # Count evidence and hypotheses
            summary["total_evidence_collected"] += len(case.evidence)
            summary["total_hypotheses_generated"] += len(case.hypotheses)
        
        return summary
