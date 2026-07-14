"""add duration_ms to usage_log (Modo Produccion — auditoria de costos)

Revision ID: e1a9c4f7b2d6
Revises: d8f27a3e6c14
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1a9c4f7b2d6'
down_revision: Union[str, Sequence[str], None] = 'd8f27a3e6c14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('usage_log', sa.Column('duration_ms', sa.Numeric(10, 2), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('usage_log', 'duration_ms')
