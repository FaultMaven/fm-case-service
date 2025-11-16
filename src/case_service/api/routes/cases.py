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


async def get_db_session() -> AsyncSession:
    """Dependency to get database session."""
    async for session in db_client.get_session():
        yield session


async def get_case_manager(
    db_session: AsyncSession = Depends(get_db_session),
) -> CaseManager:
    """Dependency to get case manager."""
    return CaseManager(db_session)


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


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("/{case_id}", response_model=CaseResponse)
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


@router.put("/{case_id}", response_model=CaseResponse)
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


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.get("", response_model=CaseListResponse)
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


@router.get("/session/{session_id}", response_model=CaseListResponse)
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


@router.post("/{case_id}/status", response_model=CaseResponse)
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
