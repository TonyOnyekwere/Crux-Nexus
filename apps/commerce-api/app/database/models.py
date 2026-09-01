"""
Central model registration for Alembic migration discovery.

This module imports all SQLAlchemy models to ensure they are registered
with the Base metadata before Alembic autogenerate runs. This prevents
empty metadata and incorrect migration generation.

All domain entities must be imported here to be discovered by migrations.
"""

from sqlalchemy.orm import relationship
from app.database import Base

# Import all domain entities to register them with Base.metadata
from app.contexts.identity.domain.entities import User
from app.contexts.tenant_management.domain.entities import Tenant
from app.contexts.tenant_management.domain.membership import TenantMembership
from app.contexts.merchant_management.domain.entities import MerchantAccount
from app.contexts.merchant_management.domain.merchant_account_user import MerchantAccountUser
from app.contexts.merchant_management.domain.merchant_account_tenant import MerchantAccountTenant
from app.contexts.billing.domain.entities import SubscriptionPlan
from app.contexts.billing.domain.merchant_subscription import MerchantSubscription
from app.contexts.billing.domain.merchant_entitlement import MerchantEntitlement
from app.contexts.billing.domain.storefront_entitlement_allocation import StorefrontEntitlementAllocation
from app.contexts.billing.domain.merchant_trial_history import MerchantTrialHistory
from app.contexts.billing.domain.storefront_staff_capacity import StorefrontStaffCapacity
from app.contexts.billing.domain.staff_capacity_allocation import StaffCapacityAllocation

# Establish relationships after all models are imported
# Note: relationships are established here to avoid circular import issues
# The actual ORM relationships would be defined in the domain entities
# but we use string references to avoid circular dependencies

# Export Base for Alembic target_metadata
__all__ = ["Base"]