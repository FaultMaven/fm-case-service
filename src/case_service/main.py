"""Main FastAPI application for fm-case-service."""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fm_core_lib.auth import ServiceAuthMiddleware

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


# Load service authentication public key
def load_service_public_key() -> str:
    """Load RSA public key for service token verification."""
    public_key_path = Path("/app/config/service-public-key.pem")

    if not public_key_path.exists():
        logger.warning(f"Service public key not found at {public_key_path}")
        logger.warning("Service-to-service authentication will be DISABLED")
        return None

    with open(public_key_path, "r") as f:
        return f.read()


# Add Service Authentication Middleware
public_key = load_service_public_key()
if public_key:
    app.add_middleware(
        ServiceAuthMiddleware,
        public_key=public_key,
        jwt_algorithm="RS256",
        jwt_audience="faultmaven-api",
        jwt_issuer="fm-auth-service",
        skip_paths=["/health", "/docs", "/openapi.json"],
    )
    logger.info("Service authentication middleware enabled")
else:
    logger.warning("Service authentication middleware DISABLED - no public key found")

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


@app.get("/health", response_model=HealthResponse)
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
