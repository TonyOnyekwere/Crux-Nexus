from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_user import (
    MerchantAccountUser,
    MerchantUserRole,
)


class MerchantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_merchant_for_user(
        self,
        user_id: UUID,
        *,
        role: MerchantUserRole | None = MerchantUserRole.OWNER,
    ) -> MerchantAccount | None:
        """Return the most recently created merchant for a user.

        The data model allows a user to be linked to multiple merchant accounts
        over time, especially during onboarding retries or historical repairs.
        In those cases, a strict scalar-one lookup raises MultipleResultsFound.
        The API is expected to operate on the user's active merchant context, so
        we pick the newest merchant as the authoritative account.
        """
        query = (
            select(MerchantAccount)
            .join(
                MerchantAccountUser,
                MerchantAccountUser.merchant_account_id == MerchantAccount.id,
            )
            .where(MerchantAccountUser.user_id == user_id)
            .order_by(MerchantAccount.created_at.desc(), MerchantAccount.id.desc())
            .limit(1)
        )
        if role is not None:
            query = query.where(MerchantAccountUser.role == role.value)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_merchant_account_id_for_user(
        self,
        user_id: UUID,
        *,
        role: MerchantUserRole | None = MerchantUserRole.OWNER,
    ) -> UUID | None:
        merchant = await self.get_merchant_for_user(user_id, role=role)
        return merchant.id if merchant else None
