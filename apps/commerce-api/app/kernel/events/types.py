from enum import StrEnum
from uuid import UUID


class DomainEvent(StrEnum):
    """Base marker for governed domain events."""

    USER_REGISTERED = "UserRegistered"
    MERCHANT_CREATED = "MerchantCreated"
    STOREFRONT_CREATED = "StorefrontCreated"
    STAFF_MEMBER_ADDED = "StaffMemberAdded"
    SUBSCRIPTION_CREATED = "SubscriptionCreated"
    ENTITLEMENT_ALLOCATED = "EntitlementAllocated"
    PAYMENT_SUCCESSFUL = "PaymentSuccessful"


class EventEnvelope:
    """Normalized event envelope written to the outbox."""

    def __init__(
        self,
        *,
        event_type: DomainEvent,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict,
        tenant_id: UUID | None = None,
    ):
        self.event_type = event_type
        self.aggregate_type = aggregate_type
        self.aggregate_id = aggregate_id
        self.payload = payload
        self.tenant_id = tenant_id
