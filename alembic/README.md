# Database Migrations

This directory contains Alembic migrations for fm-case-service.

## Configuration

This Alembic setup is configured for **async SQLAlchemy** operations. The `env.py` file uses `run_async()` to properly handle async database connections, avoiding the common sync/async mismatch trap.

### Database URL Priority

1. **Environment Variable**: `DATABASE_URL` (deployment neutral)
2. **Fallback**: SQLite at `./data/faultmaven.db`

### Supported Databases

- SQLite (via `aiosqlite`)
- PostgreSQL (via `asyncpg`)

## Usage

### Generate Initial Migration

```bash
# From fm-case-service directory
alembic revision --autogenerate -m "initial schema"
```

### Run Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history
```

### Create Manual Migration

```bash
alembic revision -m "add new column"
```

## Docker Integration

Migrations run automatically on container startup via the entrypoint:

```bash
# Run migrations before starting the service
alembic upgrade head && uvicorn case_service.main:app --host 0.0.0.0 --port 8000
```

## Production Notes

- Migrations are **idempotent** - safe to run multiple times
- Downtime during schema changes depends on migration type
- For zero-downtime deployments, use blue-green deployment strategy
- Always backup database before running migrations in production

## Troubleshooting

### "No such table" errors

Run migrations:
```bash
alembic upgrade head
```

### "AsyncEngine" errors

The `env.py` is configured for async operations. If you see sync-related errors, verify that `run_async()` is being used correctly.

### Connection errors

Check `DATABASE_URL` environment variable:
```bash
echo $DATABASE_URL
```

For SQLite, ensure the data directory exists:
```bash
mkdir -p ./data
```
