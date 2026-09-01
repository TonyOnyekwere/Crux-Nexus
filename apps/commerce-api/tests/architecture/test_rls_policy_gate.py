"""Architecture gate: honest RLS status reporting."""

from app.database.tenant_scope import TENANT_SCOPED_TABLES


def test_tenant_scoped_registry_empty_in_phase_0():
    assert len(TENANT_SCOPED_TABLES) == 0


def test_rls_gate_documents_vacuous_pass_when_registry_empty():
    from pathlib import Path

    tenant_scope = Path(__file__).resolve().parents[2] / "app" / "database" / "tenant_scope.py"
    content = tenant_scope.read_text(encoding="utf-8")
    assert "VACUOUS" in content or "vacuous" in content.lower()
