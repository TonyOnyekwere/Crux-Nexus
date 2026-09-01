"""Architecture gate: OpenAPI contract exposes canonical routes."""

from app.main import app

CORE_ROUTES = [
    "/api/v1/identity/users",
    "/api/v1/identity/login",
    "/api/v1/identity/switch-tenant",
    "/api/v1/identity/storefronts",
    "/api/v1/onboarding/merchant",
    "/api/v1/storefronts",
    "/api/v1/merchant/storefronts",
    "/health/live",
    "/health/ready",
]


def test_openapi_contains_core_routes():
    schema = app.openapi()
    paths = schema["paths"]
    for route in CORE_ROUTES:
        assert route in paths, f"Missing route: {route}"


def test_openapi_artifact_can_be_generated():
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "generate_openapi.py"
    assert script.exists()
