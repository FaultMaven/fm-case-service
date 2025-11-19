#!/usr/bin/env python3
"""Auto-generate README.md from OpenAPI specification.

This script reads the OpenAPI spec generated from FastAPI and creates
a comprehensive README with endpoint documentation, examples, and statistics.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any


def load_openapi_spec() -> Dict[str, Any]:
    """Load OpenAPI spec from docs/api/openapi.json"""
    spec_path = Path(__file__).parent.parent / "docs" / "api" / "openapi.json"

    if not spec_path.exists():
        raise FileNotFoundError(
            f"OpenAPI spec not found at {spec_path}. "
            "Run the app to generate it first."
        )

    with open(spec_path, 'r') as f:
        return json.load(f)


def generate_endpoint_table(spec: Dict[str, Any]) -> str:
    """Generate markdown table of endpoints"""
    endpoints = []

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                # Extract summary or use path as fallback
                summary = details.get('summary', path)

                endpoints.append({
                    'method': method.upper(),
                    'path': path,
                    'summary': summary
                })

    # Sort endpoints: health first, then by path
    def sort_key(e):
        if e['path'] == '/health':
            return (0, '')
        return (1, e['path'])

    endpoints.sort(key=sort_key)

    # Build markdown table
    table = "| Method | Endpoint | Description |\n"
    table += "|--------|----------|-------------|\n"

    for endpoint in endpoints:
        table += f"| {endpoint['method']} | `{endpoint['path']}` | {endpoint['summary']} |\n"

    return table


def extract_response_codes(spec: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Extract unique response codes and their descriptions across all endpoints"""
    response_info = {}

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                for code, response_details in details.get('responses', {}).items():
                    desc = response_details.get('description', 'No description')
                    if code not in response_info:
                        response_info[code] = set()
                    response_info[code].add(desc)

    return response_info


def generate_response_codes_section(spec: Dict[str, Any]) -> str:
    """Generate response codes documentation"""
    response_info = extract_response_codes(spec)

    if not response_info:
        return ""

    section = "\n## Common Response Codes\n\n"

    # Sort codes numerically
    for code in sorted(response_info.keys(), key=lambda x: int(x)):
        descriptions = list(response_info[code])
        section += f"- **{code}**: {descriptions[0]}\n"

    return section


def count_endpoints(spec: Dict[str, Any]) -> int:
    """Count total number of endpoints"""
    count = 0
    for path, methods in spec.get('paths', {}).items():
        for method in methods.keys():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                count += 1
    return count


def main():
    """Generate README.md from OpenAPI specification"""
    print("🚀 Generating README.md from OpenAPI specification...")

    # Load spec
    spec = load_openapi_spec()

    # Extract metadata
    info = spec.get('info', {})
    title = info.get('title', 'fm-case-service')
    version = info.get('version', '1.0.0')
    description = info.get('description', 'Microservice for case management')

    # Generate sections
    endpoint_table = generate_endpoint_table(spec)
    response_codes = generate_response_codes_section(spec)
    total_endpoints = count_endpoints(spec)
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    # Build README content
    readme_content = f"""# {title}

> **🤖 This README is auto-generated** from code on every commit.
> Last updated: **{timestamp}** | Total endpoints: **{total_endpoints}**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/faultmaven/fm-case-service)
[![Auto-Docs](https://img.shields.io/badge/docs-auto--generated-success.svg)](.github/workflows/generate-docs.yml)

## Overview

**{description}** - Part of the FaultMaven troubleshooting platform.

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
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate

# Install dependencies
pip install -e .

# Run service
uvicorn case_service.main:app --reload --port 8003
```

The service creates a SQLite database at `./fm_cases.db` on first run.

## API Endpoints

{endpoint_table}

**OpenAPI Documentation**: See [docs/api/openapi.json](docs/api/openapi.json) or [docs/api/openapi.yaml](docs/api/openapi.yaml) for complete API specification.
{response_codes}

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
{{
    "case_id": "case_abc123def456",
    "user_id": "user_123",
    "session_id": "session_xyz789",
    "title": "Database connection timeout in production",
    "description": "Users experiencing intermittent connection timeouts on RDS instance",
    "status": "investigating",
    "severity": "high",
    "category": "performance",
    "metadata": {{"environment": "production", "affected_users": 42}},
    "tags": ["database", "timeout", "rds"],
    "created_at": "2025-11-15T10:30:00Z",
    "updated_at": "2025-11-15T12:45:00Z",
    "resolved_at": null
}}
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

- ✅ User isolation enforced at database query level
- ✅ All endpoints validate X-User-ID header presence
- ✅ Cross-user access attempts return 404 (not 403) to prevent enumeration
- ⚠️ Service trusts headers set by upstream gateway

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
3. Auto-generate this README from code
4. Commit changes back to repository (if on main)

See [.github/workflows/generate-docs.yml](.github/workflows/generate-docs.yml) for implementation details.

**Documentation Guarantee**: This README is always in sync with the actual code. Any endpoint changes automatically trigger documentation updates.

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

**📊 Documentation Statistics**
- Total endpoints: {total_endpoints}
- Last generated: {timestamp}
- OpenAPI spec version: {version}
- Generator: scripts/generate_readme.py
- CI/CD: GitHub Actions

*This README is automatically updated on every commit to ensure zero documentation drift.*
"""

    # Write README
    readme_path = Path(__file__).parent.parent / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"✅ README.md generated successfully")
    print(f"   Location: {readme_path}")
    print(f"   Total endpoints documented: {total_endpoints}")
    print(f"   Timestamp: {timestamp}")


if __name__ == "__main__":
    main()
