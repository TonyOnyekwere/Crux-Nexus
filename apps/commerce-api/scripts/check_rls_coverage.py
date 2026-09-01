"""
RLS Policy Coverage Check Script

This script checks that all tenant-scoped tables have:
1. RLS enabled
2. FORCE ROW LEVEL SECURITY
3. Appropriate tenant isolation policies
4. Both USING and WITH CHECK clauses for write operations
"""

import asyncio
import sys
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.database.tenant_scope import TENANT_SCOPED_TABLES
from app.database.url import normalize_async_database_url


async def check_rls_coverage():
    """Check RLS coverage for all tenant-scoped tables."""
    # CRX-P0-008 P0-6: Use CI environment variables directly
    # CI provides explicit env vars for ephemeral infrastructure
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Centralized Railway database URL normalization (CRX-P0-007 P0-2)
    database_url = normalize_async_database_url(database_url)
    
    engine = create_async_engine(database_url, echo=False)
    
    # Use canonical registry from tenant_scope.py (CRX-P0-007 P0-1)
    # This ensures CI enforces the same table list as the architecture
    
    failed_tables = []
    partial_failures = []

    if not TENANT_SCOPED_TABLES:
        print(
            "⚠️  VACUOUS PASS: TENANT_SCOPED_TABLES is empty — no tenant-owned commerce "
            "tables exist yet. RLS proof is NOT established for tenant data-plane tables."
        )
        await engine.dispose()
        sys.exit(0)

    async with engine.begin() as conn:
        for table_name in TENANT_SCOPED_TABLES:
            # Check if table exists
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = :table_name
                    )
                """),
                {"table_name": table_name}
            )
            table_exists = result.scalar()
            
            if not table_exists:
                print(f"❌ FAIL: Required table '{table_name}' does not exist")
                failed_tables.append((table_name, ["Required table missing"]))
                continue
            
            table_issues = []
            
            # Check if RLS is enabled
            result = await conn.execute(
                text("""
                    SELECT relrowsecurity 
                    FROM pg_class 
                    WHERE relname = :table_name
                """),
                {"table_name": table_name}
            )
            rls_enabled = result.scalar()
            
            if not rls_enabled:
                table_issues.append("RLS not enabled")
            
            # Check if FORCE ROW LEVEL SECURITY is enabled
            result = await conn.execute(
                text("""
                    SELECT relforcerowsecurity 
                    FROM pg_class 
                    WHERE relname = :table_name
                """),
                {"table_name": table_name}
            )
            rls_forced = result.scalar()
            
            if not rls_forced:
                table_issues.append("FORCE ROW LEVEL SECURITY not enabled")
            
            # Check if tenant isolation policy exists
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_policy 
                        WHERE tablename = :table_name
                        AND policyname LIKE '%tenant%'
                    )
                """),
                {"table_name": table_name}
            )
            policy_exists = result.scalar()
            
            if not policy_exists:
                table_issues.append("No tenant isolation policy found")
            else:
                # Check if policy has WITH CHECK clause
                result = await conn.execute(
                    text("""
                        SELECT pg_get_expr(qual, oid) as using_expr,
                               pg_get_expr(with_check, oid) as with_check_expr
                        FROM pg_policy 
                        WHERE tablename = :table_name
                        AND policyname LIKE '%tenant%'
                    """),
                    {"table_name": table_name}
                )
                policy_data = result.fetchone()
                
                if policy_data:
                    using_expr, with_check_expr = policy_data
                    if not with_check_expr or with_check_expr.strip() == "":
                        table_issues.append("Policy missing WITH CHECK clause for write operations")
            
            if table_issues:
                if "RLS not enabled" in table_issues or "FORCE ROW LEVEL SECURITY not enabled" in table_issues:
                    failed_tables.append((table_name, table_issues))
                    print(f"❌ FAIL: Table '{table_name}' - {', '.join(table_issues)}")
                else:
                    partial_failures.append((table_name, table_issues))
                    print(f"⚠️  PARTIAL: Table '{table_name}' - {', '.join(table_issues)}")
            else:
                print(f"✅ PASS: Table '{table_name}' has complete RLS protection")
    
    await engine.dispose()
    
    if failed_tables:
        print(f"\n❌ RLS check failed for {len(failed_tables)} table(s):")
        for table, issues in failed_tables:
            print(f"   - {table}: {', '.join(issues)}")
        sys.exit(1)
    
    if partial_failures:
        print(f"\n❌ RLS check has partial failures for {len(partial_failures)} table(s):")
        for table, issues in partial_failures:
            print(f"   - {table}: {', '.join(issues)}")
        print("❌ Partial RLS failures are not acceptable for mandatory tenant isolation")
        sys.exit(1)
    
    print("\n✅ All tenant-scoped tables have complete RLS protection")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(check_rls_coverage())