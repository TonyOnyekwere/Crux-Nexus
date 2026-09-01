"""Generate committed OpenAPI contract artifact from FastAPI app."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost:5432/crux",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "12345678901234567890123456789012")
os.environ.setdefault("JWT_SECRET_KEY", "12345678901234567890123456789012")

from app.main import app  # noqa: E402

OUTPUT = ROOT / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OpenAPI spec written to {OUTPUT}")


if __name__ == "__main__":
    main()
