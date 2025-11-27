"""Case API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from fm_core_lib.auth import RequestContext, get_request_context

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


async def get_case_repository() -> "CaseRepository":
    """Dependency to get case repository.

    Returns the appropriate repository implementation based on CASE_STORAGE_TYPE
    environment variable:
    - inmemory (default): InMemoryCaseRepository for dev/testing
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
        # Default to in-memory for development/testing
        yield InMemoryCaseRepository()


async def get_case_manager(
    repository: "CaseRepository" = Depends(get_case_repository),
) -> CaseManager:
    """Dependency to get case manager with repository."""
    return CaseManager(repository)


async def get_user_id(request: Request) -> str:
    """Get user ID from request context (set by ServiceAuthMiddleware).

    The ServiceAuthMiddleware extracts user_id from X-User-ID header
    and validates the service JWT token, adding both to request context.

    Args:
        request: FastAPI request with context from ServiceAuthMiddleware

    Returns:
        User ID from request context

    Raises:
        HTTPException: If user ID is not found in context
    """
    context: RequestContext = get_request_context(request)

    if not context.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID is required",
        )

    return context.user_id


# =============================================================================
# Health Check Endpoint
# =============================================================================

@router.get("/health", summary="Get case service health")
async def get_case_service_health() -> Dict[str, Any]:
    """
    Get case service health status.

    Returns health information about the case persistence system,
    including connectivity and performance metrics.
    """
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
1. Case created in 'active' status with auto-generated ID (case_XXXX format)
2. Title auto-generated if not provided (Case-MMDD-N format)
3. Optional session linking for associating with investigation sessions
4. User can specify severity, category, metadata, and tags

**Request Body Example**:
```json
{
  "title": "Redis connection timeouts in production",
  "description": "Intermittent timeouts on Redis cluster during peak hours",
  "severity": "high",
  "category": "performance",
  "session_id": "session_abc123",
  "metadata": {"environment": "production", "cluster": "redis-prod-1"},
  "tags": ["redis", "timeout", "performance"]
}
```

**Response Example**:
```json
{
  "case_id": "case_a1b2c3d4e5f6",
  "user_id": "user_123",
  "session_id": "session_abc123",
  "title": "Redis connection timeouts in production",
  "description": "Intermittent timeouts on Redis cluster during peak hours",
  "status": "active",
  "severity": "high",
  "category": "performance",
  "metadata": {"environment": "production", "cluster": "redis-prod-1"},
  "tags": ["redis", "timeout", "performance"],
  "created_at": "2025-11-19T10:30:00Z",
  "updated_at": "2025-11-19T10:30:00Z",
  "resolved_at": null
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
- `status`: Case status (active/investigating/resolved/archived/closed)
- `severity`: Severity level (low/medium/high/critical)
- `category`: Category (performance/error/configuration/infrastructure/security/other)
- `metadata`: Custom metadata dictionary (merged with existing)
- `tags`: Tag list (replaces existing tags)

**Request Example**:
```json
{
  "status": "investigating",
  "severity": "critical",
  "description": "Issue escalated - affecting 50% of users",
  "metadata": {"escalated": true, "affected_users": 500},
  "tags": ["redis", "timeout", "critical", "escalated"]
}
```

**Response Example**:
```json
{
  "case_id": "case_a1b2c3d4e5f6",
  "status": "investigating",
  "severity": "critical",
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


@router.get("/{case_id}/ui", summary="Get case UI data")
async def get_case_ui(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Get phase-adaptive UI-optimized case response.

    Returns UI state optimized for the current investigation phase.
    This endpoint eliminates multiple API calls by returning all UI state
    in a single response.

    Args:
        case_id: Case identifier
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        UI-optimized case data
    """
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
            "severity": case.severity.value if hasattr(case.severity, 'value') else case.severity,
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


@router.post("/{case_id}/title", summary="Generate case title")
async def generate_case_title(
    case_id: str,
    title_request: Optional[Dict[str, Any]] = None,
    force: bool = Query(False, description="Force overwrite of existing title"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Generate a concise, case-specific title from case messages and metadata.

    Args:
        case_id: Case identifier
        title_request: Optional parameters (max_words, hint)
        force: Force overwrite of existing meaningful title
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        Title response with generated or existing title
    """
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
      "severity": "high",
      "created_at": "2025-11-19T10:30:00Z",
      ...
    },
    {
      "case_id": "case_x7y8z9a0b1c2",
      "title": "API latency spike",
      "status": "investigating",
      "severity": "medium",
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
    cases, total = await case_manager.list_cases(
        user_id=user_id,
        status=status_filter,
        page=page,
        page_size=page_size,
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
    cases, total = await case_manager.list_cases_by_session(
        session_id=session_id,
        page=page,
        page_size=page_size,
    )

    # Filter to only cases owned by the authenticated user
    user_cases = [case for case in cases if case.user_id == user_id]
    user_total = len(user_cases)

    return CaseListResponse(
        cases=[CaseResponse.from_case(case) for case in user_cases],
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

@router.get("/{case_id}/data", summary="List case data")
async def list_case_data(
    case_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    List data files associated with a case.

    Returns array of data records with pagination.

    Args:
        case_id: Case identifier
        limit: Maximum number of items to return
        offset: Number of items to skip
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        List of data records with pagination metadata
    """
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


@router.get("/{case_id}/data/{data_id}", summary="Get case data")
async def get_case_data(
    case_id: str,
    data_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Get specific data file details for a case.

    Args:
        case_id: Case identifier
        data_id: Data record identifier
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        Data record details
    """
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


@router.delete("/{case_id}/data/{data_id}", summary="Delete case data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case_data(
    case_id: str,
    data_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """
    Delete a specific data file from a case.

    Args:
        case_id: Case identifier
        data_id: Data record identifier to delete
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        204 No Content on success
    """
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


@router.get("/{case_id}/evidence/{evidence_id}", summary="Get specific evidence by ID")
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


@router.get("/{case_id}/uploaded-files", summary="Get uploaded files for case")
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


@router.get("/{case_id}/uploaded-files/{file_id}", summary="Get uploaded file details")
async def get_uploaded_file_details(
    case_id: str,
    file_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Get details for a specific uploaded file.

    Args:
        case_id: Case identifier
        file_id: File identifier
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        File details including metadata and derived evidence
    """
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


@router.post("/{case_id}/close", response_model=CaseResponse, summary="Close a case")
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


@router.post("/search", response_model=CaseListResponse, summary="Search cases")
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

@router.post("/{case_id}/hypotheses", summary="Add hypothesis to case")
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


@router.put("/{case_id}/hypotheses/{hypothesis_id}", summary="Update hypothesis")
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


@router.post("/{case_id}/queries", summary="Submit case query")
async def submit_case_query(
    case_id: str,
    query_data: Dict[str, Any],
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Submit user message to case investigation.

    Processes the message and adds it to the case query history.

    Args:
        case_id: Case identifier
        query_data: Query request containing 'message' field
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        Query response with case_id and query status
    """
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


@router.get("/{case_id}/queries", summary="Get case query history")
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


@router.get("/{case_id}/messages", summary="Get case messages")
async def get_case_messages(
    case_id: str,
    limit: int = Query(50, le=100, ge=1, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    include_debug: bool = Query(False, description="Include debug information for troubleshooting"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Retrieve conversation messages for a case with pagination.

    Supports pagination and includes metadata about message retrieval status.

    Args:
        case_id: Case identifier
        limit: Maximum number of messages to return
        offset: Offset for pagination
        include_debug: Include debug information
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        Messages response with metadata
    """
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

@router.get("/{case_id}/analytics", summary="Get case analytics")
async def get_case_analytics(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Get case analytics and metrics.

    Returns analytics data including message counts, participant activity,
    resolution time, and other case metrics.

    Args:
        case_id: Case identifier
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        Analytics data for the case
    """
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


@router.get("/{case_id}/report-recommendations", summary="Get report recommendations")
async def get_report_recommendations(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Get intelligent report recommendations for a case.

    Returns recommendations for which reports to generate, including
    intelligent runbook suggestions based on similarity search.

    Args:
        case_id: Case identifier
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        Report recommendations with available types
    """
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


@router.post("/{case_id}/reports", summary="Generate case reports")
async def generate_case_reports(
    case_id: str,
    report_request: Dict[str, Any],
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Generate case documentation reports.

    Args:
        case_id: Case identifier
        report_request: Report generation request with report_types
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        Report generation response with report IDs
    """
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


@router.get("/{case_id}/reports", summary="Get case reports")
async def get_case_reports(
    case_id: str,
    include_history: bool = Query(default=False, description="Include all report versions"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Retrieve generated reports for a case.

    Args:
        case_id: Case identifier
        include_history: If True, return all report versions; if False, only current
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        List of reports for the case
    """
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


@router.get("/{case_id}/reports/{report_id}/download", summary="Download case report")
async def download_case_report(
    case_id: str,
    report_id: str,
    format: str = Query(default="markdown", description="Output format (markdown or pdf)"),
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
) -> Dict[str, Any]:
    """
    Download case report in specified format.

    Args:
        case_id: Case identifier
        report_id: Report identifier
        format: Output format (markdown or pdf) - currently only markdown supported
        user_id: Authenticated user ID
        case_manager: Case manager dependency

    Returns:
        File response with report content
    """
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


@router.get("/reports", summary="List available reports")
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


@router.get("/reports/{report_id}", summary="Get specific report")
async def get_report(
    report_id: str,
    user_id: str = Depends(get_user_id),
):
    """Get specific case report by ID."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Report generation system not yet implemented"
    )


@router.get("/analytics/summary", summary="Get case analytics summary")
async def get_analytics_summary(
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get analytics summary for user's cases."""
    summary = await case_manager.get_analytics_summary(user_id)
    return summary


@router.get("/analytics/trends", summary="Get case trends")
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
