# FaultMaven Case Service - PUBLIC Open Source Version
# Apache 2.0 License

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.0

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Export dependencies to requirements.txt (no dev dependencies)
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create data directory for SQLite database
RUN mkdir -p /data && chmod 777 /data

# Set PYTHONPATH to include src directory
ENV PYTHONPATH=/app/src:$PYTHONPATH

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8003/health', timeout=2)"

# Run service
CMD ["python", "-m", "uvicorn", "case_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
