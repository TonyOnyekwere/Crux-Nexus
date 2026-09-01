from enum import Enum
from typing import Dict, Set


class Permission(str, Enum):
    """Individual permissions for granular access control."""
    VIEW_DASHBOARD = "view_dashboard"
    MANAGE_PRODUCTS = "manage_products"
    MANAGE_INVENTORY = "manage_inventory"
    MANAGE_ORDERS = "manage_orders"
    MANAGE_STAFF = "manage_staff"
    MANAGE_STORE_SETTINGS = "manage_store_settings"
    VIEW_REPORTS = "view_reports"
    EXPORT_DATA = "export_data"


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "owner": {
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_ORDERS,
        Permission.MANAGE_STAFF,
        Permission.MANAGE_STORE_SETTINGS,
        Permission.VIEW_REPORTS,
        Permission.EXPORT_DATA,
    },
    "manager": {
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_ORDERS,
        Permission.VIEW_REPORTS,
    },
    "staff": {
        Permission.VIEW_DASHBOARD,
        Permission.MANAGE_INVENTORY,
        Permission.MANAGE_ORDERS,
    },
}


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


# Backward-compatible alias for older imports during the architecture transition.
role_has_permission = has_permission