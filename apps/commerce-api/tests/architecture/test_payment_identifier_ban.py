"""Architecture gate: banned payment identifiers."""

from pathlib import Path

BANNED = [
    "payment_destinations",
    "create_payment_destination",
    "PaymentDestination",
]


def test_no_banned_payment_identifiers_in_app_code():
    app_root = Path(__file__).resolve().parents[2] / "app"
    violations = []
    for path in app_root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        for identifier in BANNED:
            if identifier in content:
                violations.append(f"{path.name}: {identifier}")
    assert not violations, f"Banned identifiers found: {violations}"
