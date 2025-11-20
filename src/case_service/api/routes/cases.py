"""Case API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


async def get_case_repository() -> "CaseRepository":
    """Dependency to get case repository.

    Returns the appropriate repository implementation based on configuration.
    For now, uses InMemoryCaseRepository for development.
    TODO: Switch to PostgreSQLHybridCaseRepository for production.
    """
    from case_service.infrastructure.persistence import InMemoryCaseRepository
    # TODO: Use env var to select repository type
    # if os.getenv("REPOSITORY_TYPE") == "postgres_hybrid":
    #     from case_service.infrastructure.persistence import PostgreSQLHybridCaseRepository
    #     async for session in db_client.get_session():
    #         yield PostgreSQLHybridCaseRepository(session)
    # else:
    return InMemoryCaseRepository()


async def get_case_manager(
    repository: "CaseRepository" = Depends(get_case_repository),
) -> CaseManager:
    """Dependency to get case manager with repository."""
    return CaseManager(repository)


async def get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    """Get user ID from gateway headers.

    Args:
        x_user_id: User ID from X-User-ID header set by gateway

    Returns:
        User ID

    Raises:
        HTTPException: If user ID header is missing
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID header (X-User-ID) is required",
        )
    return x_user_id


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


# =============================================================================
# Reports & Analytics Endpoints (Phase 6.3)
# =============================================================================

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
