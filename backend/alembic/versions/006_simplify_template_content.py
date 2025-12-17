"""Simplify template to single content field (remove gender variants)

Revision ID: 006
Revises: 005
Create Date: 2025-12-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new single content column
    op.add_column("templates", sa.Column("content", sa.Text(), nullable=True))

    # Copy content_male to content (as the default)
    op.execute("UPDATE templates SET content = content_male")

    # Make content not nullable
    op.alter_column("templates", "content", nullable=False)

    # Drop the old gender-specific columns
    op.drop_column("templates", "content_male")
    op.drop_column("templates", "content_female")
    op.drop_column("templates", "content_neutral")


def downgrade() -> None:
    # Add back the gender-specific columns
    op.add_column("templates", sa.Column("content_male", sa.Text(), nullable=True))
    op.add_column("templates", sa.Column("content_female", sa.Text(), nullable=True))
    op.add_column("templates", sa.Column("content_neutral", sa.Text(), nullable=True))

    # Copy content to all gender columns
    op.execute("UPDATE templates SET content_male = content, content_female = content, content_neutral = content")

    # Make them not nullable
    op.alter_column("templates", "content_male", nullable=False)
    op.alter_column("templates", "content_female", nullable=False)
    op.alter_column("templates", "content_neutral", nullable=False)

    # Drop the simplified content column
    op.drop_column("templates", "content")
