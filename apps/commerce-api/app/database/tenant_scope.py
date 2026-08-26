"""
Canonical registry of tenant-scoped database tables.

Any table listed here MUST:
- contain tenant_id
- have RLS enabled
- have FORCE ROW LEVEL SECURITY enabled
- enforce tenant isolation through PostgreSQL policy

Control-plane tables must NOT be added here.
"""

TENANT_SCOPED_TABLES = (
    "users",
)
