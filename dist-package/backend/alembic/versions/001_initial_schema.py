"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Jobs table
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('job_title', sa.String(255), nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='jobstatus'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Contacts table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('linkedin_url', sa.Text(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('position', sa.String(255), nullable=True),
        sa.Column('gender', sa.Enum('male', 'female', 'unknown', name='gender'), nullable=False),
        sa.Column('is_connection', sa.Boolean(), nullable=False),
        sa.Column('connection_requested_at', sa.DateTime(), nullable=True),
        sa.Column('message_sent_at', sa.DateTime(), nullable=True),
        sa.Column('message_content', sa.Text(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('linkedin_url')
    )

    # Activity logs table
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('action_type', sa.Enum(
            'job_submitted', 'company_extracted', 'selector_learned',
            'connection_search', 'connection_found', 'connection_request_sent',
            'message_sent', 'linkedin_search', 'error',
            name='actiontype'
        ), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Templates table
    op.create_table(
        'templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('content_male', sa.Text(), nullable=False),
        sa.Column('content_female', sa.Text(), nullable=False),
        sa.Column('content_neutral', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Site selectors table
    op.create_table(
        'site_selectors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('company_selector', sa.Text(), nullable=False),
        sa.Column('title_selector', sa.Text(), nullable=True),
        sa.Column('example_url', sa.Text(), nullable=True),
        sa.Column('example_company', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('domain')
    )

    # Create indexes
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_company_name', 'jobs', ['company_name'])
    op.create_index('ix_contacts_company', 'contacts', ['company'])
    op.create_index('ix_activity_logs_action_type', 'activity_logs', ['action_type'])
    op.create_index('ix_activity_logs_job_id', 'activity_logs', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_activity_logs_job_id')
    op.drop_index('ix_activity_logs_action_type')
    op.drop_index('ix_contacts_company')
    op.drop_index('ix_jobs_company_name')
    op.drop_index('ix_jobs_status')

    op.drop_table('site_selectors')
    op.drop_table('templates')
    op.drop_table('activity_logs')
    op.drop_table('contacts')
    op.drop_table('jobs')

    op.execute('DROP TYPE IF EXISTS actiontype')
    op.execute('DROP TYPE IF EXISTS gender')
    op.execute('DROP TYPE IF EXISTS jobstatus')
