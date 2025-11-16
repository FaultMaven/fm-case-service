# fm-case-service

**FaultMaven Case Management Microservice** - Open source case lifecycle management for troubleshooting workflows.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/faultmaven/fm-case-service)

## Overview

The Case Service manages the lifecycle of troubleshooting cases in FaultMaven. Cases are persistent containers that track investigations across multiple sessions, allowing users to organize their troubleshooting work over time.

**Features:**
- **Case CRUD**: Create, read, update, and delete cases
- **User Isolation**: Each user only sees their own cases
- **Session Linking**: Associate cases with troubleshooting sessions
- **Status Tracking**: Monitor case progression (active → investigating → resolved/archived/closed)
- **Flexible Categorization**: Organize by severity (low/medium/high/critical) and category (performance/error/configuration/infrastructure/security/other)
- **Metadata & Tags**: Attach custom metadata and tags for advanced organization
- **Auto-generated Titles**: Automatic title generation if not provided (Case-MMDD-N format)
- **Pagination**: Efficient list endpoints with filtering

## Quick Start

### Using Docker (Recommended)

```bash
docker run -p 8003:8003 -v ./data:/data faultmaven/fm-case-service:latest
```

The service will be available at `http://localhost:8003`. Data persists in the `./data` directory.

### Using Docker Compose

See [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) for complete deployment with all FaultMaven services.

### Development Setup

```bash
# Clone repository
git clone https://github.com/FaultMaven/fm-case-service.git
cd fm-case-service

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run service
uvicorn case_service.main:app --reload --port 8003
```

The service creates a SQLite database at `./fm_cases.db` on first run.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/cases` | Create new case |
| GET | `/api/v1/cases/{case_id}` | Get case details |
| PUT | `/api/v1/cases/{case_id}` | Update case |
| DELETE | `/api/v1/cases/{case_id}` | Delete case |
| GET | `/api/v1/cases` | List user's cases (paginated) |
| GET | `/api/v1/cases/session/{session_id}` | Get cases for a session |
| POST | `/api/v1/cases/{case_id}/status` | Update case status |
| GET | `/health` | Health check |

## Configuration

Configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_NAME` | Service identifier | `fm-case-service` |
| `ENVIRONMENT` | Deployment environment | `development` |
| `PORT` | Service port | `8003` |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./fm_cases.db` |
| `DEFAULT_PAGE_SIZE` | Default pagination size | `50` |
| `MAX_PAGE_SIZE` | Maximum pagination size | `100` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Case Data Model

```json
{
    "case_id": "case_abc123def456",
    "user_id": "user_123",
    "session_id": "session_xyz789",
    "title": "Database connection timeout",
    "description": "Users experiencing intermittent connection timeouts",
    "status": "investigating",
    "severity": "high",
    "category": "performance",
    "metadata": {},
    "tags": ["database", "timeout"],
    "created_at": "2025-11-15T10:30:00Z",
    "updated_at": "2025-11-15T12:45:00Z",
    "resolved_at": null
}
```

### Status Values
- `active` - Case created, not yet being investigated
- `investigating` - Active investigation in progress
- `resolved` - Issue resolved successfully
- `archived` - Case archived for reference
- `closed` - Case closed without resolution

### Severity Levels
- `low` - Minor issues with workarounds
- `medium` - Normal priority issues
- `high` - Significant impact requiring attention
- `critical` - Urgent issues blocking operations

### Categories
- `performance` - Performance degradation
- `error` - Error messages or exceptions
- `configuration` - Configuration problems
- `infrastructure` - Infrastructure issues
- `security` - Security concerns
- `other` - Uncategorized issues

## Authorization

This service uses **trusted header authentication** from the FaultMaven API Gateway:

- `X-User-ID` (required): Identifies the user making the request
- `X-User-Email` (optional): User's email address
- `X-User-Roles` (optional): User's roles

All case operations are scoped to the user specified in `X-User-ID`. Users can only access their own cases.

**Important**: This service should run behind the [fm-api-gateway](https://github.com/FaultMaven/faultmaven) which handles authentication and sets these headers. Never expose this service directly to the internet.

## Architecture

```
┌─────────────────┐
│  API Gateway    │ (Handles authentication)
└────────┬────────┘
         │ X-User-ID header
         ↓
┌─────────────────┐
│  Case Service   │ (Trusts headers)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  SQLite DB      │ (User-scoped data)
└─────────────────┘
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

## Related Projects

- [faultmaven](https://github.com/FaultMaven/faultmaven) - Main backend with API Gateway
- [faultmaven-copilot](https://github.com/FaultMaven/faultmaven-copilot) - Browser extension UI
- [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) - Docker Compose deployment

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read our contributing guidelines and code of conduct.
