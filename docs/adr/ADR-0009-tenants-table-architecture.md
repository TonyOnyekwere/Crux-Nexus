# ADR-0009: Tenants Table as Platform Control Plane Data

## Status
**ACCEPTED**

## Context
The `tenants` table represents CruxNexus's tenant registry and is fundamentally different from ordinary tenant-scoped data like `users`, `products`, or `orders`.

## Decision
**The `tenants` table is platform-control-plane data, not ordinary tenant-scoped data.**

### Architectural Classification
- **Platform Control Plane**: Administrative infrastructure managed by platform services
- **Tenant Commerce Plane**: Merchant data scoped to individual tenants

### Security Model
- **Direct Database Access**: Denied (RLS policy: `USING (false)`)
- **Application Services**: Only platform services may manipulate tenant records
- **Merchant Operations**: Must go through controlled application interfaces
- **Future RBAC**: Platform admin roles will have specific, scoped access

### RLS Policy
```sql
CREATE POLICY tenant_management_isolation ON tenants
USING (false)  -- Deny direct SELECT
WITH CHECK (false)  -- Deny direct INSERT/UPDATE/DELETE
```

### Rationale
1. **Platform Integrity**: Tenant lifecycle operations must be controlled and audited
2. **Security Boundary**: Merchants should not directly operate against tenant registry
3. **Data Model**: Tenants table contains platform infrastructure, not merchant data
4. **Future Evolution**: RBAC implementation will provide controlled platform admin access

## Consequences
- All tenant operations must go through application services
- Direct database queries against tenants table will fail
- Platform admin services will need dedicated authorization model
- Migration to proper RBAC in Phase 2+ will be required

## Future Evolution
- Phase 2: Implement platform admin RBAC with specific tenant management permissions
- Phase 3: Add audit logging for all tenant lifecycle operations
- Phase 4: Consider multi-region tenant registry with eventual consistency

## References
- CRX-P0-ENG-003 Finding #10 (tenants RLS policy architectural issue)
- Architecture Constitution §4.1 (Control/Commerce Plane Split)
- Architecture Constitution §15 (Multi-Tenant Security Model)