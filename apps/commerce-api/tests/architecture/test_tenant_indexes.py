"""Architecture gate: tenant-first index lint script."""

from pathlib import Path


def test_tenant_index_checker_exists():
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_tenant_indexes.py"
    assert script.exists()


def test_tenant_scoped_tables_documented_in_registry():
    from app.database import tenant_scope

    assert hasattr(tenant_scope, "TENANT_SCOPED_TABLES")
