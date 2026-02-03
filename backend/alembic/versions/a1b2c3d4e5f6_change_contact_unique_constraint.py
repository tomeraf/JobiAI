"""change_contact_unique_constraint

Revision ID: a1b2c3d4e5f6
Revises: 525b7d97c372
Create Date: 2026-02-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '525b7d97c372'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old unique constraint on linkedin_url only
    op.drop_constraint('contacts_linkedin_url_key', 'contacts', type_='unique')

    # Add new unique constraint on (linkedin_url, job_id) combination
    # This allows the same person to be contacted for multiple jobs
    op.create_unique_constraint(
        'uq_contact_linkedin_url_job_id',
        'contacts',
        ['linkedin_url', 'job_id']
    )


def downgrade() -> None:
    # Drop the composite unique constraint
    op.drop_constraint('uq_contact_linkedin_url_job_id', 'contacts', type_='unique')

    # Restore the original unique constraint on linkedin_url only
    # Note: This may fail if there are duplicate linkedin_urls
    op.create_unique_constraint('contacts_linkedin_url_key', 'contacts', ['linkedin_url'])
