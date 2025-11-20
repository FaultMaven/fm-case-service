# Task: Port All Case API Endpoints from Monolith to Microservice

## Location
- **Repository**: `/home/swhouse/product/fm-case-service`
- **Branch**: `feature/port-all-case-endpoints`
- **File to Edit**: `src/case_service/api/routes/cases.py`

## Goal
Port ALL 26 case API endpoints from the proven monolith implementation to ensure the browser extension frontend works correctly.

**Current**: 9/25 endpoints implemented (36%)
**Target**: 25/25 endpoints implemented (100%)

## Instructions

### Step 1: Read the Architecture Rules (5 minutes)
```bash
cat reference/case-and-session-concepts.md
```
**Key Rules**:
- Cases are TOP-LEVEL resources (NOT nested under sessions)
- Use `user_id` from `X-User-ID` header for auth
- NO `session_id` in Case model
- Always verify `case.owner_id == user_id`

### Step 2: Read the Detailed Guide (10 minutes)
```bash
cat AGENT_PORTING_INSTRUCTIONS.md
```
This has everything: endpoint list, line numbers, code patterns, examples.

### Step 3: Port Each Endpoint
For each missing endpoint:

1. **Find it** in `reference/monolith/case.py` (line numbers in AGENT_PORTING_INSTRUCTIONS.md)
2. **Read** the complete implementation
3. **Adapt** the code:
   - Change imports: `faultmaven.*` → `case_service.*` or `fm_core_lib.*`
   - Change dependencies: `ICaseService` → `CaseManager`
   - Change auth: session-based → `user_id` from header
   - Remove any session binding logic
4. **Add** to `src/case_service/api/routes/cases.py`
5. **Commit** after every 3-5 endpoints

### Step 4: Verify When Done
```bash
python3 verify_compliance.py
```
Should show: **✅ Implemented: 25/25 (100%)**

## Priority Order

### Must Have (P0) - 14 endpoints
- GET `/health`
- POST/GET/PUT/DELETE `/api/v1/cases` (create, list, get, update, delete)
- POST `/search`
- POST `/{case_id}/close`
- POST/GET `/{case_id}/queries` (submit query, list queries)
- POST `/{case_id}/data` (upload data)
- GET `/{case_id}/messages`

### Important (P1) - 6 endpoints
- GET `/{case_id}/ui`
- POST `/{case_id}/title`
- GET/GET/DELETE `/{case_id}/data` and `/{case_id}/data/{data_id}`
- GET `/{case_id}/uploaded-files`
- GET `/{case_id}/evidence/{evidence_id}`

### Nice to Have (P2) - 5 endpoints
- GET `/{case_id}/analytics`
- GET/POST/GET `/{case_id}/reports` (list, generate, download)

## Quick Reference: Code Pattern

```python
# Typical endpoint structure
@router.get("/{case_id}", summary="Get case")
async def get_case(
    case_id: str,
    user_id: str = Depends(get_user_id),  # From X-User-ID header
    case_manager: CaseManager = Depends(get_case_manager),
):
    """Get case by ID with authorization check."""
    case = await case_manager.get_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return case
```

## Common Import Changes

```python
# MONOLITH → MICROSERVICE
from faultmaven.models import Case → from fm_core_lib.models import Case
from faultmaven.models.api_models import CaseResponse → from case_service.models import CaseResponse
from faultmaven.api.v1.dependencies import get_case_service → from case_service.core import CaseManager
```

## When You're Done

1. Run: `python3 verify_compliance.py` → Should show 100%
2. Push: `git push origin feature/port-all-case-endpoints`
3. Report: "All 25 case endpoints ported and verified"

## Questions?
All details are in `AGENT_PORTING_INSTRUCTIONS.md`

**Estimated Time**: 6-10 hours
**Start with**: P0 endpoints (health, CRUD, queries)

Good luck! 🚀
