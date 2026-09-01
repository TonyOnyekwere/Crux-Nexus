"""
CI gate: fail if banned payment/architecture identifiers appear in production code.
"""

import sys
from pathlib import Path

BANNED_IDENTIFIERS = [
    "payment_destinations",
    "create_payment_destination",
    "virtual account generation",
    "escrow wallet",
    "PaymentDestination",
]

SCAN_ROOT = Path(__file__).resolve().parent.parent / "app"
SKIP_PARTS = {"__pycache__", ".git"}


def scan_file(path: Path) -> list[str]:
    violations = []
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return violations
    for identifier in BANNED_IDENTIFIERS:
        if identifier in content:
            violations.append(f"{path}: contains banned identifier '{identifier}'")
    return violations


def main() -> None:
    violations: list[str] = []
    for path in SCAN_ROOT.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        violations.extend(scan_file(path))

    if violations:
        print("Frozen identifier ban FAILED:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print("Frozen identifier ban PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
