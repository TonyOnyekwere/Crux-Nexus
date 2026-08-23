# Phase 0 Performance Baseline Criteria

## Purpose
Define acceptance criteria for Phase 0 performance testing to establish a baseline before Phase 1 scaling.

## Philosophy
Phase 0 is about **establishing a baseline**, not proving massive scalability. We're measuring:
- Correctness under load
- Basic latency characteristics
- Resource utilization patterns
- System stability

## Test Environment
- **Target**: Railway Staging Environment
- **Tool**: k6, locust, or similar load testing tool
- **Duration**: 5 minutes per test
- **Warm-up**: 1 minute before measurement

## Acceptance Criteria

### Health Endpoint Performance

#### `/health` (Liveness)
```
Test:
Concurrent users: 100
Duration: 5 min
Requests/sec: 50
Expected p50: < 10ms
Expected p95: < 25ms
Expected p99: < 50ms
Maximum 5xx: 0%
Maximum timeout: 100ms
Database: No DB call
Redis: No Redis call
CPU: < 10%
Memory: < 100MB
```

#### `/health/ready` (Readiness)
```
Test:
Concurrent users: 50
Duration: 5 min
Requests/sec: 25
Expected p50: < 50ms
Expected p95: < 100ms
Expected p99: < 200ms
Maximum 5xx: 0%
Maximum timeout: 500ms
Database: Check connectivity
Redis: Check connectivity
CPU: < 15%
Memory: < 150MB
```

### API Endpoint Performance

#### User Creation (`POST /api/v1/identity/users`)
```
Test:
Concurrent users: 20
Duration: 5 min
Requests/sec: 10
Expected p50: < 100ms
Expected p95: < 200ms
Expected p99: < 500ms
Maximum 5xx: < 1%
Maximum timeout: 2000ms
Database: Single INSERT
Redis: No Redis call
CPU: < 20%
Memory: < 200MB
Database connections: < 5
```

#### User Login (`POST /api/v1/identity/login`)
```
Test:
Concurrent users: 20
Duration: 5 min
Requests/sec: 10
Expected p50: < 150ms
Expected p95: < 300ms
Expected p99: < 600ms
Maximum 5xx: < 1%
Maximum timeout: 2000ms
Database: SELECT + bcrypt verify
Redis: No Redis call
CPU: < 25%
Memory: < 250MB
Database connections: < 5
```

#### User Retrieval (`GET /api/v1/identity/users/{id}`)
```
Test:
Concurrent users: 50
Duration: 5 min
Requests/sec: 25
Expected p50: < 50ms
Expected p95: < 100ms
Expected p99: < 200ms
Maximum 5xx: < 1%
Maximum timeout: 1000ms
Database: Single SELECT by PK
Redis: No Redis call
CPU: < 15%
Memory: < 150MB
Database connections: < 5
```

#### Tenant Creation (`POST /api/v1/tenants`)
```
Test:
Concurrent users: 10
Duration: 5 min
Requests/sec: 5
Expected p50: < 100ms
Expected p95: < 200ms
Expected p99: < 500ms
Maximum 5xx: < 1%
Maximum timeout: 2000ms
Database: Single INSERT
Redis: No Redis call
CPU: < 20%
Memory: < 200MB
Database connections: < 5
```

### Tenant Isolation Performance

#### Cross-Tenant Query Performance
```
Test:
Setup: Tenant A with 100 users, Tenant B with 100 users
Operation: Tenant A queries users (should only see 100)
Concurrent: 20 users
Duration: 5 min
Expected p50: < 50ms
Expected p95: < 100ms
Expected p99: < 200ms
Maximum 5xx: < 1%
RLS overhead: < 10% vs non-RLS query
```

### Failure Testing Performance

#### Database Failure Recovery
```
Test:
1. Stop PostgreSQL during load test
2. Observe /health/ready → 503
3. Restart PostgreSQL
4. Measure time to recovery
Expected recovery time: < 30 seconds
Expected successful requests after recovery: > 95%
```

#### Redis Failure Recovery
```
Test:
1. Stop Redis during load test
2. Observe /health/ready → 503
3. Restart Redis
4. Measure time to recovery
Expected recovery time: < 30 seconds
Expected successful requests after recovery: > 95%
```

## Resource Utilization Baselines

### CPU Baseline
```
Idle (no traffic): < 5%
Health endpoint load: < 10%
API endpoint load: < 25%
Database operations: < 30%
```

### Memory Baseline
```
Idle: < 100MB
Health endpoint load: < 150MB
API endpoint load: < 300MB
With 100 concurrent users: < 500MB
```

### Database Connection Pool
```
Idle: 1 connection
Health checks: 2 connections
API load: 5 connections
Maximum connections: 10
Connection reuse rate: > 80%
```

## Success Criteria

### Baseline Establishment
- [ ] All endpoints meet p99 latency criteria
- [ ] Error rate < 1% under load
- [ ] No memory leaks observed
- [ ] No connection pool exhaustion
- [ ] CPU utilization within expected ranges
- [ ] RLS overhead < 10% performance impact

### System Stability
- [ ] No crashes during load tests
- [ ] Graceful degradation under dependency failure
- [ ] Automatic recovery after dependency restoration
- [ ] No resource exhaustion

### Monitoring Baseline
- [ ] Metrics collection working
- [ ] Log aggregation functional
- [ ] Correlation ID tracking operational
- [ ] Error rate monitoring baseline established

## Performance Goals vs. Acceptance Criteria

### Current Phase 0 (Baseline)
- **Goal**: Establish performance characteristics
- **Focus**: Correctness and stability
- **Load**: Low to moderate (10-100 concurrent users)

### Future Phase 3+ (Scale)
- **Goal**: Prove scalability to 10,000+ merchants
- **Focus**: High-load performance and optimization
- **Load**: High (1000+ concurrent users)

## Performance Regression Detection

### Baseline Storage
- Store performance results in `docs/performance-baseline-results.json`
- Include: timestamp, environment, tool version, all metrics
- Track changes over Phase 0→Phase 1→Phase 2

### Regression Thresholds
- **Warning**: p99 latency increase > 20%
- **Critical**: p99 latency increase > 50%
- **Blocker**: Error rate increase > 0.5%

## Performance Testing Commands

### Using k6
```bash
# Health endpoint test
k6 run tests/performance/health-endpoints.js

# API endpoint test
k6 run tests/performance/api-endpoints.js

# Tenant isolation test
k6 run tests/performance/tenant-isolation.js
```

### Using Railway CLI
```bash
# Monitor during load test
railway logs
railway status
```

## References
- CRX-P0-ENG-001 Finding #12: Performance testing should NOT happen before correctness gates
- CRX-P0-ENG-001 Finding #13: Performance testing needs defined acceptance criteria
- Architecture Constitution §23: Monitoring & Alerting (SLO-based approach)