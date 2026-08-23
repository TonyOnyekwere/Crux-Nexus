# ADR-0010: Environment-Provided Infrastructure Configuration

## Status
**ACCEPTED**

## Context
CruxNexus must not hardcode infrastructure connection strings or provide default production fallbacks. The application should only know variable names, not actual connection strings.

## Decision
**Infrastructure connection strings SHALL be provided exclusively through deployment environment variables with zero hardcoded values.**

### Configuration Contract
- `DATABASE_URL`: REQUIRED - Provided by Railway PostgreSQL service
- `REDIS_URL`: REQUIRED - Provided by Railway Redis service  
- `SECRET_KEY`: REQUIRED - Provided by deployment environment
- `JWT_SECRET_KEY`: REQUIRED - Provided by deployment environment
- `ENVIRONMENT`: REQUIRED - Provided by deployment environment

### Implementation
```python
class Settings(BaseSettings):
    DATABASE_URL: str  # REQUIRED - no default
    REDIS_URL: str     # REQUIRED - no default
    SECRET_KEY: str    # REQUIRED - no default
    JWT_SECRET_KEY: str # REQUIRED - no default
```

### Fail-Fast Behavior
Missing required variables in production:
```text
Application startup
       ↓
FAIL
       ↓
clear configuration error
```

No localhost defaults, no empty string fallbacks, no "maybe works" behavior.

## Rationale
1. **Security**: No credentials in Git, Dockerfile, or source code
2. **Environment Agnostic**: Same image runs in staging and production
3. **Credential Rotation**: Easy to rotate without code changes
4. **Railway Integration**: Use Railway's service-variable mechanism
5. **Configuration Hierarchy**: Environment variables are source of truth

## Consequences
- Application fails startup if required environment variables are missing
- Development environments must provide all required variables
- Railway provides DATABASE_URL and REDIS_URL automatically
- Docker image contains no infrastructure addresses or credentials
- Exact same Docker image can run in staging and production

## Environment Structure
```
                    CRUXNEXUS
                       │
              ┌────────┴────────┐
              │                 │
           STAGING          PRODUCTION
              │                 │
        ┌─────┼─────┐     ┌─────┼─────┐
        │     │     │     │     │     │
       API   PG   Redis   API   PG   Redis
        │     │     │     │     │     │
        └─────┴─────┘     └─────┴─────┘
```

Each environment gets its own DATABASE_URL, REDIS_URL, SECRET_KEY, JWT_SECRET_KEY.

## References
- CRX-P0-ENG-003 Finding #16 (Configuration architecture)
- CRX-P0-004 Configuration Architecture Clarification
- Architecture Constitution §22 (Infrastructure as Code)