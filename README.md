# fm-case-service

> **Auto-generated API docs** | Last updated: **2025-12-20 11:04 UTC** | Endpoints: **34**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/faultmaven/fm-case-service)
[![Auto-Docs](https://img.shields.io/badge/docs-auto--generated-success.svg)](.github/workflows/generate-docs.yml)

## Overview

**Microservice for case management** - Part of the FaultMaven troubleshooting platform.

The Case Service manages the lifecycle of troubleshooting cases in FaultMaven. Cases are persistent containers that track investigations across multiple sessions, allowing users to organize their troubleshooting work over time.

**Key Features:**
- **Case CRUD**: Create, read, update, and delete cases
- **User Isolation**: Each user only sees their own cases (enforced via X-User-ID header)
- **Session Linking**: Associate cases with troubleshooting sessions from fm-session-service
- **Status Tracking**: Monitor case progression (active → investigating → resolved/archived/closed)
- **Flexible Categorization**: Organize by severity (low/medium/high/critical) and category (performance/error/configuration/infrastructure/security/other)
- **Metadata & Tags**: Attach custom metadata and tags for advanced organization
- **Auto-generated Titles**: Automatic title generation if not provided (Case-MMDD-N format)
- **Pagination**: Efficient list endpoints with filtering by status

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
| GET | `/health` | Health Check |
| POST | `/api/v1/cases` | Create new troubleshooting case |
| GET | `/api/v1/cases` | List user's cases with pagination |
| GET | `/api/v1/cases/analytics/summary` | Get case analytics summary |
| GET | `/api/v1/cases/analytics/trends` | Get case trends |
| GET | `/api/v1/cases/health` | Get case service health |
| GET | `/api/v1/cases/reports` | List available reports |
| GET | `/api/v1/cases/reports/{report_id}` | Get specific report |
| POST | `/api/v1/cases/search` | Search cases |
| GET | `/api/v1/cases/session/{session_id}` | Get cases linked to a session |
| GET | `/api/v1/cases/{case_id}` | Get case by ID |
| PUT | `/api/v1/cases/{case_id}` | Update case details |
| DELETE | `/api/v1/cases/{case_id}` | Delete case permanently |
| GET | `/api/v1/cases/{case_id}/analytics` | Get case analytics |
| POST | `/api/v1/cases/{case_id}/close` | Close a case |
| GET | `/api/v1/cases/{case_id}/data` | List case data |
| POST | `/api/v1/cases/{case_id}/data` | Add evidence/data to case |
| GET | `/api/v1/cases/{case_id}/data/{data_id}` | Get case data |
| DELETE | `/api/v1/cases/{case_id}/data/{data_id}` | Delete case data |
| GET | `/api/v1/cases/{case_id}/evidence/{evidence_id}` | Get specific evidence by ID |
| POST | `/api/v1/cases/{case_id}/hypotheses` | Add hypothesis to case |
| PUT | `/api/v1/cases/{case_id}/hypotheses/{hypothesis_id}` | Update hypothesis |
| GET | `/api/v1/cases/{case_id}/messages` | Get case messages |
| POST | `/api/v1/cases/{case_id}/queries` | Submit case query |
| GET | `/api/v1/cases/{case_id}/queries` | Get case query history |
| GET | `/api/v1/cases/{case_id}/report-recommendations` | Get report recommendations |
| POST | `/api/v1/cases/{case_id}/reports` | Generate case reports |
| GET | `/api/v1/cases/{case_id}/reports` | Get case reports |
| GET | `/api/v1/cases/{case_id}/reports/{report_id}/download` | Download case report |
| POST | `/api/v1/cases/{case_id}/status` | Update case status |
| POST | `/api/v1/cases/{case_id}/title` | Generate case title |
| GET | `/api/v1/cases/{case_id}/ui` | Get case UI data |
| GET | `/api/v1/cases/{case_id}/uploaded-files` | Get uploaded files for case |
| GET | `/api/v1/cases/{case_id}/uploaded-files/{file_id}` | Get uploaded file details |


**OpenAPI Documentation**: See [docs/api/openapi.json](docs/api/openapi.json) or [docs/api/openapi.yaml](docs/api/openapi.yaml) for complete API specification.

## Common Response Codes

- **200**: Case status updated successfully
- **201**: Case created successfully
- **204**: Case deleted successfully (no content returned)
- **400**: Invalid request - at least one report type required
- **401**: Unauthorized - missing X-User-ID header
- **403**: Forbidden - not authorized to access this case
- **404**: Report not found or access denied
- **422**: Validation Error
- **500**: Internal server error - database operation failed
- **501**: Feature not yet implemented


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
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `*` |
| `LOG_LEVEL` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |

Example `.env` file:

```env
ENVIRONMENT=production
PORT=8003
DATABASE_URL=sqlite+aiosqlite:///./data/fm_cases.db
LOG_LEVEL=INFO
CORS_ORIGINS=https://app.faultmaven.com,https://admin.faultmaven.com
```

## Case Data Model

Example Case Object:

```json
{
    "case_id": "case_abc123def456",
    "user_id": "user_123",
    "session_id": "session_xyz789",
    "title": "Database connection timeout in production",
    "description": "Users experiencing intermittent connection timeouts on RDS instance",
    "status": "investigating",
    "severity": "high",
    "category": "performance",
    "metadata": {"environment": "production", "affected_users": 42},
    "tags": ["database", "timeout", "rds"],
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
- `low` - Minor issues with workarounds available
- `medium` - Normal priority issues
- `high` - Significant impact requiring attention
- `critical` - Urgent issues blocking operations

### Categories
- `performance` - Performance degradation or slowness
- `error` - Error messages or exceptions
- `configuration` - Configuration problems
- `infrastructure` - Infrastructure issues (servers, network, etc.)
- `security` - Security concerns or vulnerabilities
- `other` - Uncategorized issues

## Authorization

This service uses **trusted header authentication** from the FaultMaven API Gateway:

**Required Headers:**

- `X-User-ID` (required): Identifies the user making the request

**Optional Headers:**

- `X-User-Email`: User's email address
- `X-User-Roles`: User's roles (comma-separated)

All case operations are scoped to the user specified in `X-User-ID`. Users can only access their own cases.

**Security Model:**

- User isolation enforced at database query level
- All endpoints validate X-User-ID header presence
- Cross-user access attempts return 404 (not 403) to prevent enumeration
- Service trusts headers set by upstream gateway

**Important**: This service should run behind the [fm-api-gateway](https://github.com/FaultMaven/faultmaven) which handles authentication and sets these headers. Never expose this service directly to the internet.

## Architecture

```
┌─────────────────────────┐
│  FaultMaven API Gateway │  Handles authentication (Clerk)
│  (Port 8000)            │  Sets X-User-ID header
└───────────┬─────────────┘
            │ Trusted headers (X-User-ID)
            ↓
┌─────────────────────────┐
│  fm-case-service        │  Trusts gateway headers
│  (Port 8003)            │  Enforces user isolation
└───────────┬─────────────┘
            │ SQLAlchemy ORM
            ↓
┌─────────────────────────┐
│  SQLite Database        │  fm_cases.db
│  (Local file)           │  User-scoped data
└─────────────────────────┘
```

**Related Services:**
- fm-session-service (8001) - Investigation sessions
- fm-knowledge-service (8002) - Knowledge base
- fm-evidence-service (8004) - Evidence artifacts

**Storage Details:**

- **Database**: SQLite with aiosqlite async driver
- **Location**: `./fm_cases.db` (configurable via DATABASE_URL)
- **Schema**: Auto-created on startup via SQLAlchemy
- **Indexes**: Optimized for user_id and session_id lookups
- **Migrations**: Not required (schema auto-managed)

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=case_service --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_cases.py -v

# Run with debug output
pytest -vv -s
```

**Test Coverage Goals:**

- Unit tests: Core business logic (CaseManager)
- Integration tests: Database operations
- API tests: Endpoint behavior and validation
- Target coverage: >80%

## Development Workflow

```bash
# Format code with black
black src/ tests/

# Lint with flake8
flake8 src/ tests/

# Type check with mypy
mypy src/

# Run all quality checks
black src/ tests/ && flake8 src/ tests/ && mypy src/ && pytest
```

## Related Projects

- [faultmaven](https://github.com/FaultMaven/faultmaven) - Main backend with API Gateway and orchestration
- [faultmaven-copilot](https://github.com/FaultMaven/faultmaven-copilot) - Browser extension UI for troubleshooting
- [faultmaven-deploy](https://github.com/FaultMaven/faultmaven-deploy) - Docker Compose deployment configurations
- [fm-session-service](https://github.com/FaultMaven/fm-session-service) - Investigation session management
- [fm-knowledge-service](https://github.com/FaultMaven/fm-knowledge-service) - Knowledge base and recommendations
- [fm-evidence-service](https://github.com/FaultMaven/fm-evidence-service) - Evidence artifact storage

## CI/CD

This repository uses **GitHub Actions** for automated documentation generation:

**Trigger**: Every push to `main` or `develop` branches

**Process**:
1. Generate OpenAPI spec (JSON + YAML)
2. Validate documentation completeness (fails if endpoints lack descriptions)
3. Auto-generate API tables in this README from code
4. Commit changes back to repository (if on main)

See [.github/workflows/generate-docs.yml](.github/workflows/generate-docs.yml) for implementation details.

**Documentation Guarantee**: The API sections of this README are always in sync with the actual code. Any endpoint changes automatically trigger documentation updates.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and quality checks (`pytest && black . && flake8`)
5. Commit with clear messages (`git commit -m 'feat: Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

**Code Style**: Black formatting, flake8 linting, mypy type checking
**Commit Convention**: Conventional Commits (feat/fix/docs/refactor/test/chore)

---

**Documentation Statistics**
- Total endpoints: 34
- Last generated: 2025-12-20 11:04 UTC
- OpenAPI spec version: 1.0.0
- Generator: scripts/generate_readme.py
- Template: README_TEMPLATE.md

*API sections are automatically updated on every commit. Prose sections are human-editable.*
