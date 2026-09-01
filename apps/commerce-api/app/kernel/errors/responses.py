from typing import Any


def error_response(
    *,
    code: str,
    message: str,
    details: dict | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    if request_id:
        payload["error"]["request_id"] = request_id
    return payload
