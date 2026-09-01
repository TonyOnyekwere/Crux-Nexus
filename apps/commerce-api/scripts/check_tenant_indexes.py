"""
CI gate: verify tenant-scoped tables declare tenant_id-first indexes in migrations.

When TENANT_SCOPED_TABLES is populated, this script validates that Alembic
migrations create indexes beginning with tenant_id for those tables.
"""

import re
import sys
from pathlib import Path

from app.database.tenant_scope import TENANT_SCOPED_TABLES

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations" / "versions"

# Matches CREATE INDEX ... ON table_name (tenant_id, ...)
TENANT_INDEX_PATTERN = re.compile(
    r"create_index\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"](\w+)['\"]\s*,\s*\[\s*['\"]tenant_id['\"]",
    re.IGNORECASE,
)


def find_tenant_first_indexes() -> set[str]:
    indexed_tables: set[str] = set()
    for migration_file in MIGRATIONS_DIR.glob("*.py"):
        content = migration_file.read_text(encoding="utf-8")
        for match in TENANT_INDEX_PATTERN.finditer(content):
            indexed_tables.add(match.group(1))
    return indexed_tables


def main() -> None:
    if not TENANT_SCOPED_TABLES:
        print(
            "Tenant index check PASSED (no tenant-scoped tables registered yet; "
            "gate will enforce when tables are added to TENANT_SCOPED_TABLES)"
        )
        sys.exit(0)

    indexed = find_tenant_first_indexes()
    missing = [table for table in TENANT_SCOPED_TABLES if table not in indexed]

    if missing:
        print("Tenant-first index check FAILED:")
        for table in missing:
            print(f"  - {table}: no tenant_id-first index found in migrations")
        sys.exit(1)

    print(f"Tenant-first index check PASSED for {len(TENANT_SCOPED_TABLES)} table(s)")
    sys.exit(0)


if __name__ == "__main__":
    main()
