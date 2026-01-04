"""drop_gender_column_from_contacts

Revision ID: 5e3e6d799c7d
Revises: 030ab2c99efc
Create Date: 2025-12-26 03:22:51.576683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5e3e6d799c7d'
down_revision: Union[str, None] = '030ab2c99efc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the gender column from contacts table
    op.drop_column('contacts', 'gender')
    # Also drop the gender enum type
    op.execute("DROP TYPE IF EXISTS gender")


def downgrade() -> None:
    # Recreate the gender enum type
    gender_enum = postgresql.ENUM('male', 'female', 'unknown', name='gender', create_type=False)
    gender_enum.create(op.get_bind(), checkfirst=True)
    # Add back the gender column
    op.add_column('contacts', sa.Column('gender', postgresql.ENUM('male', 'female', 'unknown', name='gender'), autoincrement=False, nullable=True))
