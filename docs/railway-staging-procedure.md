# Railway Staging Environment Procedure

## Purpose
Define the controlled staging environment procedure for Phase 0 deployment and validation.

## Architecture Decision
**Railway is the authoritative deployment target for Phase 0** (per ADR-0008)

## Environment Structure

```
Railway Project: CruxNexus

├── staging
│   ├── commerce-api (API service)
│   ├── PostgreSQL (Database)
│   └── Redis (Cache)
│
└── production (Phase 0+)
    ├── commerce-api (API service)
    ├── PostgreSQL (Database)
    └── Redis (Cache)
```

## Phase 0 Deployment Procedure

### 1. Create Railway Staging Environment

```bash
# Using Railway CLI
railway login
railway init
railway add postgres
railway add redis
railway add
```

### 2. Configure Staging Environment Variables

In Railway staging environment:
```
SECRET_KEY=<generated-strong-secret>
JWT_SECRET_KEY=<generated-strong-secret>
ENVIRONMENT=staging
DEBUG=false
CORS_ORIGINS=["http://localhost:3000","https://staging.cruxnexus.com"]
```

### 3. Deploy to Staging

```bash
# Connect GitHub repository to Railway
# Railway will auto-deploy on push to main branch
```

### 4. Run Migrations on Staging

```bash
# Option 1: Railway CLI
railway run alembic upgrade head

# Option 2: Railway Console
# Access PostgreSQL console and run migrations manually
```

### 5. Verify Staging Deployment

```bash
# Health checks
curl https://staging-api.cruxnexus.com/health
curl https://staging-api.cruxnexus.com/health/ready
curl https://staging-api.cruxnexus.com/health/live

# API functionality
curl -X POST https://staging-api.cruxnexus.com/api/v1/identity/users \
  -H "Content-Type: application/json" \
  -d '{"email":"test@staging.com","password":"test123"}'
```

### 6. Run Test Suite Against Staging

```bash
# Set staging environment variables
export DATABASE_URL=<staging-railway-database-url>
export REDIS_URL=<staging-railway-redis-url>

# Run tests
pytest tests/integration/test_tenant_isolation.py -v
```

### 7. Validate RLS on Staging

```bash
# Run RLS verification script
python scripts/check_rls_coverage.py
```

### 8. Performance Baseline Testing

```bash
# Define performance criteria (see below)
# Run load tests against staging endpoints
```

## Migration Execution Protocol

### Required Sequence
1. Railway PostgreSQL created
2. DATABASE_URL injected into environment
3. Alembic upgrade head executed
4. Schema inspection performed
5. RLS inspection performed
6. Migration version verification

### Verification Commands
```bash
# Check current migration version
alembic current

# Check head migration
alembic heads

# Verify schema
# Connect to Railway PostgreSQL and inspect tables
```

## Failure Testing Procedure

### Database Failure Scenario
1. Stop Railway PostgreSQL service
2. Call `/health/ready` → expect 503
3. Call `/health/live` → expect 200
4. Restart PostgreSQL
5. Call `/health/ready` → expect 200

### Redis Failure Scenario
1. Stop Railway Redis service
2. Call `/health/ready` → expect 503
3. Call `/health/live` → expect 200
4. Restart Redis
5. Call `/health/ready` → expect 200

## Production Deployment Gate

### Before Production Deployment
- ✅ All staging tests pass
- ✅ RLS verification passes
- ✅ Health/readiness contracts validated
- ✅ Performance baseline established
- ✅ Security scans pass
- ✅ CI/CD gates pass

### Production Deployment
1. Create production environment in Railway
2. Set production environment variables
3. Deploy using same Dockerfile
4. Run migrations on production database
5. Verify all health checks
6. Run smoke tests

## Rollback Procedure

If deployment fails:
1. Railway auto-rollback on health check failure
2. Manual rollback: `railway revert <deployment-id>`
3. Database rollback: `alembic downgrade -1`

## Monitoring Setup

### Railway Metrics
- CPU utilization
- Memory usage
- Request latency
- Error rate
- Database connection pool

### Log Collection
- Railway integrated logs
- Structured JSON logging
- Correlation ID tracking

## Success Criteria

### Phase 0 Completion
- [ ] Staging environment deployed and functional
- [ ] All health endpoints return correct status codes
- [ ] RLS isolation verified at database level
- [ ] CI/CD pipeline passes all gates
- [ ] Performance baseline established
- [ ] Security scanning passes
- [ ] Migration system proven on Railway infrastructure

## References
- ADR-0008: Railway as Authoritative Deployment Target
- CRX-P0-ENG-001: Phase 0 Engineering Findings
- Architecture Constitution §22 (Infrastructure as Code)