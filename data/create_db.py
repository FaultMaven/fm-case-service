#!/usr/bin/env python3
"""Create SQLite database with 10-table hybrid schema."""

import sqlite3
import sys
from pathlib import Path

# Read schema SQL
schema_file = Path(__file__).parent / "init_schema.sql"
db_file = Path(__file__).parent / "faultmaven.db"

print(f"Creating database: {db_file}")
print(f"Using schema: {schema_file}")

# Delete existing database
if db_file.exists():
    db_file.unlink()
    print(f"✓ Deleted existing database")

# Read schema
with open(schema_file) as f:
    schema_sql = f.read()

# Create database
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

try:
    # Execute schema
    cursor.executescript(schema_sql)
    conn.commit()

    # Verify tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()

    print("\n✅ Database created successfully!")
    print(f"\nTables created ({len(tables)}):")
    for table in tables:
        print(f"  ✓ {table[0]}")

    # Verify indices
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    indices = cursor.fetchall()
    print(f"\nIndices created ({len(indices)}):")
    for idx in indices:
        if not idx[0].startswith('sqlite_'):  # Skip auto-created indices
            print(f"  ✓ {idx[0]}")

    sys.exit(0)

except Exception as e:
    print(f"\n❌ Error creating database: {e}")
    sys.exit(1)

finally:
    conn.close()
