"""add_done_rejected_status

Revision ID: 525b7d97c372
Revises: 3b37604d5ac0
Create Date: 2026-01-03 20:35:01.439935

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '525b7d97c372'
down_revision: Union[str, None] = '3b37604d5ac0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to the jobstatus enum
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'done'")
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the type, which is complex
    pass
