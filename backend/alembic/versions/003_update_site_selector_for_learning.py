"""Update site_selectors table for pattern learning

Revision ID: 003
Revises: 002
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type for site_type
    site_type_enum = sa.Enum('company', 'platform', name='sitetype')
    site_type_enum.create(op.get_bind(), checkfirst=True)

    # Add new columns to site_selectors table
    op.add_column(
        'site_selectors',
        sa.Column(
            'site_type',
            sa.Enum('company', 'platform', name='sitetype'),
            nullable=False,
            server_default='company'
        )
    )
    op.add_column(
        'site_selectors',
        sa.Column('company_name', sa.String(255), nullable=True)
    )
    op.add_column(
        'site_selectors',
        sa.Column('platform_name', sa.String(255), nullable=True)
    )
    op.add_column(
        'site_selectors',
        sa.Column('url_pattern', sa.Text(), nullable=True)
    )

    # Make company_selector nullable (it was required before)
    op.alter_column(
        'site_selectors',
        'company_selector',
        existing_type=sa.Text(),
        nullable=True
    )


def downgrade() -> None:
    # Remove new columns
    op.drop_column('site_selectors', 'url_pattern')
    op.drop_column('site_selectors', 'platform_name')
    op.drop_column('site_selectors', 'company_name')
    op.drop_column('site_selectors', 'site_type')

    # Drop enum type
    site_type_enum = sa.Enum('company', 'platform', name='sitetype')
    site_type_enum.drop(op.get_bind(), checkfirst=True)

    # Make company_selector required again
    op.alter_column(
        'site_selectors',
        'company_selector',
        existing_type=sa.Text(),
        nullable=False
    )
