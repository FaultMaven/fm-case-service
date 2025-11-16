# fm-case-service

FaultMaven Case Management Microservice - Phase 3 of microservices migration.

## Overview

This microservice handles case management for the FaultMaven troubleshooting platform. Cases are persistent containers for troubleshooting sessions that can span multiple interactions and user sessions.

## Architecture

- **Pattern**: Microservice following fm-auth-service and fm-session-service patterns
- **Authentication**: Trusts X-User-* headers from fm-api-gateway (no JWT validation)
- **Database**: SQLite (development) / PostgreSQL (production)
- **ORM**: SQLAlchemy 2.0 async
- **API**: FastAPI with Pydantic models

## Features

- **Case CRUD**: Create, read, update, delete cases
- **Authorization**: Users can only access their own cases
- **Session Linking**: Cases can be linked to sessions
- **Status Management**: Track case lifecycle (active → investigating → resolved/archived/closed)
- **Pagination**: List endpoints support pagination and filtering
- **Auto-generated Titles**: Cases get auto-generated titles if not provided (Case-MMDD-N format)

## API Endpoints

### Case Management
- `POST /api/v1/cases` - Create new case
- `GET /api/v1/cases/{case_id}` - Get case details
- `PUT /api/v1/cases/{case_id}` - Update case
- `DELETE /api/v1/cases/{case_id}` - Delete case
- `GET /api/v1/cases` - List user's cases (with pagination)
- `GET /api/v1/cases/session/{session_id}` - Get cases for a session
- `POST /api/v1/cases/{case_id}/status` - Update case status

### Health
- `GET /health` - Health check endpoint

## Installation

### Prerequisites
- Python 3.10+
- Poetry (recommended) or pip

### Setup

```bash
# Clone repository
cd fm-case-service

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Or with Poetry
poetry install

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
vim .env
```

## Running

### Development Mode

```bash
# With uvicorn (auto-reload)
uvicorn case_service.main:app --reload --port 8003

# Or using Python module
python -m case_service.main
```

### Production Mode

```bash
# Using uvicorn
uvicorn case_service.main:app --host 0.0.0.0 --port 8003 --workers 4

# Or using gunicorn
gunicorn case_service.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8003
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=case_service

# Run specific test file
pytest tests/test_cases.py -v
```

## Database

### SQLite (Development)

SQLite database is automatically created on first run at `./fm_cases.db`.

### PostgreSQL (Production)

1. Update DATABASE_URL in .env:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/fm_cases
```

2. Run Alembic migrations:
```bash
alembic upgrade head
```

## Configuration

Configuration is managed through environment variables (see `.env.example`):

- `SERVICE_NAME`: Service identifier (default: fm-case-service)
- `ENVIRONMENT`: Environment (development/staging/production)
- `PORT`: Service port (default: 8003)
- `DATABASE_URL`: Database connection string
- `DEFAULT_PAGE_SIZE`: Default pagination size (default: 50)
- `MAX_PAGE_SIZE`: Maximum pagination size (default: 100)
- `CORS_ORIGINS`: Allowed CORS origins (default: *)
- `LOG_LEVEL`: Logging level (default: INFO)

## Case Data Model

```python
{
    "case_id": "case_abc123def456",
    "user_id": "user_123",
    "session_id": "session_xyz789",  # Optional
    "title": "Database connection timeout",
    "description": "Users experiencing intermittent connection timeouts",
    "status": "investigating",  # active, investigating, resolved, archived, closed
    "severity": "high",  # low, medium, high, critical
    "category": "performance",  # performance, error, configuration, infrastructure, security, other
    "metadata": {},  # Custom metadata
    "tags": ["database", "timeout"],
    "created_at": "2025-11-15T10:30:00Z",
    "updated_at": "2025-11-15T12:45:00Z",
    "resolved_at": null
}
```

## Integration with API Gateway

This service expects the following headers from fm-api-gateway:

- `X-User-ID`: User identifier (required)
- `X-User-Email`: User email (optional)
- `X-User-Roles`: User roles (optional)

The service trusts these headers and does NOT perform JWT validation.

## Development Notes

- Follow the same patterns as fm-auth-service and fm-session-service
- Use async/await throughout
- Pydantic models for request/response validation
- SQLAlchemy 2.0 async ORM
- Proper error handling with FastAPI HTTPException
- Comprehensive logging

## Future Enhancements

- Case sharing/collaboration
- Case search with full-text search
- Case templates
- Case export/import
- Case analytics
- Webhooks for case events

## License

Copyright (c) 2025 FaultMaven Team
