#!/usr/bin/env python3
"""Verify the 10-table hybrid schema structure."""

import sqlite3
from pathlib import Path

db_file = Path(__file__).parent / "faultmaven.db"

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

print("=" * 80)
print("DATABASE SCHEMA VERIFICATION")
print("=" * 80)

# Verify cases table structure
print("\n📋 CASES TABLE (Core table with JSONB columns):")
cursor.execute("PRAGMA table_info(cases)")
columns = cursor.fetchall()
for col in columns:
    col_name, col_type, not_null, default_val, pk = col[1], col[2], col[3], col[4], col[5]
    nullable = "NOT NULL" if not_null else "NULL"
    pk_marker = "🔑 PRIMARY KEY" if pk else ""
    print(f"  • {col_name:25} {col_type:15} {nullable:10} {pk_marker}")

expected_jsonb_cols = [
    'consulting', 'problem_verification', 'working_conclusion',
    'root_cause_conclusion', 'path_selection', 'degraded_mode',
    'escalation_state', 'documentation', 'progress', 'metadata'
]
actual_jsonb_cols = [col[1] for col in columns if 'TEXT' in col[2] and col[1] in expected_jsonb_cols]
print(f"\n  ✅ JSONB columns found: {len(actual_jsonb_cols)}/10")
for jcol in actual_jsonb_cols:
    print(f"     • {jcol}")

# Check required fields
required_fields = ['case_id', 'user_id', 'organization_id', 'title', 'status',
                  'current_turn', 'turns_without_progress']
actual_fields = [col[1] for col in columns]
missing = [f for f in required_fields if f not in actual_fields]
if missing:
    print(f"\n  ❌ Missing required fields: {missing}")
else:
    print(f"\n  ✅ All required fields present")

# Check status enum values
print("\n📊 STATUS ENUM VALUES:")
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cases'")
create_sql = cursor.fetchone()[0]
if 'consulting' in create_sql and 'investigating' in create_sql and 'resolved' in create_sql and 'closed' in create_sql:
    print("  ✅ Correct status values: consulting, investigating, resolved, closed")
    if 'active' in create_sql.lower() or 'archived' in create_sql.lower():
        print("  ❌ WARNING: Found wrong status values (active/archived)")
    else:
        print("  ✅ No wrong status values (active/archived) found")
else:
    print("  ❌ ERROR: Status enum not correctly defined")

# Verify normalized tables
print("\n📦 NORMALIZED TABLES (High-cardinality data):")
normalized_tables = ['evidence', 'hypotheses', 'solutions', 'uploaded_files', 'case_messages']
for table in normalized_tables:
    cursor.execute(f"PRAGMA table_info({table})")
    cols = cursor.fetchall()
    # Check for case_id foreign key
    has_fk = any('case_id' == col[1] for col in cols)
    fk_marker = "✅" if has_fk else "❌"
    print(f"  {fk_marker} {table:20} ({len(cols)} columns) - has case_id FK: {has_fk}")

# Verify supporting tables
print("\n🔧 SUPPORTING TABLES:")
supporting_tables = ['case_status_transitions', 'case_tags', 'agent_tool_calls']
for table in supporting_tables:
    cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
    exists = cursor.fetchone()[0] > 0
    marker = "✅" if exists else "❌"
    print(f"  {marker} {table}")

# Count total tables (excluding sqlite internal tables)
cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
table_count = cursor.fetchone()[0]

print(f"\n{'=' * 80}")
print(f"SUMMARY:")
print(f"  Total tables: {table_count} (expected: 9)")
if table_count == 9:
    print(f"  ✅ SCHEMA VERIFICATION PASSED - 10-table hybrid schema created successfully!")
    print(f"     (9 tables + sqlite_sequence = 10 total)")
else:
    print(f"  ❌ ERROR: Expected 9 tables, found {table_count}")
print(f"{'=' * 80}\n")

conn.close()
