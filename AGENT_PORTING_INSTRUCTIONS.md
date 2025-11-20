# Agent Instructions: Port All Case Endpoints from Monolith

**Branch**: `feature/port-all-case-endpoints`
**Goal**: Port all 26 case endpoints from monolith to microservice with 100% OpenAPI compliance
**Estimated Time**: 6-10 hours

---

## Context

You are porting **proven, tested** case API endpoints from the FaultMaven monolith to the fm-case-service microservice. The monolith code is in `reference/monolith/case.py` (2,804 lines, battle-tested).

**Critical**: The browser extension frontend expects the EXACT same API as defined in `reference/openapi.locked.yaml`. You must implement all 26 endpoints correctly.

---

## Reference Files Provided

All reference files are in the `reference/` directory:

1. **reference/monolith/case.py** - Source code to port from (2,804 lines)
2. **reference/openapi.locked.yaml** - API specification (authoritative)
3. **reference/case-and-session-concepts.md** - Architecture rules (MUST READ)
4. **reference/monolith/api_models.py** - Response models reference
5. **reference/monolith/case_ui.py** - UI models reference

---

## Architectural Rules (CRITICAL)

Read `reference/case-and-session-concepts.md` first. Key principles:

### ✅ DO:
1. **Cases are TOP-LEVEL resources** - URL: `/api/v1/cases/{case_id}`
2. **Authorization via user_id** - Extract from `X-User-ID` header (API gateway provides this)
3. **Verify ownership** - Always check `case.owner_id == user_id`
4. **Use CaseManager** - Microservice uses `CaseManager`, not `ICaseService`
5. **Return complete data** - Don't filter by session

### ❌ DON'T:
1. **NO session binding** - Cases are NOT nested under `/sessions/{session_id}/...`
2. **NO session_id in Case model** - Cases don't store session references
3. **NO session-filtered results** - Return ALL user's cases, not session subset

---

## Target File

**File to edit**: `src/case_service/api/routes/cases.py`

**Current status**: Partial implementation (~810 lines, ~12 endpoints)
**Goal**: Complete implementation (all 26 endpoints)

---

## 26 Endpoints to Port

Use `reference/openapi.locked.yaml` as the authoritative spec. Here's the complete list:

### Core CRUD (6 endpoints)
| Method | Path | Monolith Line | Priority |
|--------|------|---------------|----------|
| POST | `/api/v1/cases` | 246 | P0 |
| GET | `/api/v1/cases` | 325 | P0 |
| GET | `/api/v1/cases/{case_id}` | 417 | P0 |
| PUT | `/api/v1/cases/{case_id}` | 526 | P0 |
| DELETE | `/api/v1/cases/{case_id}` | 198 | P0 |
| GET | `/api/v1/cases/health` | 1526 | P0 |

### Search & Status (2 endpoints)
| Method | Path | Monolith Line | Priority |
|--------|------|---------------|----------|
| POST | `/api/v1/cases/search` | 1073 | P0 |
| POST | `/api/v1/cases/{case_id}/close` | 2158 | P0 |

### UI & Title (2 endpoints)
| Method | Path | Monolith Line | Priority |
|--------|------|---------------|----------|
| GET | `/api/v1/cases/{case_id}/ui` | 468 | P1 |
| POST | `/api/v1/cases/{case_id}/title` | 613 | P1 |

### Queries & Messages (3 endpoints)
| Method | Path | Monolith Line | Priority |
|--------|------|---------------|----------|
| POST | `/api/v1/cases/{case_id}/queries` | 1331 | P0 |
| GET | `/api/v1/cases/{case_id}/queries` | 1460 | P0 |
| GET | `/api/v1/cases/{case_id}/messages` | 1137 | P1 |

### Data Management (4 endpoints)
| Method | Path | Monolith Line | Priority |
|--------|------|---------------|----------|
| GET | `/api/v1/cases/{case_id}/data` | 1563 | P1 |
| POST | `/api/v1/cases/{case_id}/data` | 1661 | P0 |
| GET | `/api/v1/cases/{case_id}/data/{data_id}` | 1614 | P1 |
| DELETE | `/api/v1/cases/{case_id}/data/{data_id}` | 1824 | P1 |

### Files & Evidence (3 endpoints)
| Method | Path | Monolith Line | Priority |
|--------|------|---------------|----------|
| GET | `/api/v1/cases/{case_id}/uploaded-files` | 2266 | P1 |
| GET | `/api/v1/cases/{case_id}/uploaded-files/{file_id}` | 2328 | P1 |
| GET | `/api/v1/cases/{case_id}/evidence/{evidence_id}` | 2403 | P1 |

### Analytics & Reports (6 endpoints)
| Method | Path | Monolith Line | Priority |
|--------|------|---------------|----------|
| GET | `/api/v1/cases/{case_id}/analytics` | 1102 | P1 |
| GET | `/api/v1/cases/{case_id}/report-recommendations` | 1863 | P2 |
| POST | `/api/v1/cases/{case_id}/reports` | 1965 | P2 |
| GET | `/api/v1/cases/{case_id}/reports` | 2010 | P2 |
| GET | `/api/v1/cases/{case_id}/reports/{report_id}/download` | 2066 | P2 |

---

## Porting Process (For Each Endpoint)

### Step 1: Find Monolith Implementation
```bash
# Example: Health endpoint at line 1526
# Open reference/monolith/case.py and go to line 1526
```

### Step 2: Read Complete Implementation
- Understand what the endpoint does
- Note dependencies (models, services, utilities)
- Identify any session-related code (must adapt)

### Step 3: Adapt for Microservice

#### Import Changes
```python
# MONOLITH
from faultmaven.models import Case
from faultmaven.models.api_models import CaseResponse
from faultmaven.utils.serialization import to_json_compatible
from faultmaven.api.v1.dependencies import get_case_service

# MICROSERVICE
from fm_core_lib.models import Case
from case_service.models import CaseResponse
from datetime import datetime, timezone
from case_service.core import CaseManager
```

#### Dependency Changes
```python
# MONOLITH
case_service: ICaseService = Depends(get_case_service)
user_id = await session_service.get_user_from_session(session_id)

# MICROSERVICE
case_manager: CaseManager = Depends(get_case_manager)
user_id: str = Depends(get_user_id)  # From X-User-ID header
```

#### Authorization Pattern
```python
# ALWAYS verify ownership before operations
case = await case_manager.get_case(case_id, user_id)
if not case:
    raise HTTPException(status_code=404, detail="Case not found")
if case.owner_id != user_id:
    raise HTTPException(status_code=403, detail="Not authorized")
```

#### Remove Session Binding
```python
# MONOLITH (WRONG - has session binding)
session_cases = [c for c in all_cases if session_id in c.session_ids]

# MICROSERVICE (CORRECT - no session filtering)
user_cases = await case_manager.list_cases(user_id)
return user_cases  # All user's cases, not session-filtered
```

### Step 4: Handle Missing Dependencies

If monolith code uses services not available in microservice:

```python
# MONOLITH (has access to all services)
data = await data_service.get_data(data_id)
job = await job_service.create_job(...)

# MICROSERVICE (stub with TODO)
# TODO: Cross-service call to data-service pending
return {
    "data_id": data_id,
    "status": "pending",
    "message": "Data service integration pending"
}
```

### Step 5: Add to routes.py

Add the ported endpoint to `src/case_service/api/routes/cases.py`:

```python
@router.get("/health", summary="Get case service health")
async def get_case_service_health():
    """Health check endpoint."""
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
```

---

## Common Patterns

### Pattern 1: Simple Endpoint (no external dependencies)
```python
@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
```

### Pattern 2: Case Retrieval with Auth
```python
@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    case = await case_manager.get_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
```

### Pattern 3: Case Modification with Ownership Check
```python
@router.put("/{case_id}")
async def update_case(
    case_id: str,
    updates: CaseUpdateRequest,
    user_id: str = Depends(get_user_id),
    case_manager: CaseManager = Depends(get_case_manager),
):
    # Get and verify ownership
    case = await case_manager.get_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update
    updated_case = await case_manager.update_case(case_id, updates.dict(exclude_unset=True))
    return updated_case
```

---

## Verification Checklist

After porting ALL endpoints, verify:

### 1. OpenAPI Compliance
```bash
cd /home/swhouse/product
python3 verify_openapi_compliance.py
# Should show: ✅ Implemented: 26/26 (100%)
```

### 2. No Import Errors
```bash
cd /home/swhouse/product/fm-case-service
python3 -m py_compile src/case_service/api/routes/cases.py
# Should succeed with no errors
```

### 3. Architectural Compliance
- ✅ No `session_id` fields in Case model
- ✅ All endpoints use `user_id` from `X-User-ID` header
- ✅ All case operations verify `case.owner_id == user_id`
- ✅ Cases are top-level resources (not nested under sessions)

### 4. Response Models Match Spec
- Check each endpoint's response against `reference/openapi.locked.yaml`
- Ensure field names match exactly
- Ensure data types match

---

## Tips for Success

1. **Start with P0 endpoints** - Core CRUD, queries, search (most important)
2. **Port incrementally** - Do 2-3 endpoints, test, commit, repeat
3. **Don't skip reading** - Read the monolith implementation fully before porting
4. **Use TODOs** - If something requires cross-service calls, add `# TODO:` and stub
5. **Keep it simple** - If monolith logic is complex and depends on unavailable services, simplify
6. **Test after each batch** - Run the compliance check after every 5-6 endpoints

---

## Commit Strategy

Commit after each logical group:

```bash
git add src/case_service/api/routes/cases.py
git commit -m "Port core CRUD endpoints (POST/GET/PUT/DELETE cases, health, search)"

git add src/case_service/api/routes/cases.py
git commit -m "Port query endpoints (POST/GET queries, GET messages)"

# etc.
```

---

## Success Criteria

When done:
- ✅ All 26 endpoints from `reference/openapi.locked.yaml` implemented
- ✅ OpenAPI compliance check shows 100% (26/26)
- ✅ No Python syntax errors
- ✅ No session binding (architectural compliance)
- ✅ All endpoints use proper user_id authorization
- ✅ Code committed to branch `feature/port-all-case-endpoints`

---

## Questions?

If you encounter issues:
1. Check `reference/case-and-session-concepts.md` for architecture guidance
2. Look at existing endpoints in the file for patterns
3. Use TODOs for complex dependencies
4. Prioritize P0 endpoints over P2

---

## Ready to Start?

Begin with **Core CRUD** endpoints (6 endpoints, P0 priority):
1. GET `/health` (line 1526)
2. POST `/api/v1/cases` (line 246)
3. GET `/api/v1/cases` (line 325)
4. GET `/api/v1/cases/{case_id}` (line 417)
5. PUT `/api/v1/cases/{case_id}` (line 526)
6. DELETE `/api/v1/cases/{case_id}` (line 198)

Good luck! 🚀
