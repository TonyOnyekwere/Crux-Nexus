"""Migration smoke test — empty database through alembic head."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_migrations_apply_from_base_to_head():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL required for migration smoke test")

    env = os.environ.copy()
    env["DATABASE_URL"] = database_url

    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert downgrade.returncode == 0, downgrade.stderr

    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert upgrade.returncode == 0, upgrade.stderr

    import_check = subprocess.run(
        [sys.executable, "-c", "import app.main; print('ok')"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert import_check.returncode == 0, import_check.stderr
    assert "ok" in import_check.stdout
