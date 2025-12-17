"""Add workflow_step column to jobs table

Revision ID: 004
Revises: 003
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type for workflow_step
    workflow_step_enum = sa.Enum(
        'company_extraction',
        'search_connections',
        'message_connections',
        'search_linkedin',
        'send_requests',
        'done',
        name='workflowstep'
    )
    workflow_step_enum.create(op.get_bind(), checkfirst=True)

    # Add workflow_step column to jobs table
    op.add_column(
        'jobs',
        sa.Column(
            'workflow_step',
            sa.Enum(
                'company_extraction',
                'search_connections',
                'message_connections',
                'search_linkedin',
                'send_requests',
                'done',
                name='workflowstep'
            ),
            nullable=False,
            server_default='company_extraction'
        )
    )


def downgrade() -> None:
    # Remove workflow_step column
    op.drop_column('jobs', 'workflow_step')

    # Drop enum type
    workflow_step_enum = sa.Enum(
        'company_extraction',
        'search_connections',
        'message_connections',
        'search_linkedin',
        'send_requests',
        'done',
        name='workflowstep'
    )
    workflow_step_enum.drop(op.get_bind(), checkfirst=True)
