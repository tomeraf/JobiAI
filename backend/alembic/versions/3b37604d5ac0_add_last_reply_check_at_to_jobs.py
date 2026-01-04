"""add_last_reply_check_at_to_jobs

Revision ID: 3b37604d5ac0
Revises: 5e3e6d799c7d
Create Date: 2025-12-26 14:18:38.852534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b37604d5ac0'
down_revision: Union[str, None] = '5e3e6d799c7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('last_reply_check_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'last_reply_check_at')
