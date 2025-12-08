"""Initial schema for cases table

Revision ID: 001_initial
Revises:
Create Date: 2025-01-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create cases table with all columns from CaseDB model."""
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

    # Create indexes for performance
    op.create_index(op.f('ix_cases_case_id'), 'cases', ['case_id'], unique=False)
    op.create_index(op.f('ix_cases_user_id'), 'cases', ['user_id'], unique=False)
    op.create_index(op.f('ix_cases_session_id'), 'cases', ['session_id'], unique=False)
    op.create_index(op.f('ix_cases_status'), 'cases', ['status'], unique=False)
    op.create_index(op.f('ix_cases_created_at'), 'cases', ['created_at'], unique=False)


def downgrade() -> None:
    """Drop cases table and all indexes."""
    op.drop_index(op.f('ix_cases_created_at'), table_name='cases')
    op.drop_index(op.f('ix_cases_status'), table_name='cases')
    op.drop_index(op.f('ix_cases_session_id'), table_name='cases')
    op.drop_index(op.f('ix_cases_user_id'), table_name='cases')
    op.drop_index(op.f('ix_cases_case_id'), table_name='cases')
    op.drop_table('cases')

    # Drop enum types (PostgreSQL only)
    # SQLite will ignore these
    sa.Enum(name='casestatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='caseseverity').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='casecategory').drop(op.get_bind(), checkfirst=True)
