"""
Canonical registry of tenant-scoped database tables.

Any table listed here MUST:
- contain tenant_id
- have RLS enabled
- have FORCE ROW LEVEL SECURITY enabled
- enforce tenant isolation through PostgreSQL policy

Control-plane tables must NOT be added here.

Phase 0 status (honest):
- This registry is currently EMPTY because Phase 0 has no tenant-owned commerce
  tables yet (products, orders, customers, inventory, etc.).
- The RLS CI gate therefore performs a VACUOUS PASS until commerce tables land.
- Control-plane isolation (merchant ownership, membership authorization) is
  enforced at the application layer in Phase 0.
- Tenant data-plane RLS proof is NOT YET APPLICABLE — do not claim otherwise.
"""

TENANT_SCOPED_TABLES: tuple[str, ...] = (
    # Future tenant-owned commerce data tables will be added here:
    # "products",
    # "orders",
    # "customers",
    # "inventory",
)
