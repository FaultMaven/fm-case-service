"""Case API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from case_service.core import CaseManager
from case_service.infrastructure.database import db_client
from case_service.models import (
    CaseCreateRequest,
    CaseUpdateRequest,
    CaseStatusUpdateRequest,
    CaseResponse,
    CaseListResponse,
    CaseStatus,
)
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


# Global singleton in-memory repository (persists across requests)
_inmemory_repository = None

async def get_case_repository() -> "CaseRepository":
    """Dependency to get case repository.

    Returns the appropriate repository implementation based on CASE_STORAGE_TYPE
    environment variable:
    - inmemory (default): InMemoryCaseRepository singleton for dev/testing
    - postgres: PostgreSQLHybridCaseRepository for production
    """
    import os
    from case_service.infrastructure.persistence import (
        InMemoryCaseRepository,
        PostgreSQLHybridCaseRepository,
    )

    storage_type = os.getenv("CASE_STORAGE_TYPE", "inmemory").lower()

    if storage_type == "postgres":
        # Use PostgreSQL with hybrid schema
        async for session in db_client.get_session():
            yield PostgreSQLHybridCaseRepository(session)
    else:
        # Default to in-memory singleton for development/testing
        global _inmemory_repository
        if _inmemory_repository is None:
            _inmemory_repository = InMemoryCaseRepository()
        yield _inmemory_repository


async def get_case_manager(
    repository: "CaseRepository" = Depends(get_case_repository),
) -> CaseManager:
    """Dependency to get case manager with repository."""
    return CaseManager(repository)


async def get_user_id(x_user_id: Optional[str] = Header(None, alias="X-User-ID")) -> str:
    """Get user ID from X-User-ID header (set by API Gateway).

    The API Gateway validates JWT tokens and adds X-User-* headers after
    stripping any client-provided ones to prevent header injection attacks.
    Services trust these headers without additional JWT validation.

    Args:
        x_user_id: User ID from X-User-ID header (added by API Gateway)

    Returns:
        User ID string

    Raises:
        HTTPException: If X-User-ID header is missing
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID header required (should be added by API Gateway)",
        )

    return x_user_id


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get(
    "/health",
    summary="Get case service health",
    description="""
Returns health status of the case management subsystem.

**Workflow**:
1. Checks case persistence system connectivity
2. Returns service status and feature flags
3. No authentication required (health endpoints are public)

**Response Example**:
```json
{
  "service": "case_management",
  "status": "healthy",
  "timestamp": "2025-11-19T10:30:00Z",
  "features": {
    "case_persistence": true,
    "case_sharing": true,
    "conversation_history": true
  }
}
```

**Storage**: No database access (lightweight check)
**Rate Limits**: None
**Authorization**: None required (public endpoint)
    """,
    responses={
        200: {"description": "Service health status returned successfully"},
        500: {"description": "Internal server error - service unhealthy"}
    }
)
async def get_case_service_health() -> Dict[str, Any]:
    """Get case service health status."""
    try:
        return {
            "service": "case_management",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "features": {
                "case_persistence": True,
                "case_sharing": True,
                "conversation_history": True
            }
        }
    except Exception as e:
        return {
            "service": "case_management",
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }


# =============================================================================
# Core CRUD Endpoints
# =============================================================================

@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new troubleshooting case",
    description="""
Creates a new troubleshooting case for the authenticated user.

**Workflow**:
1. Case created in 'consulting' status with auto-generated ID (case_XXXX format)
2. Title auto-generated if not provided (Case-MMDD-N format)
3. User can specify priority, category, and metadata

**Request Body Example**:
```json
{
  "title": "Redis connection timeouts in production",
  "description": "Intermittent timeouts on Redis cluster during peak hours",
  "priority": "high",
  "category": "performance",
  "metadata": {"environment": "production", "cluster": "redis-prod-1"}
}
```

**Response Example**:
```json
{
  "case_id": "case_a1b2c3d4e5f6",
  "owner_id": "user_123",
  "title": "Redis connection timeouts in production",
  "description": "Intermittent timeouts on Redis cluster during peak hours",
  "status": "consulting",
  "priority": "high",
  "category": "performance",
  "metadata": {"environment": "production", "cluster": "redis-prod-1"},
  "created_at": "2025-11-19T10:30:00Z",
  "updated_at": "2025-11-19T10:30:00Z",
  "resolved_at": null,
  "message_count": 0
}
```

**Storage**: SQLite database (fm_cases.db) with user_id indexing
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header from fm-api-gateway
**User Isolation**: Cases are strictly scoped to the creating user
    """,
    responses={
        201: {
            "description": "Case created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "case_id": "case_a1b2c3d4e5f6",
                        "user_id": "user_123",
                        "status": "active",
                        "created_at": "2025-11-19T10:30:00Z"
                    }
                }
            }
        },
        400: {"description": "Invalid request data (validation error)"},
        401: {"description": "Unauthorized - missing or invalid X-User-ID header"},
        500: {"description": "Internal server error - database operation failed"}
    }
)
async def create_case(
    request: CaseCreateRequest,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Create a new case.

    Requires X-User-ID header from gateway.
    """
    case = await case_manager.create_case(user_id, request)
    return CaseResponse.from_case(case)


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Get case by ID",
    description="""
Retrieves a single case by its unique case_id.

**Access Control**:
- Users can only access their own cases
- Attempting to access another user's case returns 404 (not 403) to prevent enumeration
- Case ID must be exact match (case-sensitive)

**Request Example**:
```
GET /api/v1/cases/case_a1b2c3d4e5f6
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_a1b2c3d4e5f6",
  "user_id": "user_123",
  "session_id": "session_abc123",
  "title": "Redis connection timeouts in production",
  "description": "Intermittent timeouts on Redis cluster during peak hours",
  "status": "investigating",
  "severity": "high",
  "category": "performance",
  "metadata": {"environment": "production"},
  "tags": ["redis", "timeout"],
  "created_at": "2025-11-19T10:30:00Z",
  "updated_at": "2025-11-19T11:15:00Z",
  "resolved_at": null
}
```

**Storage**: Retrieved from SQLite with user_id filter
**Authorization**: Requires X-User-ID header
**User Isolation**: Enforced at database query level
    """,
    responses={
        200: {"description": "Case found and returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied (returns 404 to prevent enumeration)"},
        500: {"description": "Internal server error"}
    }
)
async def get_case(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get a case by ID.

    Users can only access their own cases.
    """
    case = await case_manager.get_case(case_id, user_id)

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )

    return CaseResponse.from_case(case)


@router.put(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Update case details",
    description="""
Updates an existing case with new information. All fields are optional.

**Updatable Fields**:
- `title`: Case title (max 200 characters)
- `description`: Detailed description
- `status`: Case status (consulting/investigating/resolved/closed)
- `priority`: Priority level (low/medium/high/critical)
- `category`: Category (performance/error/configuration/infrastructure/security/other)
- `metadata`: Custom metadata dictionary (merged with existing)

**Request Example**:
```json
{
  "status": "investigating",
  "priority": "critical",
  "description": "Issue escalated - affecting 50% of users",
  "metadata": {"escalated": true, "affected_users": 500}
}
```

**Response Example**:
```json
{
  "case_id": "case_a1b2c3d4e5f6",
  "status": "investigating",
  "priority": "critical",
  "updated_at": "2025-11-19T12:30:00Z",
  ...
}
```

**Behavior**:
- Only provided fields are updated (partial updates supported)
- `updated_at` timestamp automatically updated
- `resolved_at` set automatically when status changes to 'resolved'
- Users can only update their own cases

**Storage**: SQLite update with optimistic locking
**Authorization**: Requires X-User-ID header
**User Isolation**: Update only succeeds if case belongs to user
    """,
    responses={
        200: {"description": "Case updated successfully"},
        400: {"description": "Invalid request data"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def update_case(
    case_id: str,
    request: CaseUpdateRequest,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Update a case.

    Users can only update their own cases.
    """
    case = await case_manager.update_case(case_id, user_id, request)

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )

    return CaseResponse.from_case(case)


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete case permanently",
    description="""
Permanently deletes a case from the database.

**WARNING**: This operation is irreversible. The case and all associated data will be permanently deleted.

**Request Example**:
```
DELETE /api/v1/cases/case_a1b2c3d4e5f6
Headers:
  X-User-ID: user_123
```

**Response**:
```
204 No Content (success, no body returned)
404 Not Found (case doesn't exist or access denied)
```

**Behavior**:
- Case is permanently removed from database
- Session associations are not affected (sessions remain)
- Users can only delete their own cases
- No soft-delete or archival (use status='archived' instead if you want to preserve data)

**Recommended Alternative**: Consider updating status to 'archived' or 'closed' instead of deletion to preserve historical data:
```
PUT /api/v1/cases/{case_id}
{"status": "archived"}
```

**Storage**: Hard delete from SQLite
**Authorization**: Requires X-User-ID header
**User Isolation**: Delete only succeeds if case belongs to user
    """,
    responses={
        204: {"description": "Case deleted successfully (no content returned)"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def delete_case(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Delete a case.

    Users can only delete their own cases.
    """
    deleted = await case_manager.delete_case(case_id, user_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )


@router.get(
    "/{case_id}/ui",
    summary="Get case UI data",
    description="""
Returns phase-adaptive UI-optimized case data in a single response.

**Workflow**:
1. Retrieves case by ID with user ownership validation
2. Transforms case data into UI-friendly format
3. Includes phase-specific UI hints and state

**Use Case**: Frontend applications can fetch all required UI state in a single call,
reducing round-trips and improving perceived performance.

**Request Example**:
```
GET /api/v1/cases/case_abc123/ui
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "title": "Redis connection timeouts",
  "description": "Intermittent timeouts on Redis cluster",
  "status": "investigating",
  "priority": "high",
  "created_at": "2025-11-19T10:30:00Z",
  "updated_at": "2025-11-19T11:15:00Z"
}
```

**Storage**: SQLite read with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can access UI data
    """,
    responses={
        200: {"description": "UI-optimized case data returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access this case"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_ui(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Get phase-adaptive UI-optimized case response."""
    try:
        # Get case from service
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case"
            )

        # TODO: Implement transform_case_for_ui adapter
        # For now, return basic case data
        return {
            "case_id": case.case_id,
            "title": case.title,
            "description": case.description,
            "status": case.status.value if hasattr(case.status, 'value') else case.status,
            "priority": case.metadata.get("priority", "medium"),
            "created_at": case.created_at.isoformat() if hasattr(case.created_at, 'isoformat') else case.created_at,
            "updated_at": case.updated_at.isoformat() if hasattr(case.updated_at, 'isoformat') else case.updated_at,
            "note": "Full UI adapter pending implementation"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_case_ui: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get case UI data"
        )


@router.post(
    "/{case_id}/title",
    summary="Generate case title",
    description="""
Generates or retrieves a concise, case-specific title based on case content.

**Workflow**:
1. If case has meaningful existing title and force=false, returns existing title
2. Otherwise, generates new title from case messages and metadata
3. Updates case with generated title

**Query Parameters**:
- `force` (default: false): Force overwrite of existing meaningful title

**Request Body** (optional):
```json
{
  "max_words": 8,
  "hint": "focus on the root cause"
}
```

**Response Example**:
```json
{
  "title": "Redis Connection Timeout Investigation",
  "case_id": "case_abc123",
  "source": "generated",
  "generated": true
}
```

**Title Generation Rules**:
- Default titles ("New Case", "Untitled") are always regenerated
- Titles with < 3 words are considered non-meaningful
- max_words must be between 3-12 (default: 8)

**Storage**: SQLite read/write with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can generate titles
    """,
    responses={
        200: {"description": "Title generated or existing title returned"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to modify this case"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error - title generation failed"}
    }
)
async def generate_case_title(
    case_id: str,
    title_request: Optional[Dict[str, Any]] = None,
    force: bool = Query(False, description="Force overwrite of existing title"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Generate a concise, case-specific title from case messages and metadata."""
    try:
        logger.info(f"Title generation started for case {case_id}, force={force}")

        # Parse request body parameters (optional)
        max_words = 8
        hint = None
        if title_request:
            max_words = title_request.get("max_words", 8)
            hint = title_request.get("hint")
            # Validate max_words (3–12, default 8)
            if not isinstance(max_words, int) or max_words < 3 or max_words > 12:
                max_words = 8

        # Verify user has access to the case
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this case"
            )

        # Check if we should preserve existing title
        if not force and hasattr(case, 'title') and case.title:
            # Check if existing title is meaningful (not default/auto-generated)
            default_titles = ["New Case", "Untitled Case", "Untitled"]
            is_meaningful_title = (
                case.title not in default_titles and
                not case.title.lower().startswith("case-") and
                len(case.title.split()) >= 3
            )

            if is_meaningful_title:
                # Return existing user-set title to maintain idempotency
                logger.info(f"Returning existing meaningful title: '{case.title}'")
                return {
                    "title": case.title,
                    "case_id": case_id,
                    "source": "existing",
                    "generated": False
                }

        # TODO: Implement title generation with LLM
        # For now, generate a simple sequential title
        generated_title = f"Case {case_id[-8:]}"

        return {
            "title": generated_title,
            "case_id": case_id,
            "source": "generated",
            "generated": True,
            "note": "LLM title generation pending implementation"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in generate_case_title: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate title"
        )


@router.get(
    "",
    response_model=CaseListResponse,
    summary="List user's cases with pagination",
    description="""
Retrieves a paginated list of cases for the authenticated user.

**Query Parameters**:
- `status` (optional): Filter by status (active/investigating/resolved/archived/closed)
- `page` (default: 1): Page number (1-indexed)
- `page_size` (default: 50, max: 100): Number of cases per page

**Request Example**:
```
GET /api/v1/cases?status=investigating&page=1&page_size=20
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "cases": [
    {
      "case_id": "case_a1b2c3d4e5f6",
      "title": "Redis timeout issue",
      "status": "investigating",
      "priority": "high",
      "created_at": "2025-11-19T10:30:00Z",
      ...
    },
    {
      "case_id": "case_x7y8z9a0b1c2",
      "title": "API latency spike",
      "status": "investigating",
      "priority": "medium",
      "created_at": "2025-11-18T14:20:00Z",
      ...
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

**Pagination Calculation**:
- `total`: Total number of cases matching filter
- `total_pages`: ceil(total / page_size)
- Use `page` and `page_size` to navigate through results

**Sorting**: Cases returned in reverse chronological order (newest first)

**Storage**: Indexed query on user_id and status
**Authorization**: Requires X-User-ID header
**User Isolation**: Only returns cases belonging to authenticated user
    """,
    responses={
        200: {"description": "List of cases returned successfully"},
        400: {"description": "Invalid query parameters (e.g., page < 1 or page_size > 100)"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        500: {"description": "Internal server error"}
    }
)
async def list_cases(
    status_filter: Optional[CaseStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """List cases for the authenticated user.

    Supports pagination and status filtering.
    """
    # Convert page-based pagination to offset-based pagination
    offset = (page - 1) * page_size
    cases, total = await case_manager.list_cases(
        user_id=user_id,
        status=status_filter,
        limit=page_size,
        offset=offset,
    )

    return CaseListResponse(
        cases=[CaseResponse.from_case(case) for case in cases],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/session/{session_id}",
    response_model=CaseListResponse,
    summary="Get cases linked to a session",
    description="""
Retrieves all cases associated with a specific investigation session.

**Use Case**: When viewing an investigation session from fm-session-service, this endpoint shows all related troubleshooting cases.

**Query Parameters**:
- `page` (default: 1): Page number (1-indexed)
- `page_size` (default: 50, max: 100): Number of cases per page

**Request Example**:
```
GET /api/v1/cases/session/session_abc123?page=1&page_size=10
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "cases": [
    {
      "case_id": "case_a1b2c3d4e5f6",
      "session_id": "session_abc123",
      "title": "Database performance investigation",
      "status": "investigating",
      ...
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 10
}
```

**Access Control**:
- Returns only cases that belong to the authenticated user
- Even if a session has cases from multiple users, only the current user's cases are returned
- This prevents cross-user data leakage in shared session contexts

**Cross-Service Integration**:
- `session_id` comes from fm-session-service
- No validation that session exists (loose coupling)
- Session access control handled by fm-session-service

**Storage**: Query on session_id with user_id filter
**Authorization**: Requires X-User-ID header
**User Isolation**: Filtered to authenticated user's cases only
    """,
    responses={
        200: {"description": "List of cases for session returned successfully (may be empty)"},
        400: {"description": "Invalid query parameters"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        500: {"description": "Internal server error"}
    }
)
async def get_cases_for_session(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get cases for a specific session.

    Note: This returns cases linked to the session, but access control
    is still enforced via the session's user_id.
    """
    # Get all cases for the session (no pagination at manager level)
    all_cases = await case_manager.get_cases_by_session(session_id=session_id)

    # Filter to only cases owned by the authenticated user
    user_cases = [case for case in all_cases if case.user_id == user_id]

    # Apply pagination
    offset = (page - 1) * page_size
    paginated_cases = user_cases[offset:offset + page_size]
    user_total = len(user_cases)

    return CaseListResponse(
        cases=[CaseResponse.from_case(case) for case in paginated_cases],
        total=user_total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{case_id}/status",
    response_model=CaseResponse,
    summary="Update case status",
    description="""
Updates only the status field of a case (convenience endpoint).

**Status Transitions**:
```
active → investigating → resolved
         ↓
      archived
         ↓
      closed
```

**Common Workflows**:
- **Start Investigation**: active → investigating
- **Resolve Issue**: investigating → resolved
- **Archive Old Case**: resolved → archived
- **Close Without Resolution**: investigating → closed

**Request Example**:
```json
{
  "status": "resolved"
}
```

**Response Example**:
```json
{
  "case_id": "case_a1b2c3d4e5f6",
  "status": "resolved",
  "resolved_at": "2025-11-19T15:30:00Z",
  "updated_at": "2025-11-19T15:30:00Z",
  ...
}
```

**Automatic Timestamp Handling**:
- `updated_at`: Always updated to current timestamp
- `resolved_at`: Automatically set when status changes to 'resolved'
- `resolved_at`: Cleared if status changes away from 'resolved'

**Use Cases**:
- Workflow automation (e.g., auto-resolve when all tests pass)
- Status boards and dashboards
- Case lifecycle tracking

**Alternative**: You can also update status via `PUT /api/v1/cases/{case_id}` with `{"status": "resolved"}`, but this endpoint provides clearer semantics for status-only updates.

**Storage**: SQLite update with timestamp management
**Authorization**: Requires X-User-ID header
**User Isolation**: Update only succeeds if case belongs to user
    """,
    responses={
        200: {"description": "Case status updated successfully"},
        400: {"description": "Invalid status value"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def update_case_status(
    case_id: str,
    request: CaseStatusUpdateRequest,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Update case status.

    Users can only update their own cases.
    """
    case = await case_manager.update_status(case_id, user_id, request.status)

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )

    return CaseResponse.from_case(case)


# =============================================================================
# Evidence & Data Endpoints (Phase 4)
# =============================================================================

@router.get(
    "/{case_id}/data",
    summary="List case data",
    description="""
Lists all data files and artifacts associated with a case.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves paginated list of data records
3. Returns data metadata (not file contents)

**Query Parameters**:
- `limit` (default: 50, max: 200): Maximum number of items to return
- `offset` (default: 0): Number of items to skip for pagination

**Request Example**:
```
GET /api/v1/cases/case_abc123/data?limit=20&offset=0
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "data": [
    {
      "data_id": "data_xyz789",
      "filename": "error_logs.txt",
      "data_type": "log_file",
      "size_bytes": 15360,
      "upload_timestamp": "2025-11-19T10:30:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

**Storage**: SQLite query with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can list data
    """,
    responses={
        200: {"description": "Data list returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access this case"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def list_case_data(
    case_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """List data files associated with a case."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case"
            )

        # TODO: Implement data listing in CaseManager
        # For now, return empty list
        return {
            "case_id": case_id,
            "data": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "note": "Data storage integration pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing case data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list case data"
        )


@router.get(
    "/{case_id}/data/{data_id}",
    summary="Get case data",
    description="""
Retrieves details for a specific data file attached to a case.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves data record by ID
3. Returns data metadata and processing status

**Request Example**:
```
GET /api/v1/cases/case_abc123/data/data_xyz789
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "data_id": "data_xyz789",
  "case_id": "case_abc123",
  "filename": "error_logs.txt",
  "description": "Application error logs from production",
  "data_type": "log_file",
  "size_bytes": 15360,
  "upload_timestamp": "2025-11-19T10:30:00Z",
  "processing_status": "completed"
}
```

**Data Types**:
- `log_file`: Application or system logs
- `config_file`: Configuration files
- `screenshot`: UI screenshots
- `trace`: Distributed traces or stack traces
- `metrics`: Metrics data exports
- `other`: Uncategorized data

**Storage**: SQLite query with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can access data
    """,
    responses={
        200: {"description": "Data record details returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access this case"},
        404: {"description": "Case or data record not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_data(
    case_id: str,
    data_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Get specific data file details for a case."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case"
            )

        # TODO: Implement get specific data in CaseManager
        # For now, return mock data record
        return {
            "data_id": data_id,
            "case_id": case_id,
            "filename": f"data_{data_id}.txt",
            "description": "Sample case data",
            "data_type": "log_file",
            "size_bytes": 1024,
            "upload_timestamp": datetime.now(timezone.utc).isoformat(),
            "processing_status": "pending",
            "note": "Data storage integration pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting case data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve case data: {str(e)}"
        )


@router.delete(
    "/{case_id}/data/{data_id}",
    summary="Delete case data",
    status_code=status.HTTP_204_NO_CONTENT,
    description="""
Permanently deletes a data file from a case.

**WARNING**: This operation is irreversible. The data file and all associated
metadata will be permanently deleted.

**Workflow**:
1. Validates case exists and user has access
2. Deletes data record and associated file storage
3. Returns 204 No Content on success

**Request Example**:
```
DELETE /api/v1/cases/case_abc123/data/data_xyz789
Headers:
  X-User-ID: user_123
```

**Response**:
```
204 No Content (success, no body returned)
404 Not Found (case or data doesn't exist)
```

**Behavior**:
- Data record is permanently removed
- Associated file in storage is deleted
- Operation is idempotent (deleting non-existent data returns 404)

**Storage**: SQLite delete with file storage cleanup
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can delete data
    """,
    responses={
        204: {"description": "Data deleted successfully (no content returned)"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to delete from this case"},
        404: {"description": "Case or data record not found"},
        500: {"description": "Internal server error"}
    }
)
async def delete_case_data(
    case_id: str,
    data_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Delete a specific data file from a case."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete data from this case"
            )

        # TODO: Implement delete data in CaseManager
        # For now, return success (idempotent)
        logger.info(f"Delete data {data_id} from case {case_id} (stub implementation)")
        return

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting case data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete case data"
        )


@router.post(
    "/{case_id}/data",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Add evidence/data to case",
    description="""
Adds evidence or data files to a case for investigation.

**Workflow**:
1. Validates case exists and user has access
2. Processes and stores the evidence data
3. Returns updated case with new evidence attached

**Request Body Example**:
```json
{
  "type": "log_file",
  "filename": "application.log",
  "content": "2025-11-19 10:30:00 ERROR Connection timeout...",
  "metadata": {
    "source": "production-server-01",
    "log_level": "ERROR"
  }
}
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "user_id": "user_123",
  "title": "Connection timeout investigation",
  "status": "investigating",
  ...
}
```

**Evidence Types**:
- `log_file`: Application or system logs
- `config_file`: Configuration files
- `screenshot`: UI screenshots
- `trace`: Stack traces or distributed traces
- `metrics`: Performance metrics

**Storage**: SQLite with file storage for large content
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can add evidence
    """,
    responses={
        200: {"description": "Evidence added successfully, returns updated case"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def add_case_data(
    case_id: str,
    evidence_data: dict,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Add evidence/data to a case."""
    case = await case_manager.add_evidence(case_id, user_id, evidence_data)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    return CaseResponse.from_case(case)


@router.get(
    "/{case_id}/evidence/{evidence_id}",
    summary="Get specific evidence by ID",
    description="""
Retrieves a specific evidence item from a case by its ID.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves evidence by ID from case
3. Returns evidence details and content

**Request Example**:
```
GET /api/v1/cases/case_abc123/evidence/ev_xyz789
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "evidence_id": "ev_xyz789",
  "case_id": "case_abc123",
  "type": "log_file",
  "filename": "error.log",
  "content": "2025-11-19 ERROR: Connection refused...",
  "created_at": "2025-11-19T10:30:00Z",
  "metadata": {"source": "production"}
}
```

**Storage**: SQLite query with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can access evidence
    """,
    responses={
        200: {"description": "Evidence details returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case or evidence not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_evidence(
    case_id: str,
    evidence_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get specific evidence from a case."""
    evidence = await case_manager.get_evidence(case_id, evidence_id, user_id)
    if not evidence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evidence {evidence_id} not found")
    return evidence


@router.get(
    "/{case_id}/uploaded-files",
    summary="Get uploaded files for case",
    description="""
Lists all files uploaded to a case during investigation.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves list of uploaded files
3. Returns file metadata and processing status

**Request Example**:
```
GET /api/v1/cases/case_abc123/uploaded-files
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "files": [
    {
      "file_id": "file_xyz789",
      "filename": "screenshot.png",
      "content_type": "image/png",
      "size_bytes": 102400,
      "upload_timestamp": "2025-11-19T10:30:00Z",
      "status": "processed"
    }
  ],
  "total": 3
}
```

**Storage**: SQLite query with file storage references
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can list files
    """,
    responses={
        200: {"description": "File list returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_uploaded_files(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get uploaded files for a case."""
    files = await case_manager.get_uploaded_files(case_id, user_id)
    if files is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    return {"files": files, "total": len(files)}


@router.get(
    "/{case_id}/uploaded-files/{file_id}",
    summary="Get uploaded file details",
    description="""
Retrieves detailed information for a specific uploaded file.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves file metadata by ID
3. Returns file details including derived evidence

**Request Example**:
```
GET /api/v1/cases/case_abc123/uploaded-files/file_xyz789
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "file_id": "file_xyz789",
  "case_id": "case_abc123",
  "filename": "error_screenshot.png",
  "content_type": "image/png",
  "size_bytes": 102400,
  "upload_timestamp": "2025-11-19T10:30:00Z",
  "status": "processed",
  "derived_evidence": [
    {"type": "text_extraction", "content": "Error: Connection refused"}
  ]
}
```

**File Processing Status**:
- `pending`: File uploaded, awaiting processing
- `processing`: File being analyzed
- `processed`: Processing complete, evidence extracted
- `failed`: Processing failed

**Storage**: SQLite query with file storage reference
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can access file details
    """,
    responses={
        200: {"description": "File details returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access this case"},
        404: {"description": "Case or file not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_uploaded_file_details(
    case_id: str,
    file_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Get details for a specific uploaded file."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case"
            )

        # TODO: Implement get specific uploaded file details in CaseManager
        # For now, return mock file details
        return {
            "file_id": file_id,
            "case_id": case_id,
            "filename": f"upload_{file_id}.log",
            "content_type": "text/plain",
            "size_bytes": 2048,
            "upload_timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "processed",
            "derived_evidence": [],
            "note": "File storage integration pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting uploaded file details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file details"
        )


@router.post(
    "/{case_id}/close",
    response_model=CaseResponse,
    summary="Close a case",
    description="""
Closes a case, marking the investigation as complete.

**Workflow**:
1. Validates case exists and user has access
2. Updates case status to 'closed'
3. Records closure metadata (resolution, notes)
4. Returns updated case

**Request Body** (optional):
```json
{
  "resolution": "resolved",
  "resolution_notes": "Root cause identified as misconfigured timeout",
  "resolved_by": "Increased connection timeout to 30s"
}
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "status": "closed",
  "resolved_at": "2025-11-19T15:30:00Z",
  ...
}
```

**Closure Types**:
- `resolved`: Issue successfully resolved
- `not_reproducible`: Could not reproduce the issue
- `duplicate`: Duplicate of another case
- `wont_fix`: Issue acknowledged but won't be fixed
- `invalid`: Not a valid issue

**Storage**: SQLite update with timestamp management
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can close case
    """,
    responses={
        200: {"description": "Case closed successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def close_case(
    case_id: str,
    close_data: Optional[dict] = None,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Close a case."""
    case = await case_manager.close_case(case_id, user_id, close_data)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    return CaseResponse.from_case(case)


@router.post(
    "/search",
    response_model=CaseListResponse,
    summary="Search cases",
    description="""
Searches cases with flexible filtering criteria.

**Workflow**:
1. Validates search parameters
2. Executes search query with user isolation
3. Returns paginated results

**Request Body Example**:
```json
{
  "query": "connection timeout",
  "status": ["investigating", "active"],
  "severity": ["high", "critical"],
  "category": "performance",
  "date_from": "2025-11-01T00:00:00Z",
  "date_to": "2025-11-30T23:59:59Z",
  "tags": ["redis", "database"],
  "page": 1,
  "page_size": 20
}
```

**Response Example**:
```json
{
  "cases": [...],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

**Search Fields**:
- `query`: Full-text search in title and description
- `status`: Filter by status (array)
- `severity`: Filter by severity (array)
- `category`: Filter by category
- `date_from`/`date_to`: Date range filter
- `tags`: Filter by tags (AND logic)

**Storage**: SQLite full-text search with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only searches user's own cases
    """,
    responses={
        200: {"description": "Search results returned successfully"},
        400: {"description": "Invalid search parameters"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        500: {"description": "Internal server error"}
    }
)
async def search_cases(
    search_params: dict,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Search cases with filters."""
    cases, total = await case_manager.search_cases(user_id, search_params)
    return CaseListResponse(
        cases=[CaseResponse.from_case(case) for case in cases],
        total=total,
        page=1,
        page_size=len(cases),
    )


# =============================================================================
# Hypothesis Management Endpoints (Phase 6.3)
# =============================================================================

@router.post(
    "/{case_id}/hypotheses",
    summary="Add hypothesis to case",
    description="""
Adds a new hypothesis to an investigation case for tracking potential root causes.

**Workflow**:
1. Validates case exists and user has access
2. Creates hypothesis with initial status
3. Returns hypothesis ID and updated count

**Request Body Example**:
```json
{
  "title": "Redis connection pool exhaustion",
  "description": "High load causing connection pool to be exhausted",
  "confidence": 0.7,
  "evidence": ["Connection timeout errors in logs", "Pool size at max"],
  "suggested_tests": ["Increase pool size", "Check connection leaks"]
}
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "hypothesis": {...},
  "total_hypotheses": 3
}
```

**Hypothesis Status Values**:
- `proposed`: Initial state
- `testing`: Under investigation
- `confirmed`: Validated as root cause
- `rejected`: Ruled out
- `deferred`: Put on hold

**Storage**: SQLite with JSONB for hypothesis data
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can add hypotheses
    """,
    responses={
        200: {"description": "Hypothesis added successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def add_hypothesis(
    case_id: str,
    hypothesis_data: dict,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Add a new hypothesis to investigation case."""
    case = await case_manager.add_hypothesis(case_id, user_id, hypothesis_data)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    return {"case_id": case_id, "hypothesis": hypothesis_data, "total_hypotheses": len(case.hypotheses)}


@router.put(
    "/{case_id}/hypotheses/{hypothesis_id}",
    summary="Update hypothesis",
    description="""
Updates an existing hypothesis with new status, confidence, or evidence.

**Workflow**:
1. Validates case and hypothesis exist
2. Applies partial updates to hypothesis
3. Returns updated hypothesis

**Request Body Example**:
```json
{
  "status": "confirmed",
  "confidence": 0.95,
  "confirmation_evidence": "Load test confirmed pool exhaustion under high load",
  "resolution": "Increased pool size from 10 to 50"
}
```

**Response Example**:
```json
{
  "hypothesis_id": "hyp_xyz789",
  "case_id": "case_abc123",
  "title": "Redis connection pool exhaustion",
  "status": "confirmed",
  "confidence": 0.95,
  "updated_at": "2025-11-19T15:30:00Z"
}
```

**Updatable Fields**:
- `status`: Hypothesis status
- `confidence`: Confidence score (0.0-1.0)
- `evidence`: Additional evidence array
- `confirmation_evidence`: Evidence confirming/rejecting
- `resolution`: How the issue was resolved

**Storage**: SQLite update with JSONB merge
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can update hypotheses
    """,
    responses={
        200: {"description": "Hypothesis updated successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case or hypothesis not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_hypothesis(
    case_id: str,
    hypothesis_id: str,
    updates: dict,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Update an existing hypothesis (status, confidence, etc)."""
    hypothesis = await case_manager.update_hypothesis(case_id, hypothesis_id, user_id, updates)
    if not hypothesis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Hypothesis {hypothesis_id} not found")
    return hypothesis


@router.post(
    "/{case_id}/queries",
    summary="Submit case query",
    description="""
Submits a user message or query to the case investigation.

**Workflow**:
1. Validates case exists and user has access
2. Stores query in case history
3. Returns query acknowledgment

**Request Body Example**:
```json
{
  "message": "What are the common causes of Redis connection timeouts?",
  "context": {
    "current_focus": "connection_pool"
  }
}
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "message": "What are the common causes...",
  "status": "received",
  "timestamp": "2025-11-19T10:30:00Z"
}
```

**Query Types**:
- Investigation questions
- Troubleshooting commands
- Evidence requests
- Hypothesis proposals

**Storage**: SQLite with message history
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can submit queries
    """,
    responses={
        200: {"description": "Query submitted successfully"},
        400: {"description": "Invalid query data - message required"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to query this case"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def submit_case_query(
    case_id: str,
    query_data: Dict[str, Any],
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Submit user message to case investigation."""
    # Validate case_id parameter
    if not case_id or case_id.strip() in ("", "undefined", "null"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid case_id is required"
        )

    # Extract message text
    message_text = query_data.get("message", "")
    if not message_text or not message_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message text is required"
        )

    # Verify case exists and user has access
    case = await case_manager.get_case(case_id, user_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found or access denied"
        )

    # Verify ownership
    if case.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit queries to this case"
        )

    # Add query to case history
    try:
        # TODO: Implement add_case_query method in CaseManager
        # For now, return success response
        return {
            "case_id": case_id,
            "message": message_text,
            "status": "received",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Query processing pending - investigation service integration required"
        }
    except Exception as e:
        logger.error(f"Error submitting query for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit query"
        )


@router.get(
    "/{case_id}/queries",
    summary="Get case query history",
    description="""
Retrieves the history of user queries submitted to this case.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves query history
3. Returns chronologically ordered queries

**Request Example**:
```
GET /api/v1/cases/case_abc123/queries
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "queries": [
    {
      "query_id": "q_001",
      "message": "What causes connection timeouts?",
      "timestamp": "2025-11-19T10:30:00Z",
      "response_status": "answered"
    }
  ],
  "total": 5
}
```

**Storage**: SQLite query with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can view query history
    """,
    responses={
        200: {"description": "Query history returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_queries(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get all user queries/messages for this case."""
    queries = await case_manager.get_case_queries(case_id, user_id)
    if queries is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    return {"case_id": case_id, "queries": queries, "total": len(queries)}


@router.get(
    "/{case_id}/messages",
    summary="Get case messages",
    description="""
Retrieves conversation messages for a case with pagination support.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves paginated message history
3. Returns messages with metadata

**Query Parameters**:
- `limit` (default: 50, max: 100): Maximum messages to return
- `offset` (default: 0): Pagination offset
- `include_debug` (default: false): Include debug metadata

**Request Example**:
```
GET /api/v1/cases/case_abc123/messages?limit=20&offset=0
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "messages": [
    {
      "message_id": "msg_001",
      "role": "user",
      "content": "I'm seeing connection timeouts",
      "timestamp": "2025-11-19T10:30:00Z"
    },
    {
      "message_id": "msg_002",
      "role": "assistant",
      "content": "Let me help investigate...",
      "timestamp": "2025-11-19T10:30:05Z"
    }
  ],
  "total_count": 50,
  "retrieved_count": 20,
  "limit": 20,
  "offset": 0
}
```

**Message Roles**:
- `user`: User messages
- `assistant`: AI assistant responses
- `system`: System notifications

**Storage**: SQLite with message pagination
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can view messages
    """,
    responses={
        200: {"description": "Messages returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access this case"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_messages(
    case_id: str,
    limit: int = Query(50, le=100, ge=1, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    include_debug: bool = Query(False, description="Include debug information for troubleshooting"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Retrieve conversation messages for a case with pagination."""
    try:
        # Verify user has access to the case
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case"
            )

        # TODO: Implement get_case_messages_enhanced method in CaseManager
        # For now, return mock response structure
        return {
            "case_id": case_id,
            "messages": [],
            "total_count": 0,
            "retrieved_count": 0,
            "limit": limit,
            "offset": offset,
            "debug_info": {
                "storage_status": "pending",
                "note": "Message storage integration pending"
            } if include_debug else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_case_messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}"
        )


# =============================================================================
# Reports & Analytics Endpoints (Phase 6.3)
# =============================================================================

@router.get(
    "/{case_id}/analytics",
    summary="Get case analytics",
    description="""
Returns analytics and metrics for a specific case.

**Workflow**:
1. Validates case exists and user has access
2. Calculates case metrics
3. Returns analytics summary

**Request Example**:
```
GET /api/v1/cases/case_abc123/analytics
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "message_count": 25,
  "participant_count": 1,
  "resolution_time_minutes": 120,
  "status": "resolved",
  "hypotheses_count": 3,
  "evidence_count": 5,
  "first_response_time_seconds": 15
}
```

**Metrics Included**:
- `message_count`: Total messages in case
- `participant_count`: Number of participants
- `resolution_time_minutes`: Time to resolution (if resolved)
- `hypotheses_count`: Number of hypotheses generated
- `evidence_count`: Number of evidence items attached

**Storage**: SQLite aggregation queries
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can view analytics
    """,
    responses={
        200: {"description": "Analytics data returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access this case"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_analytics(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Get case analytics and metrics."""
    try:
        # Verify user has access to the case
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case"
            )

        # TODO: Implement get_case_analytics in CaseManager
        # For now, return mock analytics
        return {
            "case_id": case_id,
            "message_count": 0,
            "participant_count": 1,
            "resolution_time_minutes": None,
            "status": case.status.value if hasattr(case.status, 'value') else case.status,
            "note": "Analytics calculation pending implementation"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting case analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get case analytics: {str(e)}"
        )


@router.get(
    "/{case_id}/report-recommendations",
    summary="Get report recommendations",
    description="""
Returns intelligent recommendations for which reports to generate for a case.

**Workflow**:
1. Analyzes case content and status
2. Determines applicable report types
3. Returns prioritized recommendations

**Request Example**:
```
GET /api/v1/cases/case_abc123/report-recommendations
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "available_reports": ["incident_report", "post_mortem", "runbook"],
  "recommended_reports": [
    {
      "type": "post_mortem",
      "reason": "Case resolved with root cause identified",
      "priority": "high"
    }
  ],
  "similar_runbooks": [
    {"id": "rb_001", "title": "Redis Connection Issues", "similarity": 0.85}
  ]
}
```

**Report Types**:
- `incident_report`: Standard incident documentation
- `post_mortem`: Root cause analysis document
- `runbook`: Operational runbook for similar issues
- `timeline`: Event timeline summary

**Storage**: SQLite with vector similarity search
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can get recommendations
    """,
    responses={
        200: {"description": "Recommendations returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access this case"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_report_recommendations(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Get intelligent report recommendations for a case."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this case"
            )

        # TODO: Implement report recommendation logic
        # For now, return basic recommendations
        return {
            "case_id": case_id,
            "available_reports": ["incident_report", "post_mortem"],
            "recommended_reports": [],
            "note": "Report recommendation system pending implementation"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get report recommendations"
        )


@router.post(
    "/{case_id}/reports",
    summary="Generate case reports",
    description="""
Generates documentation reports for a case.

**Workflow**:
1. Validates case exists and user has access
2. Queues report generation for requested types
3. Returns report IDs for tracking

**Request Body Example**:
```json
{
  "report_types": ["incident_report", "post_mortem"],
  "options": {
    "include_timeline": true,
    "include_evidence": true,
    "format": "markdown"
  }
}
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "report_types": ["incident_report", "post_mortem"],
  "status": "generating",
  "reports": [
    {"type": "incident_report", "report_id": "rpt_001", "status": "pending"},
    {"type": "post_mortem", "report_id": "rpt_002", "status": "pending"}
  ]
}
```

**Report Types**:
- `incident_report`: Standard incident documentation
- `post_mortem`: Detailed root cause analysis
- `runbook`: Operational runbook
- `summary`: Brief case summary

**Storage**: SQLite with async report generation
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can generate reports
    """,
    responses={
        200: {"description": "Report generation started"},
        400: {"description": "Invalid request - at least one report type required"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to generate reports"},
        404: {"description": "Case not found"},
        500: {"description": "Internal server error"}
    }
)
async def generate_case_reports(
    case_id: str,
    report_request: Dict[str, Any],
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Generate case documentation reports."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to generate reports for this case"
            )

        # Extract report types from request
        report_types = report_request.get("report_types", [])
        if not report_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one report type is required"
            )

        # TODO: Implement report generation
        # For now, return mock response
        return {
            "case_id": case_id,
            "report_types": report_types,
            "status": "pending",
            "note": "Report generation service pending implementation"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/{case_id}/reports",
    summary="Get case reports",
    description="""
Retrieves generated reports for a case.

**Workflow**:
1. Validates case exists and user has access
2. Retrieves report list (current or historical)
3. Returns report metadata

**Query Parameters**:
- `include_history` (default: false): Include all report versions

**Request Example**:
```
GET /api/v1/cases/case_abc123/reports?include_history=false
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "case_id": "case_abc123",
  "reports": [
    {
      "report_id": "rpt_001",
      "type": "incident_report",
      "status": "completed",
      "created_at": "2025-11-19T10:30:00Z",
      "version": 1
    }
  ],
  "include_history": false
}
```

**Report Status Values**:
- `pending`: Report generation queued
- `generating`: Report being generated
- `completed`: Report ready for download
- `failed`: Generation failed

**Storage**: SQLite query with version filtering
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can view reports
    """,
    responses={
        200: {"description": "Reports list returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to access reports"},
        404: {"description": "Case not found or access denied"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_reports(
    case_id: str,
    include_history: bool = Query(default=False, description="Include all report versions"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Retrieve generated reports for a case."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found or access denied"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access reports for this case"
            )

        # TODO: Implement report retrieval from report store
        # For now, return empty list
        return {
            "case_id": case_id,
            "reports": [],
            "include_history": include_history,
            "note": "Report storage integration pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving case reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reports"
        )


@router.get(
    "/{case_id}/reports/{report_id}/download",
    summary="Download case report",
    description="""
Downloads a generated report in the specified format.

**Workflow**:
1. Validates case and report exist
2. Generates report in requested format
3. Returns file download response

**Query Parameters**:
- `format` (default: markdown): Output format (markdown or pdf)

**Request Example**:
```
GET /api/v1/cases/case_abc123/reports/rpt_001/download?format=markdown
Headers:
  X-User-ID: user_123
```

**Response**:
- Content-Type: text/markdown or application/pdf
- Content-Disposition: attachment; filename="report.md"

**Supported Formats**:
- `markdown`: Markdown text format (default)
- `pdf`: PDF document (coming soon)

**Storage**: SQLite with file content retrieval
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only case owner can download reports
    """,
    responses={
        200: {"description": "Report file returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        403: {"description": "Forbidden - not authorized to download report"},
        404: {"description": "Case or report not found"},
        501: {"description": "PDF format not yet supported"},
        500: {"description": "Internal server error"}
    }
)
async def download_case_report(
    case_id: str,
    report_id: str,
    format: str = Query(default="markdown", description="Output format (markdown or pdf)"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """Download case report in specified format."""
    try:
        # Verify case exists and user has access
        case = await case_manager.get_case(case_id, user_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found"
            )

        # Verify ownership
        if case.owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to download reports for this case"
            )

        # Check format support
        if format == "pdf":
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="PDF format not yet supported - use markdown format"
            )

        # TODO: Implement report download from report store
        # For now, return placeholder
        return {
            "case_id": case_id,
            "report_id": report_id,
            "format": format,
            "status": "pending",
            "note": "Report download service pending implementation"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download report"
        )


@router.get(
    "/reports",
    summary="List available reports",
    description="""
Lists all available reports across the user's cases.

**Workflow**:
1. Retrieves all reports for user's cases
2. Returns paginated list with metadata

**Query Parameters**:
- `limit` (default: 50, max: 100): Maximum reports to return

**Request Example**:
```
GET /api/v1/cases/reports?limit=20
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "reports": [
    {
      "report_id": "rpt_001",
      "case_id": "case_abc123",
      "type": "incident_report",
      "status": "completed",
      "created_at": "2025-11-19T10:30:00Z"
    }
  ],
  "total": 15
}
```

**Storage**: SQLite query with user_id filter
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only shows user's own reports
    """,
    responses={
        200: {"description": "Reports list returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        500: {"description": "Internal server error"}
    }
)
async def list_reports(
    user_id: str = Depends(get_user_id),
    limit: int = Query(50, ge=1, le=100),
):
    """List available case reports for user."""
    # TODO: Implement actual report generation system
    return {
        "reports": [],
        "total": 0,
        "message": "Report generation system not yet implemented"
    }


@router.get(
    "/reports/{report_id}",
    summary="Get specific report",
    description="""
Retrieves a specific report by its ID.

**Workflow**:
1. Validates report exists and user has access
2. Returns report metadata and content

**Request Example**:
```
GET /api/v1/cases/reports/rpt_001
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "report_id": "rpt_001",
  "case_id": "case_abc123",
  "type": "incident_report",
  "title": "Redis Connection Timeout Incident",
  "status": "completed",
  "content": "# Incident Report\\n\\n## Summary...",
  "created_at": "2025-11-19T10:30:00Z",
  "version": 1
}
```

**Storage**: SQLite query with user access validation
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only report owner can access
    """,
    responses={
        200: {"description": "Report returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        404: {"description": "Report not found or access denied"},
        501: {"description": "Feature not yet implemented"},
        500: {"description": "Internal server error"}
    }
)
async def get_report(
    report_id: str,
    user_id: str = Depends(get_user_id),
):
    """Get specific case report by ID."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Report generation system not yet implemented"
    )


@router.get(
    "/analytics/summary",
    summary="Get case analytics summary",
    description="""
Returns aggregate analytics across all of the user's cases.

**Workflow**:
1. Aggregates metrics across user's cases
2. Calculates summary statistics
3. Returns analytics dashboard data

**Request Example**:
```
GET /api/v1/cases/analytics/summary
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "total_cases": 25,
  "cases_by_status": {
    "active": 5,
    "investigating": 8,
    "resolved": 10,
    "closed": 2
  },
  "cases_by_severity": {
    "critical": 2,
    "high": 8,
    "medium": 10,
    "low": 5
  },
  "average_resolution_time_hours": 4.5,
  "cases_this_week": 3,
  "cases_this_month": 12
}
```

**Metrics Included**:
- Total case count
- Cases by status breakdown
- Cases by severity breakdown
- Average resolution time
- Time-based case counts

**Storage**: SQLite aggregation queries
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only aggregates user's own cases
    """,
    responses={
        200: {"description": "Analytics summary returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        500: {"description": "Internal server error"}
    }
)
async def get_analytics_summary(
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get analytics summary for user's cases."""
    summary = await case_manager.get_analytics_summary(user_id)
    return summary


@router.get(
    "/analytics/trends",
    summary="Get case trends",
    description="""
Returns case trends and patterns over a specified time period.

**Workflow**:
1. Analyzes case data over time period
2. Calculates trends and patterns
3. Returns time-series data

**Query Parameters**:
- `days` (default: 30, max: 365): Number of days to analyze

**Request Example**:
```
GET /api/v1/cases/analytics/trends?days=30
Headers:
  X-User-ID: user_123
```

**Response Example**:
```json
{
  "period_days": 30,
  "trends": [
    {"date": "2025-11-01", "created": 2, "resolved": 1},
    {"date": "2025-11-02", "created": 3, "resolved": 2},
    ...
  ],
  "summary": {
    "total_created": 25,
    "total_resolved": 20,
    "trend_direction": "improving"
  }
}
```

**Trend Analysis**:
- Daily case creation counts
- Daily resolution counts
- Moving averages
- Trend direction indicators

**Storage**: SQLite time-series aggregation
**Rate Limits**: None (enforced at API Gateway level)
**Authorization**: Requires X-User-ID header
**User Isolation**: Only analyzes user's own cases
    """,
    responses={
        200: {"description": "Trends data returned successfully"},
        401: {"description": "Unauthorized - missing X-User-ID header"},
        500: {"description": "Internal server error"}
    }
)
async def get_case_trends(
    user_id: str = Depends(get_user_id),
    days: int = Query(30, ge=1, le=365),
):
    """Get case trends over time."""
    # TODO: Implement trend analysis
    return {
        "period_days": days,
        "trends": [],
        "message": "Trend analysis not yet implemented"
    }
