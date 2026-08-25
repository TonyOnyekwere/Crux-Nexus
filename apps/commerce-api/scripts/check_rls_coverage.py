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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.config import get_settings


async def check_rls_coverage():
    """Check RLS coverage for all tenant-scoped tables."""
    settings = get_settings()
    
    # Use async URL with async engine (CRX-P0-005B fix)
    database_url = settings.DATABASE_URL
    
    # Check for Railway DATABASE_URL
    import os
    railway_db_url = os.environ.get("DATABASE_URL")
    if railway_db_url:
        database_url = railway_db_url
    
    engine = create_async_engine(database_url, echo=False)
    
    # CRX-P0-005C: Tenants table is platform-control-plane data, not tenant-scoped
    # Only check RLS on actual tenant-owned tables
    tenant_scoped_tables = [
        "users",
        # Add more tenant-scoped tables as they are created
    ]
    
    failed_tables = []
    partial_failures = []
    
    async with engine.begin() as conn:
        for table in tenant_scoped_tables:
            # Check if table exists
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = :table_name
                    )
                """),
                {"table_name": table}
            )
            table_exists = result.scalar()
            
            if not table_exists:
                print(f"❌ FAIL: Required table '{table}' does not exist")
                failed_tables.append((table, ["Required table missing"]))
                continue
            
            table_issues = []
            
            # Check if RLS is enabled
            result = await conn.execute(
                text("""
                    SELECT relrowsecurity 
                    FROM pg_class 
                    WHERE relname = :table_name
                """),
                {"table_name": table}
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
                {"table_name": table}
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
                {"table_name": table}
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
                    {"table_name": table}
                )
                policy_data = result.fetchone()
                
                if policy_data:
                    using_expr, with_check_expr = policy_data
                    if not with_check_expr or with_check_expr.strip() == "":
                        table_issues.append("Policy missing WITH CHECK clause for write operations")
            
            if table_issues:
                if "RLS not enabled" in table_issues or "FORCE ROW LEVEL SECURITY not enabled" in table_issues:
                    failed_tables.append((table, table_issues))
                    print(f"❌ FAIL: Table '{table}' - {', '.join(table_issues)}")
                else:
                    partial_failures.append((table, table_issues))
                    print(f"⚠️  PARTIAL: Table '{table}' - {', '.join(table_issues)}")
            else:
                print(f"✅ PASS: Table '{table}' has complete RLS protection")
    
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