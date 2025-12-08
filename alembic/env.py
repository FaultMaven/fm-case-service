"""Alembic environment configuration (Async Mode).

This env.py is configured for ASYNC SQLAlchemy operations.
It uses run_async() to properly handle async engine connections.

CRITICAL: Standard Alembic templates use SYNC operations which will fail
with async SQLAlchemy engines. This configuration fixes that trap.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add src directory to path to import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Alembic Config object
config = context.config

# Interpret the config file for Python logging (if present)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No target metadata - we use manual migrations only (not autogenerate)
# The 10-table hybrid schema is defined in explicit migration files
target_metadata = None

# Get DATABASE_URL from environment (deployment neutral)
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Override alembic.ini with environment variable
    config.set_main_option("sqlalchemy.url", database_url)
    print(f"[Alembic] Using DATABASE_URL from environment: {database_url}")
else:
    # Fallback to alembic.ini (for local development)
    database_url = config.get_main_option("sqlalchemy.url")
    if not database_url:
        # Ultimate fallback: SQLite
        database_url = "sqlite+aiosqlite:///./data/faultmaven.db"
        config.set_main_option("sqlalchemy.url", database_url)
        print(f"[Alembic] No DATABASE_URL found, using fallback: {database_url}")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well.  By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with an active connection.

    This is called by run_async() in online mode.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with ASYNC engine.

    CRITICAL: This uses run_async() to properly handle async connections.
    Without this, Alembic will try to use sync operations and fail.
    """
    # Create async engine from alembic config
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async).

    This is the entry point for normal migration execution.
    """
    asyncio.run(run_async_migrations())


# Determine which mode to run in
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
