"""add_waiting_workflow_steps_and_reply_tracking

Revision ID: 030ab2c99efc
Revises: cfec6fe591d0
Create Date: 2025-12-18 12:24:17.547684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '030ab2c99efc'
down_revision: Union[str, None] = 'cfec6fe591d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add reply tracking field to contacts
    op.add_column('contacts', sa.Column('reply_received_at', sa.DateTime(), nullable=True))

    # Add new workflow step values to the enum
    # Note: PostgreSQL enums can be extended with ALTER TYPE
    op.execute("ALTER TYPE workflowstep ADD VALUE IF NOT EXISTS 'waiting_for_reply'")
    op.execute("ALTER TYPE workflowstep ADD VALUE IF NOT EXISTS 'waiting_for_accept'")


def downgrade() -> None:
    op.drop_column('contacts', 'reply_received_at')
    # Note: PostgreSQL doesn't support removing values from enums easily
    # The enum values will remain but won't be used
