"""Initial hybrid schema with 10 tables

Revision ID: 002_hybrid_schema
Revises: 001_initial
Create Date: 2025-02-08 00:00:00.000000

This migration creates the production-ready 10-table hybrid schema that matches
the authoritative FaultMaven-Mono design. It replaces the incomplete single-table
schema with:
  - 1 core table (cases) with JSONB columns for flexible low-cardinality data
  - 6 normalized tables for high-cardinality data (evidence, hypotheses, solutions, etc.)
  - 3 supporting tables (tags, status transitions, tool calls)

Design Reference: FaultMaven-Mono/docs/architecture/case-storage-design.md
Source Schema: FaultMaven-Mono/docs/schema/001_initial_hybrid_schema.sql
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_hybrid_schema'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace single-table schema with complete 10-table hybrid schema."""

    # ========================================================================
    # STEP 1: Drop old single-table schema
    # ========================================================================

    # Drop indexes if they exist (SQLite doesn't support IF EXISTS in Alembic)
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Check if table exists
    if 'cases' in inspector.get_table_names():
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('cases')]

        # Drop indexes only if they exist
        if 'ix_cases_created_at' in existing_indexes:
            op.drop_index(op.f('ix_cases_created_at'), table_name='cases')
        if 'ix_cases_status' in existing_indexes:
            op.drop_index(op.f('ix_cases_status'), table_name='cases')
        if 'ix_cases_session_id' in existing_indexes:
            op.drop_index(op.f('ix_cases_session_id'), table_name='cases')
        if 'ix_cases_user_id' in existing_indexes:
            op.drop_index(op.f('ix_cases_user_id'), table_name='cases')
        if 'ix_cases_case_id' in existing_indexes:
            op.drop_index(op.f('ix_cases_case_id'), table_name='cases')

        op.drop_table('cases')

    # Drop old enum types (PostgreSQL only)
    # SQLAlchemy will automatically handle enum creation/deletion per database
    sa.Enum(name='casestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='caseseverity').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='casecategory').drop(op.get_bind(), checkfirst=True)

    # ========================================================================
    # STEP 2: Create new enum types (database-neutral)
    # ========================================================================

    # PostgreSQL: native ENUM, SQLite: TEXT with CHECK constraint
    case_status = sa.Enum(
        'consulting', 'investigating', 'resolved', 'closed',
        name='case_status',
        create_type=True
    )

    evidence_category = sa.Enum(
        'LOGS_AND_ERRORS', 'STRUCTURED_CONFIG', 'METRICS_AND_PERFORMANCE',
        'UNSTRUCTURED_TEXT', 'SOURCE_CODE', 'VISUAL_EVIDENCE', 'UNKNOWN',
        name='evidence_category',
        create_type=True
    )

    hypothesis_status = sa.Enum(
        'proposed', 'testing', 'validated', 'invalidated', 'deferred',
        name='hypothesis_status',
        create_type=True
    )

    solution_status = sa.Enum(
        'proposed', 'in_progress', 'implemented', 'verified', 'rejected',
        name='solution_status',
        create_type=True
    )

    message_role = sa.Enum(
        'user', 'assistant', 'system',
        name='message_role',
        create_type=True
    )

    file_processing_status = sa.Enum(
        'pending', 'processing', 'completed', 'failed',
        name='file_processing_status',
        create_type=True
    )

    # ========================================================================
    # STEP 3: Create core cases table
    # ========================================================================

    op.create_table(
        'cases',
        # Primary Key
        sa.Column('case_id', sa.String(length=17), nullable=False),

        # Core Attributes
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('status', case_status, nullable=False, server_default='consulting'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),

        # JSON columns for low-cardinality flexible data
        # PostgreSQL: JSONB, SQLite: TEXT with JSON validation
        sa.Column('consulting', sa.JSON(), nullable=False, server_default='{"initial_description": "", "context": {}, "user_goals": []}'),
        sa.Column('problem_verification', sa.JSON(), nullable=True),
        sa.Column('working_conclusion', sa.JSON(), nullable=True),
        sa.Column('root_cause_conclusion', sa.JSON(), nullable=True),
        sa.Column('path_selection', sa.JSON(), nullable=True),
        sa.Column('degraded_mode', sa.JSON(), nullable=True),
        sa.Column('escalation_state', sa.JSON(), nullable=True),
        sa.Column('documentation', sa.JSON(), nullable=False, server_default='{"summary": "", "timeline": [], "lessons_learned": []}'),
        sa.Column('progress', sa.JSON(), nullable=False, server_default='{"current_phase": "consulting", "completion_percentage": 0, "milestones": []}'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),

        # Turn Tracking (added per fm-core-lib model)
        sa.Column('current_turn', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('turns_without_progress', sa.Integer(), nullable=False, server_default='0'),

        # Constraints
        sa.PrimaryKeyConstraint('case_id'),
        sa.CheckConstraint("LENGTH(TRIM(title)) > 0", name='cases_title_not_empty'),
        sa.CheckConstraint("LENGTH(TRIM(user_id)) > 0", name='cases_user_id_not_empty'),
        sa.CheckConstraint("LENGTH(TRIM(organization_id)) > 0", name='cases_organization_id_not_empty'),
    )

    # Indexes
    op.create_index('idx_cases_user_id', 'cases', ['user_id'])
    op.create_index('idx_cases_organization_id', 'cases', ['organization_id'])
    op.create_index('idx_cases_status', 'cases', ['status'])
    op.create_index('idx_cases_created_at', 'cases', ['created_at'])
    op.create_index('idx_cases_updated_at', 'cases', ['updated_at'])

    # GIN indexes for JSONB (PostgreSQL only, ignored by SQLite)
    op.create_index('idx_cases_consulting_gin', 'cases', ['consulting'], postgresql_using='gin')
    op.create_index('idx_cases_problem_verification_gin', 'cases', ['problem_verification'], postgresql_using='gin')
    op.create_index('idx_cases_metadata_gin', 'cases', ['metadata'], postgresql_using='gin')

    # ========================================================================
    # STEP 4: Create normalized tables for high-cardinality data
    # ========================================================================

    # Evidence table
    op.create_table(
        'evidence',
        sa.Column('evidence_id', sa.String(length=15), nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('category', evidence_category, nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=False),
        sa.Column('preprocessed_content', sa.Text(), nullable=False),
        sa.Column('content_ref', sa.String(length=1000), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('upload_timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('evidence_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.CheckConstraint("LENGTH(TRIM(summary)) > 0", name='evidence_summary_not_empty'),
        sa.CheckConstraint("LENGTH(TRIM(preprocessed_content)) > 0", name='evidence_content_not_empty'),
    )
    op.create_index('idx_evidence_case_id', 'evidence', ['case_id'])
    op.create_index('idx_evidence_category', 'evidence', ['category'])
    op.create_index('idx_evidence_upload_timestamp', 'evidence', ['upload_timestamp'])
    op.create_index('idx_evidence_metadata_gin', 'evidence', ['metadata'], postgresql_using='gin')

    # Hypotheses table
    op.create_table(
        'hypotheses',
        sa.Column('hypothesis_id', sa.String(length=15), nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', hypothesis_status, nullable=False, server_default='proposed'),
        sa.Column('confidence_score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('supporting_evidence_ids', sa.JSON(), nullable=True),  # PostgreSQL: ARRAY, SQLite: JSON
        sa.Column('validation_result', sa.Text(), nullable=True),
        sa.Column('validation_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('proposed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('hypothesis_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.CheckConstraint("LENGTH(TRIM(description)) > 0", name='hypotheses_description_not_empty'),
        sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name='hypotheses_confidence_range'),
    )
    op.create_index('idx_hypotheses_case_id', 'hypotheses', ['case_id'])
    op.create_index('idx_hypotheses_status', 'hypotheses', ['status'])
    op.create_index('idx_hypotheses_proposed_at', 'hypotheses', ['proposed_at'])
    op.create_index('idx_hypotheses_confidence_score', 'hypotheses', ['confidence_score'])

    # Solutions table
    op.create_table(
        'solutions',
        sa.Column('solution_id', sa.String(length=15), nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', solution_status, nullable=False, server_default='proposed'),
        sa.Column('implementation_steps', sa.JSON(), nullable=True),  # PostgreSQL: ARRAY, SQLite: JSON
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('estimated_effort', sa.String(length=50), nullable=True),
        sa.Column('verification_result', sa.Text(), nullable=True),
        sa.Column('verification_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('proposed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('implemented_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('solution_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.CheckConstraint("LENGTH(TRIM(description)) > 0", name='solutions_description_not_empty'),
        sa.CheckConstraint("risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'critical')", name='solutions_risk_level_valid'),
    )
    op.create_index('idx_solutions_case_id', 'solutions', ['case_id'])
    op.create_index('idx_solutions_status', 'solutions', ['status'])
    op.create_index('idx_solutions_proposed_at', 'solutions', ['proposed_at'])
    op.create_index('idx_solutions_risk_level', 'solutions', ['risk_level'])

    # Case messages table
    op.create_table(
        'case_messages',
        sa.Column('message_id', sa.String(length=20), nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('role', message_role, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('message_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.CheckConstraint("LENGTH(TRIM(content)) > 0", name='case_messages_content_not_empty'),
    )
    op.create_index('idx_case_messages_case_id', 'case_messages', ['case_id'])
    op.create_index('idx_case_messages_timestamp', 'case_messages', ['timestamp'])
    op.create_index('idx_case_messages_role', 'case_messages', ['role'])

    # Uploaded files table
    op.create_table(
        'uploaded_files',
        sa.Column('file_id', sa.String(length=15), nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('storage_path', sa.String(length=1000), nullable=True),
        sa.Column('processing_status', file_processing_status, nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('file_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.CheckConstraint("LENGTH(TRIM(filename)) > 0", name='uploaded_files_filename_not_empty'),
        sa.CheckConstraint("file_size > 0", name='uploaded_files_file_size_positive'),
    )
    op.create_index('idx_uploaded_files_case_id', 'uploaded_files', ['case_id'])
    op.create_index('idx_uploaded_files_uploaded_at', 'uploaded_files', ['uploaded_at'])
    op.create_index('idx_uploaded_files_processing_status', 'uploaded_files', ['processing_status'])

    # ========================================================================
    # STEP 5: Create supporting tables
    # ========================================================================

    # Case status transitions table (audit trail)
    op.create_table(
        'case_status_transitions',
        sa.Column('transition_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('from_status', case_status, nullable=True),
        sa.Column('to_status', case_status, nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('transitioned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('transition_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
    )
    op.create_index('idx_case_status_transitions_case_id', 'case_status_transitions', ['case_id'])
    op.create_index('idx_case_status_transitions_timestamp', 'case_status_transitions', ['transitioned_at'])

    # Case tags table
    op.create_table(
        'case_tags',
        sa.Column('tag_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('tag', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('tag_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('case_id', 'tag', name='case_tags_unique'),
        sa.CheckConstraint("LENGTH(TRIM(tag)) > 0", name='case_tags_tag_not_empty'),
    )
    op.create_index('idx_case_tags_case_id', 'case_tags', ['case_id'])
    op.create_index('idx_case_tags_tag', 'case_tags', ['tag'])

    # Agent tool calls table (observability)
    op.create_table(
        'agent_tool_calls',
        sa.Column('call_id', sa.String(length=20), nullable=False),
        sa.Column('case_id', sa.String(length=17), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('tool_input', sa.JSON(), nullable=False),
        sa.Column('tool_output', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('call_id'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.case_id'], ondelete='CASCADE'),
        sa.CheckConstraint("LENGTH(TRIM(tool_name)) > 0", name='agent_tool_calls_tool_name_not_empty'),
        sa.CheckConstraint("status IN ('pending', 'running', 'success', 'error')", name='agent_tool_calls_status_valid'),
    )
    op.create_index('idx_agent_tool_calls_case_id', 'agent_tool_calls', ['case_id'])
    op.create_index('idx_agent_tool_calls_tool_name', 'agent_tool_calls', ['tool_name'])
    op.create_index('idx_agent_tool_calls_status', 'agent_tool_calls', ['status'])
    op.create_index('idx_agent_tool_calls_started_at', 'agent_tool_calls', ['started_at'])
    op.create_index('idx_agent_tool_calls_tool_input_gin', 'agent_tool_calls', ['tool_input'], postgresql_using='gin')


def downgrade() -> None:
    """Drop 10-table hybrid schema and restore simple single-table schema."""

    # Drop all tables in reverse order (respecting foreign keys)
    op.drop_index('idx_agent_tool_calls_tool_input_gin', table_name='agent_tool_calls')
    op.drop_index('idx_agent_tool_calls_started_at', table_name='agent_tool_calls')
    op.drop_index('idx_agent_tool_calls_status', table_name='agent_tool_calls')
    op.drop_index('idx_agent_tool_calls_tool_name', table_name='agent_tool_calls')
    op.drop_index('idx_agent_tool_calls_case_id', table_name='agent_tool_calls')
    op.drop_table('agent_tool_calls')

    op.drop_index('idx_case_tags_tag', table_name='case_tags')
    op.drop_index('idx_case_tags_case_id', table_name='case_tags')
    op.drop_table('case_tags')

    op.drop_index('idx_case_status_transitions_timestamp', table_name='case_status_transitions')
    op.drop_index('idx_case_status_transitions_case_id', table_name='case_status_transitions')
    op.drop_table('case_status_transitions')

    op.drop_index('idx_uploaded_files_processing_status', table_name='uploaded_files')
    op.drop_index('idx_uploaded_files_uploaded_at', table_name='uploaded_files')
    op.drop_index('idx_uploaded_files_case_id', table_name='uploaded_files')
    op.drop_table('uploaded_files')

    op.drop_index('idx_case_messages_role', table_name='case_messages')
    op.drop_index('idx_case_messages_timestamp', table_name='case_messages')
    op.drop_index('idx_case_messages_case_id', table_name='case_messages')
    op.drop_table('case_messages')

    op.drop_index('idx_solutions_risk_level', table_name='solutions')
    op.drop_index('idx_solutions_proposed_at', table_name='solutions')
    op.drop_index('idx_solutions_status', table_name='solutions')
    op.drop_index('idx_solutions_case_id', table_name='solutions')
    op.drop_table('solutions')

    op.drop_index('idx_hypotheses_confidence_score', table_name='hypotheses')
    op.drop_index('idx_hypotheses_proposed_at', table_name='hypotheses')
    op.drop_index('idx_hypotheses_status', table_name='hypotheses')
    op.drop_index('idx_hypotheses_case_id', table_name='hypotheses')
    op.drop_table('hypotheses')

    op.drop_index('idx_evidence_metadata_gin', table_name='evidence')
    op.drop_index('idx_evidence_upload_timestamp', table_name='evidence')
    op.drop_index('idx_evidence_category', table_name='evidence')
    op.drop_index('idx_evidence_case_id', table_name='evidence')
    op.drop_table('evidence')

    op.drop_index('idx_cases_metadata_gin', table_name='cases')
    op.drop_index('idx_cases_problem_verification_gin', table_name='cases')
    op.drop_index('idx_cases_consulting_gin', table_name='cases')
    op.drop_index('idx_cases_updated_at', table_name='cases')
    op.drop_index('idx_cases_created_at', table_name='cases')
    op.drop_index('idx_cases_status', table_name='cases')
    op.drop_index('idx_cases_organization_id', table_name='cases')
    op.drop_index('idx_cases_user_id', table_name='cases')
    op.drop_table('cases')

    # Drop enum types
    sa.Enum(name='file_processing_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='message_role').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='solution_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='hypothesis_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='evidence_category').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='case_status').drop(op.get_bind(), checkfirst=True)

    # Recreate old single-table schema
    op.create_table(
        'cases',
        sa.Column('case_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'RESOLVED', 'ARCHIVED', name='casestatus'), nullable=False),
        sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='caseseverity'), nullable=False),
        sa.Column('category', sa.Enum('INCIDENT', 'CHANGE', 'PROBLEM', 'SERVICE_REQUEST', 'OTHER', name='casecategory'), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('case_id')
    )

    op.create_index(op.f('ix_cases_case_id'), 'cases', ['case_id'], unique=False)
    op.create_index(op.f('ix_cases_user_id'), 'cases', ['user_id'], unique=False)
    op.create_index(op.f('ix_cases_session_id'), 'cases', ['session_id'], unique=False)
    op.create_index(op.f('ix_cases_status'), 'cases', ['status'], unique=False)
    op.create_index(op.f('ix_cases_created_at'), 'cases', ['created_at'], unique=False)
