"""Add needs_input status and company_input_needed action type

Revision ID: 002
Revises: 001
Create Date: 2024-01-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new value to jobstatus enum
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'needs_input'")

    # Add new value to actiontype enum
    op.execute("ALTER TYPE actiontype ADD VALUE IF NOT EXISTS 'company_input_needed'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing values from enums easily
    # To properly downgrade, you'd need to:
    # 1. Create new enum without the value
    # 2. Update columns to use new enum
    # 3. Drop old enum
    # 4. Rename new enum
    # For simplicity, we'll leave this as a no-op warning
    pass
