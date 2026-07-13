"""add social_publications for publicacion multicanal (FASE 2.4)

Revision ID: c7d2e4f81a90
Revises: a1f3c9e07b21
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c7d2e4f81a90'
down_revision: Union[str, Sequence[str], None] = 'a1f3c9e07b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'social_publications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('library_asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.String(length=30), nullable=False),
        sa.Column('caption', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='borrador'),
        sa.Column('legal_review_text', sa.Text(), nullable=True),
        sa.Column('legal_review_verdict', sa.String(length=20), nullable=True),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('created_by_agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('platform_post_id', sa.String(length=255), nullable=True),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['library_asset_id'], ['library_assets.id'], ),
        sa.ForeignKeyConstraint(['created_by_agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_social_publications_client_id', 'social_publications', ['client_id'])
    op.create_index('ix_social_publications_platform', 'social_publications', ['platform'])
    op.create_index('ix_social_publications_status', 'social_publications', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_social_publications_status', table_name='social_publications')
    op.drop_index('ix_social_publications_platform', table_name='social_publications')
    op.drop_index('ix_social_publications_client_id', table_name='social_publications')
    op.drop_table('social_publications')
