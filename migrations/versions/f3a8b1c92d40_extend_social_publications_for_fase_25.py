"""extend social_publications for FASE 2.5 (real publish wiring)

Revision ID: f3a8b1c92d40
Revises: c7d2e4f81a90
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3a8b1c92d40'
down_revision: Union[str, Sequence[str], None] = 'c7d2e4f81a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('social_publications', sa.Column('is_test', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('social_publications', sa.Column('published_at', sa.DateTime(), nullable=True))
    op.add_column('social_publications', sa.Column('publish_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('social_publications', sa.Column('publish_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('social_publications', 'publish_error')
    op.drop_column('social_publications', 'publish_response')
    op.drop_column('social_publications', 'published_at')
    op.drop_column('social_publications', 'is_test')
