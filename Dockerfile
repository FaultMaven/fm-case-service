# FaultMaven Case Service - PUBLIC Open Source Version
# Apache 2.0 License

FROM python:3.11-slim

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.0

# Copy fm-core-lib first (required dependency)
COPY fm-core-lib/ ./fm-core-lib/
RUN pip install --no-cache-dir ./fm-core-lib

# Copy dependency files and install
COPY fm-case-service/pyproject.toml ./
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi --no-root

# Copy source code and migrations
COPY fm-case-service/src/ ./src/
COPY fm-case-service/alembic/ ./alembic/
COPY fm-case-service/alembic.ini ./

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
