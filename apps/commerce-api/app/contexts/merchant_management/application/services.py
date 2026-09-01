from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_user import (
    MerchantAccountUser,
    MerchantUserRole,
)
from app.kernel.errors.codes import MERCHANT_REQUIRED
from app.kernel.errors.exceptions import CruxNexusError


class MerchantContextRequiredError(CruxNexusError):
    def __init__(self, message: str = "No merchant account found for this user."):
        super().__init__(code=MERCHANT_REQUIRED, message=message)


class AmbiguousMerchantContextError(CruxNexusError):
    def __init__(
        self,
        message: str = (
            "Multiple owner merchant accounts found. "
            "An explicit merchant context is required."
        ),
    ):
        super().__init__(code=MERCHANT_REQUIRED, message=message)


class MerchantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def require_owner_merchant_account_id(self, user_id: UUID) -> UUID:
        """Return the single owner merchant account for a user.

        Never silently selects among multiple merchants. The database partial
        unique index uq_one_owner_merchant_per_user enforces at most one owner
        merchant per user; if multiple rows exist, fail explicitly.
        """
        result = await self.db.execute(
            select(MerchantAccountUser.merchant_account_id).where(
                MerchantAccountUser.user_id == user_id,
                MerchantAccountUser.role == MerchantUserRole.OWNER.value,
            )
        )
        merchant_ids = list(result.scalars().all())
        if not merchant_ids:
            raise MerchantContextRequiredError()
        if len(merchant_ids) > 1:
            raise AmbiguousMerchantContextError()
        return merchant_ids[0]

    async def get_owner_merchant_account(self, user_id: UUID) -> MerchantAccount | None:
        try:
            merchant_account_id = await self.require_owner_merchant_account_id(user_id)
        except MerchantContextRequiredError:
            return None
        except AmbiguousMerchantContextError:
            raise

        result = await self.db.execute(
            select(MerchantAccount).where(MerchantAccount.id == merchant_account_id)
        )
        return result.scalar_one_or_none()

    async def get_merchant_account_id_for_user(self, user_id: UUID) -> UUID | None:
        try:
            return await self.require_owner_merchant_account_id(user_id)
        except MerchantContextRequiredError:
            return None

    # Backward-compatible alias used by existing tests/imports.
    async def get_merchant_for_user(
        self,
        user_id: UUID,
        *,
        role: MerchantUserRole | None = MerchantUserRole.OWNER,
    ) -> MerchantAccount | None:
        if role is not None and role != MerchantUserRole.OWNER:
            result = await self.db.execute(
                select(MerchantAccount)
                .join(
                    MerchantAccountUser,
                    MerchantAccountUser.merchant_account_id == MerchantAccount.id,
                )
                .where(
                    MerchantAccountUser.user_id == user_id,
                    MerchantAccountUser.role == role.value,
                )
            )
            return result.scalar_one_or_none()
        return await self.get_owner_merchant_account(user_id)
