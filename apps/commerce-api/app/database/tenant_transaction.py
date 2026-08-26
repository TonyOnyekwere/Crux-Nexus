from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def tenant_transaction(
    session: AsyncSession,
    tenant_id: UUID,
) -> AsyncIterator[AsyncSession]:
    """
    Execute tenant-scoped database work inside one PostgreSQL transaction.

    The tenant context is transaction-local and cannot survive after
    commit or rollback.
    """

    async with session.begin():

        await session.execute(
            text(
                """
                SELECT set_config(
                    'app.current_tenant_id',
                    :tenant_id,
                    true
                )
                """
            ),
            {
                "tenant_id": str(tenant_id),
            },
        )

        yield session
