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
