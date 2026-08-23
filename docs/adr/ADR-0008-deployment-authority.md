# ADR-0008: Railway as Authoritative Deployment Target for Phase 0

## Status
**ACCEPTED**

## Context
The project contains multiple infrastructure mechanisms:
- Railway configuration
- Dockerfile  
- Docker Compose
- AWS/Terraform infrastructure (deferred)

This creates ambiguity over which deployment mechanism is authoritative for Phase 0.

## Decision
**Railway is the authoritative deployment target for Phase 0.**

### Authority Matrix
```
AUTHORITY (Phase 0)

Deployment target: Railway
Application: commerce-api  
Database: Railway PostgreSQL
Redis: Railway Redis
Container/build path: Dockerfile (Railway-native)
AWS infrastructure: DEFERRED (not active for Phase 0)
Local development: Docker Compose (development only, not production)
```

### AWS Infrastructure Status
- **NOT DELETED** - Marked as historical/deferred
- Will be revisited in Phase 3+ when scaling justifies multi-region deployment
- ADR will be created to formally resolve AWS vs Railway at that time

## Consequences
- All Phase 0 deployment efforts target Railway
- Railway DATABASE_URL and REDIS_URL are authoritative connection strings
- Docker Compose is for local development only
- AWS Terraform modules remain in repository but are not executed

## Rationale
Given network limitations and Phase 0 scope, Railway provides:
- Deterministic cloud deployment
- Managed PostgreSQL and Redis
- Zero infrastructure maintenance overhead
- Single deployment authority reduces configuration ambiguity

## References
- CRX-P0-ENG-001 Finding #1
- Architecture Constitution §4.1 (Control/Commerce Plane Split)