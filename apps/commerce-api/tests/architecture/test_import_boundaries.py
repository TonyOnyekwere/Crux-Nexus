"""Architecture gate: import boundary configuration."""

from pathlib import Path


def test_importlinter_config_exists():
    config = Path(__file__).resolve().parents[2] / ".importlinter"
    assert config.exists(), "Import linter config required for CI architecture gate"
