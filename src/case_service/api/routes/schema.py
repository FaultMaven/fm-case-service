"""Schema metadata endpoint for database introspection.

Exposes database schema information for unified documentation aggregation.
This endpoint is excluded from OpenAPI docs (internal use only).
"""

import logging
from typing import Any, Dict, List
from fastapi import APIRouter
from sqlalchemy import inspect

from case_service.infrastructure.database.client import db_client
from case_service.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Schema"])


@router.get("/schema.json", include_in_schema=False)
async def get_schema() -> Dict[str, Any]:
    """
    Expose database schema metadata for documentation and ER diagram generation.

    This endpoint introspects the actual database schema (not just SQLAlchemy models)
    to provide accurate schema information including:
    - Tables and columns with types
    - Primary keys and foreign keys
    - Indexes
    - JSONB column schemas (for hybrid schema documentation)

    Returns:
        Schema metadata in unified format compatible with schema aggregation.

    Note:
        This endpoint is excluded from OpenAPI documentation (internal use only).
        Used by fm-api-gateway's SchemaAggregator for unified schema delivery.
    """
    inspector = inspect(db_client.engine.sync_engine)

    # Get current Alembic migration version
    alembic_version = "unknown"
    try:
        async with db_client.engine.begin() as conn:
            result = await conn.execute(
                "SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"
            )
            row = result.fetchone()
            if row:
                alembic_version = row[0]
    except Exception as e:
        logger.warning(f"Could not fetch Alembic version: {e}")

    schema_metadata = {
        "service": "fm-case-service",
        "database_type": "postgresql" if "postgresql" in settings.database_url else "sqlite",
        "version": "1.0.0",
        "alembic_version": alembic_version,
        "tables": []
    }

    # Introspect all tables
    for table_name in inspector.get_table_names():
        table_info = {
            "name": table_name,
            "description": _get_table_description(table_name),
            "columns": [],
            "indexes": [],
            "foreign_keys": []
        }

        # Get columns
        for column in inspector.get_columns(table_name):
            col_info = {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column["nullable"],
                "primary_key": column.get("primary_key", False),
                "default": str(column.get("default")) if column.get("default") else None
            }

            # Special handling for JSONB/JSON columns (hybrid schema)
            column_type_str = str(column["type"]).upper()
            if "JSON" in column_type_str or "JSONB" in column_type_str:
                # Document JSONB schema if available
                jsonb_schema = _get_jsonb_schema_metadata(table_name, column["name"])
                if jsonb_schema:
                    col_info["jsonb_schema"] = jsonb_schema

            table_info["columns"].append(col_info)

        # Get foreign keys
        for fk in inspector.get_foreign_keys(table_name):
            table_info["foreign_keys"].append({
                "constrained_columns": fk["constrained_columns"],
                "referred_table": fk["referred_table"],
                "referred_columns": fk["referred_columns"]
            })

        # Get indexes
        for index in inspector.get_indexes(table_name):
            table_info["indexes"].append({
                "name": index["name"],
                "columns": index["column_names"],
                "unique": index["unique"]
            })

        schema_metadata["tables"].append(table_info)

    return schema_metadata


def _get_table_description(table_name: str) -> str:
    """Get human-readable description for table."""
    descriptions = {
        "cases": "Troubleshooting cases with hybrid JSONB fields for flexible metadata",
        "hypotheses": "Root cause hypotheses linked to cases",
        "solutions": "Proposed and implemented solutions for cases",
        "case_messages": "Conversation history and AI agent interactions",
        "evidence": "Evidence artifacts linked to cases",
        "uploaded_files": "File upload metadata and references",
        "case_status_transitions": "Audit trail of case status changes",
        "case_tags": "Tag assignments for case categorization",
        "agent_tool_calls": "Tool usage tracking for AI agent calls",
        "alembic_version": "Database migration version tracking"
    }
    return descriptions.get(table_name, f"{table_name} table")


def _get_jsonb_schema_metadata(table_name: str, column_name: str) -> Dict[str, Any] | None:
    """
    Get JSONB schema documentation for hybrid schema columns.

    fm-case-service uses hybrid normalized + JSONB design:
    - Normalized tables for high-cardinality data (hypotheses, solutions)
    - JSONB columns for flexible, low-cardinality fields (metadata, tags)

    This documents the expected structure of JSONB columns.
    """
    # Currently, case metadata fields are stored in separate JSONB columns in the cases table
    # Document known JSONB schemas here

    if table_name == "cases" and column_name == "metadata":
        return {
            "type": "object",
            "description": "Additional case metadata (flexible JSON structure)",
            "properties": {
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "environment": {"type": "string", "description": "Environment where issue occurred"},
                "affected_systems": {"type": "array", "items": {"type": "string"}},
                "custom_fields": {"type": "object", "description": "User-defined custom fields"}
            }
        }

    if table_name == "case_messages" and column_name == "metadata":
        return {
            "type": "object",
            "description": "Message metadata (tool calls, attachments, etc.)",
            "properties": {
                "tool_calls": {"type": "array", "description": "AI agent tool invocations"},
                "attachments": {"type": "array", "description": "File attachments"},
                "internal_notes": {"type": "boolean", "description": "Whether message is internal"}
            }
        }

    # Return None if no schema documentation available
    return None
