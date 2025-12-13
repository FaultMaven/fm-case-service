# FaultMaven Case Service - PUBLIC Open Source Version
# Apache 2.0 License

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.0

# Copy fm-core-lib first (required dependency)
COPY fm-core-lib/ ./fm-core-lib/

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Export dependencies to requirements.txt (no dev dependencies)
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev || \
    echo "fastapi>=0.109.0\nuvicorn[standard]>=0.27.0\npydantic>=2.5.0\npydantic-settings>=2.1.0\npython-dotenv>=1.0.0\nsqlalchemy[asyncio]>=2.0.25\naiosqlite>=0.19.0\nalembic>=1.13.0\nasyncpg>=0.29.0\nhttpx>=0.28.1\npyjwt>=2.8.0\ncryptography>=41.0.0" > requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install fm-core-lib
COPY --from=builder /app/fm-core-lib/ ./fm-core-lib/
RUN pip install --no-cache-dir ./fm-core-lib

# Copy source code and migrations
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Create data directory for SQLite database
RUN mkdir -p /data && chmod 777 /data

# Set PYTHONPATH to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=2)"

# Run migrations then start service
# Migrations are idempotent - safe to run on every startup
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn case_service.main:app --host 0.0.0.0 --port 8000"]
