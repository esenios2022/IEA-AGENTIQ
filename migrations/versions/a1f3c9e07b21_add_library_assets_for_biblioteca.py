"""add library_assets for biblioteca inteligente de marketing (FASE 2.3)

Revision ID: a1f3c9e07b21
Revises: bd6ae2f9e149
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1f3c9e07b21'
down_revision: Union[str, Sequence[str], None] = 'bd6ae2f9e149'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'library_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('category', sa.String(length=120), nullable=False),
        sa.Column('subcategory', sa.String(length=255), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_type', sa.String(length=30), nullable=False),
        sa.Column('mime_type', sa.String(length=120), nullable=True),
        sa.Column('file_extension', sa.String(length=20), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='es'),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('created_by_agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='borrador'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['created_by_agent_id'], ['agents.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_library_assets_client_id', 'library_assets', ['client_id'])
    op.create_index('ix_library_assets_category', 'library_assets', ['category'])
    op.create_index('ix_library_assets_subcategory', 'library_assets', ['subcategory'])
    op.create_index('ix_library_assets_status', 'library_assets', ['status'])
    op.create_index('ix_library_assets_client_category_status', 'library_assets', ['client_id', 'category', 'status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_library_assets_client_category_status', table_name='library_assets')
    op.drop_index('ix_library_assets_status', table_name='library_assets')
    op.drop_index('ix_library_assets_subcategory', table_name='library_assets')
    op.drop_index('ix_library_assets_category', table_name='library_assets')
    op.drop_index('ix_library_assets_client_id', table_name='library_assets')
    op.drop_table('library_assets')
