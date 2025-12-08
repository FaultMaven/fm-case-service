# Case Status Enum Correction

**Date**: 2025-12-08
**Issue**: Mismatch between PostgreSQL schema and fm-core-lib model

---

## Problem Identified

The source PostgreSQL schema file has **inconsistent** status enum values:

### ❌ Source File (Wrong - 7 values)
**File**: `FaultMaven-Mono/docs/schema/001_initial_hybrid_schema.sql`
```sql
CREATE TYPE case_status AS ENUM (
    'consulting',
    'problem_verification',      -- ❌ NOT in fm-core-lib
    'root_cause_analysis',        -- ❌ NOT in fm-core-lib
    'solution_implementation',    -- ❌ NOT in fm-core-lib
    'resolved',
    'closed',
    'archived'                    -- ❌ NOT in fm-core-lib
);
```

### ✅ fm-core-lib Model (Correct - 4 values)
**File**: `fm-core-lib/src/fm_core_lib/models/case.py`
```python
class CaseStatus(str, Enum):
    CONSULTING = "consulting"      # ✅
    INVESTIGATING = "investigating" # ✅
    RESOLVED = "resolved"          # ✅
    CLOSED = "closed"              # ✅
```

---

## ✅ Already Corrected

The restoration process **correctly used the fm-core-lib enum values** instead of the outdated PostgreSQL schema values:

### ✅ Alembic Migration (Correct)
**File**: `alembic/versions/20250208_initial_hybrid_schema.py` (Lines 55-59)
```python
case_status = sa.Enum(
    'consulting', 'investigating', 'resolved', 'closed',  # ✅ Matches fm-core-lib
    name='case_status',
    create_type=True
)
```

### ✅ SQLite Schema (Correct)
**File**: `data/init_schema.sql` (Line 14)
```sql
status TEXT NOT NULL DEFAULT 'consulting'
CHECK(status IN ('consulting', 'investigating', 'resolved', 'closed'))  -- ✅ Matches fm-core-lib
```

### ✅ Integration Tests (Verified)
**File**: `data/test_case_creation.py`

Test results confirm:
- ✅ Status enum accepts: `consulting, investigating, resolved, closed`
- ✅ Status enum **rejects**: `active, archived, problem_verification, root_cause_analysis, solution_implementation`

```
✅ Test 3: Verify wrong status values are rejected
   Database correctly rejected wrong status 'active'
   Error: CHECK constraint failed: status IN ('consulting', 'investigating', 'resolved', 'closed')
```

---

## Why the Discrepancy Exists

The PostgreSQL schema file (`001_initial_hybrid_schema.sql`) appears to be from an **older design iteration** that had a more detailed workflow with explicit status values for each investigation phase:

1. `consulting` → Initial consultation phase
2. `problem_verification` → Verifying the problem exists
3. `root_cause_analysis` → Analyzing root cause
4. `solution_implementation` → Implementing solution
5. `resolved` → Solution verified
6. `closed` → Case closed
7. `archived` → Case archived

However, **fm-core-lib simplified this** to just 4 status values, using the JSONB columns (`problem_verification`, `working_conclusion`, `root_cause_conclusion`, etc.) to track the detailed workflow state instead of separate status enum values.

This is a **better design** because:
- ✅ Simpler status lifecycle
- ✅ Flexible phase tracking via JSONB
- ✅ Easier to understand and maintain
- ✅ Matches actual fm-core-lib implementation

---

## Verification

All created schemas use the **correct 4-value enum**:

| Component | Status Enum | Correct? |
|-----------|-------------|----------|
| fm-core-lib Case model | `consulting, investigating, resolved, closed` | ✅ Source of truth |
| Alembic migration (Python) | `consulting, investigating, resolved, closed` | ✅ Matches |
| SQLite schema (SQL) | `consulting, investigating, resolved, closed` | ✅ Matches |
| PostgreSQL source (SQL) | `consulting, problem_verification, ...` (7 values) | ❌ Outdated |
| Integration tests | Rejects wrong values, accepts correct ones | ✅ Verified |

---

## Recommendation

### ✅ No Action Required

The restoration is **correct as-is**. All runtime components use the correct 4-value enum from fm-core-lib.

### 📝 Optional: Update Source Schema

If you want to update the source PostgreSQL schema file to match fm-core-lib (for documentation purposes):

**File to update**: `FaultMaven-Mono/docs/schema/001_initial_hybrid_schema.sql`

**Change**:
```sql
-- BEFORE (7 values)
CREATE TYPE case_status AS ENUM (
    'consulting',
    'problem_verification',
    'root_cause_analysis',
    'solution_implementation',
    'resolved',
    'closed',
    'archived'
);

-- AFTER (4 values - matches fm-core-lib)
CREATE TYPE case_status AS ENUM (
    'consulting',
    'investigating',
    'resolved',
    'closed'
);
```

But this is **purely cosmetic** - the actual implementation already uses the correct values.

---

## Conclusion

### ✅ Issue Already Resolved

The case status enum **has been corrected** in all runtime components:
- ✅ Alembic migration uses correct 4 values
- ✅ SQLite schema uses correct 4 values
- ✅ Integration tests verify correct values
- ✅ fm-core-lib model is the source of truth

The PostgreSQL schema file in FaultMaven-Mono is **documentation only** and doesn't affect the fm-case-service runtime. All actual database schemas created during restoration use the **correct 4-value enum**.

**No further action required.**

---

**Status**: ✅ **RESOLVED**
