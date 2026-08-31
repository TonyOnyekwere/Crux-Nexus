from enum import Enum

from app.contexts.tenant_management.domain.membership import TenantRole


class Permission(str, Enum):
    VIEW_DASHBOARD = "view_dashboard"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_ORDERS = "manage_orders"
    MANAGE_STAFF = "manage_staff"
    MANAGE_STORE_SETTINGS = "manage_store_settings"


ROLE_PERMISSIONS: dict[TenantRole, set[Permission]] = {
    TenantRole.OWNER: {
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_ORDERS,
        Permission.MANAGE_STAFF,
        Permission.MANAGE_STORE_SETTINGS,
    },
    TenantRole.MANAGER: {
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_ORDERS,
        Permission.MANAGE_STORE_SETTINGS,
    },
    TenantRole.STAFF: {
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_ORDERS,
    },
}


def role_has_permission(role: TenantRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
