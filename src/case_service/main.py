"""Main FastAPI application for fm-case-service."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from case_service.config import settings
from case_service.infrastructure.database import db_client
from case_service.api.routes.cases import router as cases_router
from case_service.models import HealthResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="FaultMaven Case Service",
    description="Microservice for case management",
    version="1.0.0",
)

# Service-to-service JWT authentication removed - services trust X-User-* headers from API Gateway
# The gateway validates user JWTs and adds X-User-* headers after stripping any client-provided ones
logger.info("Service trusts X-User-* headers from API Gateway (no JWT validation)")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cases_router)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    logger.info(f"Starting {settings.service_name} on port {settings.port}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database: {settings.database_url}")

    try:
        # Verify connection with retry logic (handles K8s/scale-to-zero)
        await db_client.verify_connection()

        # Note: Alembic migrations run in Dockerfile CMD before uvicorn starts
        # create_tables() is kept for backward compatibility with non-Docker setups
        await db_client.create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    """Clean up resources on shutdown."""
    logger.info("Shutting down service")
    await db_client.close()


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="""
Returns the health status of the Case Service.

**Workflow**:
1. Checks service availability
2. Reports database connection type
3. Returns service metadata

**Response Example**:
```json
{
  "status": "healthy",
  "service": "fm-case-service",
  "version": "1.0.0",
  "database": "sqlite+aiosqlite"
}
```

**Use Cases**:
- Kubernetes liveness/readiness probes
- Load balancer health checks
- Service mesh health monitoring
- Docker Compose healthcheck

**Storage**: No database query (reports connection type only)
**Rate Limits**: None
**Authorization**: None required (public endpoint)
    """,
    responses={
        200: {"description": "Service is healthy and operational"},
        500: {"description": "Service is unhealthy or experiencing issues"}
    }
)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version="1.0.0",
        database=settings.database_url.split("://")[0],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "case_service.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
    )
