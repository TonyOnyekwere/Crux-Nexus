"""Integration tests for the trial expiration worker.

Covers the lifecycle the trial-history patch introduced:
    onboarding -> TRIALING (trial_ends_at in the future)
    -> [time passes] -> expire_due_trials() -> EXPIRED
    -> merchant_trial_history closed
    -> owning tenant(s) suspended
    -> TRIAL_EXPIRED outbox event emitted

And the property the worker depends on for correctness in production: a
second sweep over an already-expired subscription must be a no-op — the
worker runs on a fixed interval forever, not once.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.contexts.billing.domain.merchant_subscription import MerchantSubscription, SubscriptionStatus
from app.contexts.billing.domain.merchant_trial_history import MerchantTrialHistory
from app.contexts.identity.domain.entities import User
from app.contexts.onboarding.application.services import OnboardingService
from app.contexts.tenant_management.domain.entities import Tenant, TenantStatus
from app.infrastructure.outbox.repository import OutboxEvent
from app.kernel.events.types import DomainEvent
from app.workers.trial_expiration import expire_due_trials


async def _onboard_trialing_merchant(db_session, *, plan_code: str = "starter"):
    user = User(email=f"trial-{uuid4()}@example.com", password_hash="hash")
    db_session.add(user)
    await db_session.flush()

    onboarding = OnboardingService(db_session)
    result = await onboarding.onboard_merchant(
        user_id=user.id,
        merchant_name="Trial Expiration Merchant",
        storefront_slug=f"trial-exp-{uuid4()}",
        plan_code=plan_code,
    )
    return result


async def _backdate_trial(db_session, subscription_id):
    """Simulate a trial that ended in the past, without waiting real time."""
    past = datetime.now(timezone.utc) - timedelta(days=1)
    subscription = await db_session.get(MerchantSubscription, subscription_id)
    subscription.trial_ends_at = past
    await db_session.flush()
    return past


@pytest.mark.asyncio
async def test_expire_due_trials_transitions_subscription_history_and_tenant(db_session):
    result = await _onboard_trialing_merchant(db_session)
    subscription_id = result["subscription_id"]
    tenant_id = result["tenant_id"]

    past = await _backdate_trial(db_session, subscription_id)
    await db_session.commit()

    expired_count = await expire_due_trials(db_session)
    assert expired_count == 1

    subscription = await db_session.get(MerchantSubscription, subscription_id)
    assert subscription.status == SubscriptionStatus.EXPIRED.value
    assert subscription.ends_at == past

    history_result = await db_session.execute(
        select(MerchantTrialHistory).where(
            MerchantTrialHistory.subscription_id == subscription_id
        )
    )
    history = history_result.scalar_one()
    assert history.status == SubscriptionStatus.EXPIRED.value
    assert history.ended_at == past

    # Entitlement decision: losing trial entitlement suspends the tenant,
    # not just the billing record. Onboarding creates the tenant as
    # ONBOARDING, so this also proves suspension applies from that state,
    # not only from ACTIVE.
    tenant = await db_session.get(Tenant, tenant_id)
    assert tenant.status == TenantStatus.SUSPENDED.value

    outbox_result = await db_session.execute(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == subscription_id,
            OutboxEvent.event_type == DomainEvent.TRIAL_EXPIRED.value,
        )
    )
    outbox_event = outbox_result.scalar_one()
    assert outbox_event.payload["suspended_tenant_ids"] == [str(tenant_id)]


@pytest.mark.asyncio
async def test_expire_due_trials_does_not_touch_already_archived_tenant(db_session):
    """A tenant already in a terminal offboarding state should not be
    resurrected or otherwise touched by trial expiration — expiration only
    suspends tenants that are still operationally active/onboarding."""
    result = await _onboard_trialing_merchant(db_session)
    subscription_id = result["subscription_id"]
    tenant_id = result["tenant_id"]

    tenant = await db_session.get(Tenant, tenant_id)
    tenant.status = TenantStatus.ARCHIVED
    await db_session.flush()

    await _backdate_trial(db_session, subscription_id)
    await db_session.commit()

    expired_count = await expire_due_trials(db_session)
    assert expired_count == 1

    tenant = await db_session.get(Tenant, tenant_id)
    assert tenant.status == TenantStatus.ARCHIVED.value

    outbox_result = await db_session.execute(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == subscription_id,
            OutboxEvent.event_type == DomainEvent.TRIAL_EXPIRED.value,
        )
    )
    outbox_event = outbox_result.scalar_one()
    assert outbox_event.payload["suspended_tenant_ids"] == []


@pytest.mark.asyncio
async def test_expire_due_trials_is_idempotent_on_repeated_sweeps(db_session):
    """The worker runs every interval forever — a second sweep over an
    already-expired subscription must not re-expire it or double-emit the
    TRIAL_EXPIRED event."""
    result = await _onboard_trialing_merchant(db_session)
    subscription_id = result["subscription_id"]

    await _backdate_trial(db_session, subscription_id)
    await db_session.commit()

    first_pass = await expire_due_trials(db_session)
    assert first_pass == 1

    second_pass = await expire_due_trials(db_session)
    assert second_pass == 0

    outbox_result = await db_session.execute(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == subscription_id,
            OutboxEvent.event_type == DomainEvent.TRIAL_EXPIRED.value,
        )
    )
    assert len(outbox_result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_expire_due_trials_ignores_trials_not_yet_ended(db_session):
    result = await _onboard_trialing_merchant(db_session)
    subscription_id = result["subscription_id"]
    tenant_id = result["tenant_id"]

    # trial_ends_at was set by onboarding to the future (now + plan.trial_days);
    # left untouched, this subscription should not be picked up, and its
    # tenant should not be suspended.
    expired_count = await expire_due_trials(db_session)
    assert expired_count == 0

    subscription = await db_session.get(MerchantSubscription, subscription_id)
    assert subscription.status == SubscriptionStatus.TRIALING.value

    tenant = await db_session.get(Tenant, tenant_id)
    assert tenant.status == TenantStatus.ONBOARDING.value
