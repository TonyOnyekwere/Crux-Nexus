# CruxNexus Commerce API

Trust-centric commerce infrastructure platform built with FastAPI, PostgreSQL, and Railway.

## Features

- **Multi-tenant Architecture**: Built-in tenant isolation with Row Level Security (RLS)
- **Trust-First Design**: Evidence-based trust scoring and fraud detection
- **Provider Abstraction**: Pluggable payment, logistics, and notification providers
- **Guest Checkout**: Frictionless purchasing without forced account creation
- **Modular Monolith**: Bounded contexts with hexagonal architecture

## Tech Stack

- **Backend**: FastAPI (Python 3.12)
- **Database**: PostgreSQL with RLS
- **Cache**: Redis
- **Task Queue**: Celery
- **Deployment**: Railway
- **ORM**: SQLAlchemy 2.0 (async)

## Project Structure

```
apps/commerce-api/
├── app/
│   ├── contexts/           # Bounded contexts
│   │   ├── identity/      # User authentication & management
│   │   │   ├── domain/     # Domain entities & logic
│   │   │   ├── application/ # Application services
│   │   │   ├── infrastructure/ # External dependencies
│   │   │   └── api/        # API routes & schemas
│   │   └── tenant_management/ # Tenant provisioning
│   ├── config.py           # Application configuration
│   ├── database.py         # Database connection
│   └── main.py             # FastAPI application
├── migrations/             # Alembic database migrations
├── tests/                  # Test suite
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container definition
├── railway.toml           # Railway deployment config
└── alembic.ini            # Alembic configuration
```

## Local Development

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (recommended)
- OR PostgreSQL 16+ and Redis 7+ (manual setup)

### Quick Start with Docker Compose

1. Clone the repository and navigate to the commerce-api directory
2. Start all services:
   ```bash
   docker-compose up -d
   ```
3. Run database migrations:
   ```bash
   docker-compose exec app alembic upgrade head
   ```
4. The API will be available at http://localhost:8000

### Manual Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your local database and Redis URLs
   ```

3. Run database migrations:
   ```bash
   alembic upgrade head
   ```

4. Start the development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Railway Deployment

This project is configured for Railway deployment:

1. **Railway automatically provides**:
   - `DATABASE_URL`: PostgreSQL connection string
   - `REDIS_URL`: Redis connection string
   - `PORT`: Port to run on (default 8000)

2. **Required environment variables** (set in Railway dashboard):
   - `SECRET_KEY`: Application secret key
   - `JWT_SECRET_KEY`: JWT signing key
   - `CORS_ORIGINS`: Allowed CORS origins

3. **Deployment**:
   - Connect your GitHub repository to Railway
   - Railway will automatically detect the Python project
   - Set required environment variables
   - Deploy!

## API Endpoints

### Health Checks
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check (DB/Redis connectivity)
- `GET /health/live` - Liveness check

### Identity
- `POST /api/v1/identity/users` - Create user
- `GET /api/v1/identity/users/{user_id}` - Get user by ID
- `GET /api/v1/identity/users/email/{email}` - Get user by email

### Tenants
- `POST /api/v1/tenants` - Create tenant
- `GET /api/v1/tenants/{tenant_id}` - Get tenant by ID
- `GET /api/v1/tenants/slug/{slug}` - Get tenant by slug
- `PATCH /api/v1/tenants/{tenant_id}/status` - Update tenant status

## Database Migrations

### Create a new migration
```bash
alembic revision --autogenerate -m "description"
```

### Apply migrations
```bash
alembic upgrade head
```

### Rollback migration
```bash
alembic downgrade -1
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test
pytest tests/contexts/identity/
```

## Architecture Principles

1. **Infrastructure, Not Intermediary**: Merchants retain ownership of their data
2. **Trust as First-Class**: Evidence-based scoring, not cosmetic badges
3. **Defense-in-Depth**: App-layer + RLS tenant isolation
4. **Provider Independence**: Pluggable adapters for external services
5. **Modular Monolith**: Bounded contexts ready for extraction when needed

## Current Status

### ✅ Completed
- Project structure per Engineering Handbook
- Base FastAPI application
- Identity bounded context (users, authentication)
- Tenant Management bounded context
- PostgreSQL migrations with RLS
- Railway deployment configuration
- API endpoints for core contexts
- JWT authentication middleware
- Tenant resolution middleware
- Tenant isolation test suite
- CI/CD pipeline with GitHub Actions
- Docker Compose development environment

### 🚧 In Progress
- Testing and validation of existing components

### 📋 Planned
- Catalog & Inventory contexts
- Orders & Checkout flows
- Payment provider integration
- Trust Intelligence Engine
- Enhanced RBAC permissions
- Provider adapter implementations

## License

Proprietary - All rights reserved