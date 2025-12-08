"""Database client for SQLite/PostgreSQL connections."""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from fm_core_lib.utils import service_startup_retry

from case_service.config import settings

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Async database client for SQLAlchemy."""

    def __init__(self):
        """Initialize database engine and session factory."""
        # For SQLite, use NullPool to avoid connection issues
        # For PostgreSQL, use default pool
        pool_class = NullPool if "sqlite" in settings.database_url else None

        self.engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "DEBUG",
            poolclass=pool_class,
        )

        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info(f"Database client initialized with URL: {settings.database_url}")

    @service_startup_retry
    async def verify_connection(self):
        """Verify database connection with retry logic.

        This is called before migrations/table creation to ensure the database
        is ready. Retries with exponential backoff for K8s/scale-to-zero scenarios.
        """
        async with self.engine.begin() as conn:
            # Simple query to verify connection works
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")

    async def create_tables(self):
        """Create all database tables via Alembic migrations.

        NOTE: Tables are now managed by Alembic migrations, not ORM.
        Run 'alembic upgrade head' to create/update database schema.
        This method is kept for backward compatibility but does nothing.
        """
        logger.info("Database tables managed by Alembic migrations")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session for dependency injection."""
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        """Close database engine."""
        await self.engine.dispose()
        logger.info("Database client closed")


# Global database client instance
db_client = DatabaseClient()
