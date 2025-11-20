# Quick Start for Agent - Case Endpoint Porting

**Repository**: `/home/swhouse/product/fm-case-service`
**Branch**: `feature/port-all-case-endpoints`
**Task**: Port all 26 case API endpoints from monolith to microservice

---

## Setup Complete ✅

All reference materials and instructions are ready in this branch.

---

## What You Need to Do

### 1. Read Instructions (10 minutes)
📖 **AGENT_PORTING_INSTRUCTIONS.md** - Complete porting guide with:
- Architecture rules (CRITICAL - read first)
- 26 endpoints to port (with line numbers)
- Step-by-step porting process
- Code examples and patterns
- Verification checklist

### 2. Port Endpoints (6-10 hours)
📝 **File to edit**: `src/case_service/api/routes/cases.py`

For each endpoint:
1. Find implementation in `reference/monolith/case.py` (line number provided)
2. Read and understand the code
3. Adapt for microservice (imports, dependencies, auth)
4. Add to `src/case_service/api/routes/cases.py`
5. Commit after each batch

### 3. Verify Completion
✅ Run verification script:
```bash
cd /home/swhouse/product/fm-case-service
python3 verify_compliance.py
```

**Target**: Shows `✅ Implemented: 26/26 (100%)`

---

## Reference Files Provided

All in `reference/` directory:

| File | Purpose | Size |
|------|---------|------|
| `monolith/case.py` | Source code to port from | 2,804 lines |
| `openapi.locked.yaml` | API specification (authoritative) | Complete spec |
| `case-and-session-concepts.md` | Architecture rules (READ FIRST) | Design doc |
| `monolith/api_models.py` | Response models reference | Models |
| `monolith/case_ui.py` | UI models reference | Models |

---

## Priority Order

### P0 - Core (8 endpoints) - MUST HAVE
- GET `/health`
- POST/GET/PUT/DELETE `/api/v1/cases` (CRUD)
- POST `/search`
- POST `/{case_id}/close`
- POST/GET `/{case_id}/queries`

### P1 - Important (10 endpoints)
- GET `/{case_id}/ui`
- POST `/{case_id}/title`
- GET `/{case_id}/messages`
- Data endpoints (4): GET/POST/GET/DELETE `/data`
- Files endpoints (3): uploaded-files, file details, evidence

### P2 - Reports (8 endpoints)
- Analytics, report generation, downloads

---

## Success Criteria

When done:
- ✅ All 26 endpoints implemented
- ✅ `verify_compliance.py` shows 100%
- ✅ No Python syntax errors
- ✅ No session binding (architecture compliant)
- ✅ Committed to branch

---

## Quick Test

Check current status:
```bash
cd /home/swhouse/product/fm-case-service
python3 verify_compliance.py
```

Should show current endpoint count and what's missing.

---

## Questions?

Everything you need is in **AGENT_PORTING_INSTRUCTIONS.md**.

Start with P0 endpoints and work through systematically.

Good luck! 🚀
