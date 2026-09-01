from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth.tenant_context import resolve_tenant_from_jwt


@pytest.mark.asyncio
async def test_resolve_tenant_from_jwt_rejects_invalid_bearer_token(monkeypatch):
    request = SimpleNamespace(headers={"Authorization": "Bearer invalid-token"})

    def raise_bad_token(_token):
        raise ValueError("bad token")

    monkeypatch.setattr("app.auth.jwt_handler.decode_access_token", raise_bad_token)

    with pytest.raises(HTTPException):
        await resolve_tenant_from_jwt(request)
