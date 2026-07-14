"""add structured_content to library_assets (FASE 3.1 — Calendario Editorial)

Revision ID: a4e6c19d5b73
Revises: f3a8b1c92d40
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a4e6c19d5b73'
down_revision: Union[str, Sequence[str], None] = 'f3a8b1c92d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('library_assets', sa.Column('structured_content', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('library_assets', 'structured_content')
