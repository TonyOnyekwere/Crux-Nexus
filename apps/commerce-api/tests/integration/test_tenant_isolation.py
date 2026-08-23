import pytest
from sqlalchemy import text
from httpx import AsyncClient
from uuid import uuid4


class TestTenantIsolation:
    """Test suite to verify tenant isolation across all tenant-scoped tables."""
    
    @pytest.mark.asyncio
    async def test_users_tenant_isolation(self, client: AsyncClient, db_session):
        """Test that users from one tenant cannot access users from another tenant."""
        # Create two tenants
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Create users for each tenant
        user1_response = await client.post(
            "/api/v1/identity/users",
            json={
                "email": "user1@tenant1.com",
                "password": "password123",
                "tenant_id": str(tenant1_id)
            }
        )
        assert user1_response.status_code == 201
        user1_data = user1_response.json()
        
        user2_response = await client.post(
            "/api/v1/identity/users",
            json={
                "email": "user2@tenant2.com", 
                "password": "password123",
                "tenant_id": str(tenant2_id)
            }
        )
        assert user2_response.status_code == 201
        user2_data = user2_response.json()
        
        # Set tenant context to tenant1
        client.headers.update({"X-Tenant-ID": str(tenant1_id)})
        
        # Try to access user2 (should fail with 404 or 403)
        response = await client.get(f"/api/v1/identity/users/{user2_data['id']}")
        # This should fail due to tenant isolation
        assert response.status_code in [403, 404]
    
    @pytest.mark.asyncio
    async def test_rls_policy_enforcement(self, db_session):
        """Test that RLS policies are actually enforced at the database level."""
        # Create two tenants
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Insert users directly (bypassing application layer)
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, auth_provider, status, tenant_id)
                VALUES (:id1, :email1, 'hash', 'password', 'active', :tenant1)
            """),
            {"id1": uuid4(), "email1": "user1@tenant1.com", "tenant1": str(tenant1_id)}
        )
        
        user2_id = uuid4()
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, auth_provider, status, tenant_id)
                VALUES (:id2, :email2, 'hash', 'password', 'active', :tenant2)
            """),
            {"id2": user2_id, "email2": "user2@tenant2.com", "tenant2": str(tenant2_id)}
        )
        
        await db_session.commit()
        
        # Set tenant context to tenant1
        await db_session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(tenant1_id)}
        )
        
        # Try to query user2 while in tenant1 context
        result = await db_session.execute(
            text("SELECT * FROM users WHERE id = :id"),
            {"id": str(user2_id)}
        )
        
        # Should return no rows due to RLS
        user_row = result.fetchone()
        assert user_row is None, "RLS policy failed - tenant can access other tenant's data"
    
    @pytest.mark.asyncio
    async def test_rls_select_isolation(self, db_session):
        """Test SELECT isolation - tenant A cannot SELECT tenant B's data."""
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Insert users for both tenants
        user1_id = uuid4()
        user2_id = uuid4()
        
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, auth_provider, status, tenant_id)
                VALUES (:id1, :email1, 'hash', 'password', 'active', :tenant1),
                       (:id2, :email2, 'hash', 'password', 'active', :tenant2)
            """),
            {"id1": user1_id, "email1": "user1@tenant1.com", "tenant1": str(tenant1_id),
             "id2": user2_id, "email2": "user2@tenant2.com", "tenant2": str(tenant2_id)}
        )
        
        await db_session.commit()
        
        # Set tenant context to tenant1
        await db_session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(tenant1_id)}
        )
        
        # Try to SELECT all users - should only see tenant1's users
        result = await db_session.execute(text("SELECT id FROM users"))
        user_ids = [row[0] for row in result.fetchall()]
        
        assert user2_id not in user_ids, "RLS SELECT failed - can see other tenant's data"
        assert user1_id in user_ids, "RLS SELECT failed - cannot see own tenant's data"
    
    @pytest.mark.asyncio
    async def test_rls_insert_isolation(self, db_session):
        """Test INSERT isolation - tenant A cannot INSERT into tenant B's context."""
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Set tenant context to tenant1
        await db_session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(tenant1_id)}
        )
        
        # Try to INSERT a user with tenant2_id - should fail
        user_id = uuid4()
        insert_result = await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, auth_provider, status, tenant_id)
                VALUES (:id, :email, 'hash', 'password', 'active', :tenant)
                RETURNING id
            """),
            {"id": user_id, "email": "malicious@tenant1.com", "tenant": str(tenant2_id)}
        )
        
        # Should not return inserted ID due to RLS
        inserted_id = insert_result.scalar()
        assert inserted_id is None, "RLS INSERT failed - can insert with different tenant_id"
        
        # Verify no row was actually inserted
        verification_result = await db_session.execute(
            text("SELECT id FROM users WHERE id = :id"),
            {"id": str(user_id)}
        )
        assert verification_result.fetchone() is None, "Row was actually inserted despite RLS"
        
        await db_session.rollback()
    
    @pytest.mark.asyncio
    async def test_rls_update_isolation(self, db_session):
        """Test UPDATE isolation - tenant A cannot UPDATE tenant B's data."""
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Insert a user for tenant2
        user2_id = uuid4()
        original_email = "user2@tenant2.com"
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, auth_provider, status, tenant_id)
                VALUES (:id, :email, 'hash', 'password', 'active', :tenant)
            """),
            {"id": user2_id, "email": original_email, "tenant": str(tenant2_id)}
        )
        await db_session.commit()
        
        # Set tenant context to tenant1
        await db_session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(tenant1_id)}
        )
        
        # Try to UPDATE tenant2's user
        update_result = await db_session.execute(
            text("UPDATE users SET email = :email WHERE id = :id RETURNING email"),
            {"email": "hacked@tenant1.com", "id": str(user2_id)}
        )
        
        # Should not update any rows due to RLS
        updated_email = update_result.scalar()
        assert updated_email is None, "RLS UPDATE failed - can update other tenant's data"
        
        # Verify email is unchanged
        verification_result = await db_session.execute(
            text("SELECT email FROM users WHERE id = :id"),
            {"id": str(user2_id)}
        )
        current_email = verification_result.scalar()
        assert current_email == original_email, "Email was changed despite RLS"
        
        await db_session.rollback()
    
    @pytest.mark.asyncio
    async def test_rls_delete_isolation(self, db_session):
        """Test DELETE isolation - tenant A cannot DELETE tenant B's data."""
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Insert a user for tenant2
        user2_id = uuid4()
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, auth_provider, status, tenant_id)
                VALUES (:id, :email, 'hash', 'password', 'active', :tenant)
            """),
            {"id": user2_id, "email": "user2@tenant2.com", "tenant": str(tenant2_id)}
        )
        await db_session.commit()
        
        # Set tenant context to tenant1
        await db_session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(tenant1_id)}
        )
        
        # Try to DELETE tenant2's user
        delete_result = await db_session.execute(
            text("DELETE FROM users WHERE id = :id RETURNING id"),
            {"id": str(user2_id)}
        )
        
        # Should not delete any rows due to RLS
        deleted_id = delete_result.scalar()
        assert deleted_id is None, "RLS DELETE failed - can delete other tenant's data"
        
        # Verify user still exists
        verification_result = await db_session.execute(
            text("SELECT id FROM users WHERE id = :id"),
            {"id": str(user2_id)}
        )
        assert verification_result.fetchone() is not None, "User was deleted despite RLS"
        
        await db_session.rollback()
    
    @pytest.mark.asyncio
    async def test_missing_tenant_context_deny(self, db_session):
        """Test that missing tenant context results in DENY, not unrestricted access."""
        # Insert a user without setting tenant context
        user_id = uuid4()
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, auth_provider, status, tenant_id)
                VALUES (:id, :email, 'hash', 'password', 'active', :tenant)
            """),
            {"id": user_id, "email": "test@test.com", "tenant": str(uuid4())}
        )
        await db_session.commit()
        
        # Try to SELECT without tenant context set
        # With nullable RLS policy, this should return no rows
        result = await db_session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": str(user_id)})
        user_row = result.fetchone()
        assert user_row is None, "Missing tenant context should deny access"
    
    @pytest.mark.asyncio
    async def test_tenant_context_setting(self, client: AsyncClient):
        """Test that tenant context is properly set in database sessions."""
        tenant_id = uuid4()
        
        # Create a user with tenant
        response = await client.post(
            "/api/v1/identity/users",
            json={
                "email": "test@tenant.com",
                "password": "password123",
                "tenant_id": str(tenant_id)
            }
        )
        assert response.status_code == 201
        
        # Set tenant header
        client.headers.update({"X-Tenant-ID": str(tenant_id)})
        
        # Try to access the user - should work
        user_data = response.json()
        response = await client.get(f"/api/v1/identity/users/{user_data['id']}")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_cross_tenant_data_leak_prevention(self, client: AsyncClient):
        """Test that cross-tenant data leaks are prevented."""
        # Create tenant1 and tenant2
        tenant1_id = uuid4()
        tenant2_id = uuid4()
        
        # Create users for both tenants
        user1_response = await client.post(
            "/api/v1/identity/users",
            json={
                "email": "user1@tenant1.com",
                "password": "password123",
                "tenant_id": str(tenant1_id)
            }
        )
        
        user2_response = await client.post(
            "/api/v1/identity/users",
            json={
                "email": "user2@tenant2.com",
                "password": "password123",
                "tenant_id": str(tenant2_id)
            }
        )
        
        # Try to list all users without tenant context (should fail or return empty)
        response = await client.get("/api/v1/identity/users")
        # Should return 404 or empty list since we don't have a list endpoint yet
        # When we add list endpoints, they should respect tenant isolation