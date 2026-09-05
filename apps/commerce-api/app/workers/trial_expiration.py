"""Trial expiration worker — closes out trials once trial_ends_at has passed.

MerchantSubscription.trial_ends_at is set once, at onboarding, from the
plan's configured trial_days (see OnboardingService.onboard_merchant). This
worker is the other half of that lifecycle: it periodically scans for
TRIALING subscriptions whose trial has run out, flips them to EXPIRED, and
closes the corresponding merchant_trial_history entry with an ended_at
timestamp. Without this worker, subscriptions would sit in TRIALING forever
regardless of how much time has passed.

Phase 0 note: expiring here means EXPIRED, not PAST_DUE — PAST_DUE is
reserved for a paid subscription with a failed billing attempt, which does
not exist yet. A trial that runs out without conversion has simply ended.

Entitlement decision (locked in): subscription state and tenant state are
separate concepts — MerchantSubscription answers "does this merchant have
commercial entitlement", Tenant answers "is this storefront operationally
usable". A trial expiring is not merely a billing-record change; it removes
entitlement, so this worker suspends every tenant the merchant owns in the
same transaction as the subscription/history transition, rather than
leaving that as an async, eventually-consistent side effect. Suspension is
enforced two ways once Tenant.status = SUSPENDED:
  - Public storefront resolution (resolve_tenant_from_subdomain) only
    matches tenants with status='active', so a suspended storefront simply
    stops resolving — no separate check needed there.
  - Merchant-authenticated access is blocked explicitly in
    TenantContextResolution.resolve_tenant_context_from_jwt (see
    app/auth/tenant_context.py), the same place ARCHIVED is already
    rejected.

Reactivation (SUSPENDED -> ACTIVE on successful paid conversion) is not
implemented here — there is no payment/subscription-activation flow in the
codebase yet for it to hook into. That is Phase 1 work once billing exists;
the natural trigger point is whatever service transitions
MerchantSubscription EXPIRED -> ACTIVE.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.contexts.billing.domain.merchant_subscription import MerchantSubscription, SubscriptionStatus
from app.contexts.billing.domain.merchant_trial_history import MerchantTrialHistory
from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.database.url import normalize_async_database_url
from app.kernel.events.publisher import publish_to_outbox
from app.kernel.events.types import DomainEvent, EventEnvelope

logger = logging.getLogger(__name__)

# Tenant states a trial expiration is allowed to suspend from. A tenant
# already ARCHIVED or OFFBOARDING is in a terminal/exit flow unrelated to
# billing entitlement — expiration should not resurrect or otherwise touch
# it. SUSPENDED is included so this stays idempotent if it somehow runs
# twice against the same tenant.
_SUSPENDABLE_TENANT_STATUSES = (
    TenantStatus.PROVISIONING,
    TenantStatus.ONBOARDING,
    TenantStatus.ACTIVE,
)


async def expire_due_trials(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    batch_size: int = 50,
) -> int:
    """Transition TRIALING subscriptions past their trial_ends_at to EXPIRED.

    For each expired subscription this also closes the open
    merchant_trial_history row (status + ended_at), suspends every tenant
    the merchant owns (see module docstring — entitlement decision), and
    emits a TRIAL_EXPIRED outbox event. Returns the number of subscriptions
    expired.
    """
    now = now or datetime.now(timezone.utc)

    result = await db.execute(
        select(MerchantSubscription)
        .where(
            MerchantSubscription.status == SubscriptionStatus.TRIALING.value,
            MerchantSubscription.trial_ends_at.is_not(None),
            MerchantSubscription.trial_ends_at <= now,
        )
        .order_by(MerchantSubscription.trial_ends_at)
        .limit(batch_size)
    )
    subscriptions = result.scalars().all()
    if not subscriptions:
        return 0

    for subscription in subscriptions:
        logger.info(
            "Expiring trial for subscription %s merchant=%s",
            subscription.id,
            subscription.merchant_account_id,
        )

        await db.execute(
            update(MerchantSubscription)
            .where(MerchantSubscription.id == subscription.id)
            .values(status=SubscriptionStatus.EXPIRED.value, ends_at=subscription.trial_ends_at)
        )

        # Close the open trial_history entry written at trial start.
        # Primary match: direct subscription_id reference (migration 011).
        # Fallback: the older correlation by merchant + plan + status, kept
        # only for any row written before that column existed — new rows
        # always carry subscription_id, so this branch should not fire for
        # anything created after this patch.
        history_result = await db.execute(
            select(MerchantTrialHistory).where(
                MerchantTrialHistory.subscription_id == subscription.id,
                MerchantTrialHistory.ended_at.is_(None),
            )
        )
        open_trial_history = history_result.scalar_one_or_none()

        if open_trial_history is None:
            legacy_result = await db.execute(
                select(MerchantTrialHistory)
                .where(
                    MerchantTrialHistory.subscription_id.is_(None),
                    MerchantTrialHistory.merchant_account_id == subscription.merchant_account_id,
                    MerchantTrialHistory.subscription_plan_id == subscription.subscription_plan_id,
                    MerchantTrialHistory.status == SubscriptionStatus.TRIALING.value,
                    MerchantTrialHistory.ended_at.is_(None),
                )
                .order_by(MerchantTrialHistory.started_at.desc())
                .limit(1)
            )
            open_trial_history = legacy_result.scalar_one_or_none()

        if open_trial_history is not None:
            await db.execute(
                update(MerchantTrialHistory)
                .where(MerchantTrialHistory.id == open_trial_history.id)
                .values(status=SubscriptionStatus.EXPIRED.value, ended_at=subscription.trial_ends_at)
            )
        else:
            logger.warning(
                "No open merchant_trial_history entry found for subscription %s "
                "(merchant=%s, plan=%s) while expiring trial",
                subscription.id,
                subscription.merchant_account_id,
                subscription.subscription_plan_id,
            )

        # Suspend every tenant this merchant owns. A merchant can own more
        # than one storefront (max_extra_storefronts per plan); losing
        # entitlement suspends all of them, not just one.
        suspended_tenant_ids_result = await db.execute(
            update(Tenant)
            .where(
                Tenant.id.in_(
                    select(MerchantAccountTenant.tenant_id).where(
                        MerchantAccountTenant.merchant_account_id == subscription.merchant_account_id
                    )
                ),
                Tenant.status.in_(_SUSPENDABLE_TENANT_STATUSES),
            )
            .values(status=TenantStatus.SUSPENDED)
            .returning(Tenant.id)
        )
        suspended_tenant_ids = [row[0] for row in suspended_tenant_ids_result.fetchall()]
        if not suspended_tenant_ids:
            logger.warning(
                "No suspendable tenant found for merchant %s while expiring "
                "subscription %s — merchant may already have no active "
                "storefronts, or already-terminal tenants (archived/offboarding)",
                subscription.merchant_account_id,
                subscription.id,
            )

        await publish_to_outbox(
            db,
            EventEnvelope(
                event_type=DomainEvent.TRIAL_EXPIRED,
                aggregate_type="MerchantSubscription",
                aggregate_id=subscription.id,
                payload={
                    "subscription_id": str(subscription.id),
                    "merchant_account_id": str(subscription.merchant_account_id),
                    "subscription_plan_id": str(subscription.subscription_plan_id),
                    "trial_ends_at": subscription.trial_ends_at.isoformat(),
                    "suspended_tenant_ids": [str(tid) for tid in suspended_tenant_ids],
                },
            ),
        )

    await db.commit()
    return len(subscriptions)


async def run_trial_expiration_loop(interval_seconds: int = 300) -> None:
    """Run expire_due_trials() on a fixed interval, forever.

    Deployment invariant: the web service owns schema migration
    (entrypoint.sh runs `alembic upgrade head` only in web mode); this
    worker never migrates. If the worker starts against a not-yet-migrated
    database, the broad except below catches the resulting error (e.g.
    ProgrammingError for a missing/outdated table), logs it, and retries on
    the next tick rather than crash-looping the process — the same pattern
    app.workers.event_relay and app.main's tenant_middleware already use for
    the same reason. Once the web service's migration completes, the next
    tick succeeds with no restart needed.
    """
    settings = get_settings()
    engine = create_async_engine(normalize_async_database_url(settings.DATABASE_URL))
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    while True:
        async with session_factory() as session:
            try:
                count = await expire_due_trials(session)
                if count:
                    logger.info("Expired %d trial(s)", count)
            except Exception:
                logger.exception("Trial expiration sweep failed")
                await session.rollback()
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_trial_expiration_loop())
