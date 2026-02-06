"""Add hebrew_names table and needs_hebrew_names workflow step

Revision ID: 005
Revises: 004
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create hebrew_names table
    op.create_table(
        'hebrew_names',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('english_name', sa.String(length=100), nullable=False),
        sa.Column('hebrew_name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_hebrew_names_english_name', 'hebrew_names', ['english_name'], unique=True)

    # Add 'needs_hebrew_names' to workflowstep enum
    # PostgreSQL requires ALTER TYPE
    op.execute("ALTER TYPE workflowstep ADD VALUE IF NOT EXISTS 'needs_hebrew_names' AFTER 'search_connections'")

    # Add pending_hebrew_names column to jobs table for storing names awaiting translation
    op.add_column('jobs', sa.Column('pending_hebrew_names', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Drop pending_hebrew_names column from jobs
    op.drop_column('jobs', 'pending_hebrew_names')

    # Drop hebrew_names table
    op.drop_index('ix_hebrew_names_english_name', table_name='hebrew_names')
    op.drop_table('hebrew_names')

    # Note: PostgreSQL doesn't support removing values from enums easily
    # The 'needs_hebrew_names' value will remain in the enum after downgrade
