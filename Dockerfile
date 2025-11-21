# FaultMaven Case Service - PUBLIC Open Source Version
# Apache 2.0 License

FROM python:3.11-slim

WORKDIR /app

# Install git (for fm-core-lib dependency) and poetry
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir poetry==1.7.0

# Copy dependency files and install
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

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
