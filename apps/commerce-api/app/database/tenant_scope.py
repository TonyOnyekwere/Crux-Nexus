"""
Canonical registry of tenant-scoped database tables.

Any table listed here MUST:
- contain tenant_id
- have RLS enabled
- have FORCE ROW LEVEL SECURITY enabled
- enforce tenant isolation through PostgreSQL policy

Control-plane tables must NOT be added here.

Note: users table is NOT tenant-scoped (global identity).
Future tenant-owned commerce data (products, orders, etc.) will be added here.
"""

TENANT_SCOPED_TABLES = (
    # Future tenant-owned commerce data tables will be added here:
    # "products",
    # "orders",
    # "customers",
    # "inventory",
    # etc.
)
