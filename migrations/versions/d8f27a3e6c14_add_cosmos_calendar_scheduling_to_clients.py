"""add cosmos calendar scheduling fields to clients (FASE 3.2A)

Revision ID: d8f27a3e6c14
Revises: a4e6c19d5b73
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f27a3e6c14'
down_revision: Union[str, Sequence[str], None] = 'a4e6c19d5b73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('clients', sa.Column('cosmos_calendar_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('clients', sa.Column('cosmos_calendar_frequency', sa.String(length=20), nullable=True))
    op.add_column('clients', sa.Column('cosmos_calendar_next_run_at', sa.DateTime(), nullable=True))
    op.add_column('clients', sa.Column('cosmos_calendar_last_run_at', sa.DateTime(), nullable=True))
    op.add_column('clients', sa.Column('cosmos_calendar_last_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clients', 'cosmos_calendar_last_error')
    op.drop_column('clients', 'cosmos_calendar_last_run_at')
    op.drop_column('clients', 'cosmos_calendar_next_run_at')
    op.drop_column('clients', 'cosmos_calendar_frequency')
    op.drop_column('clients', 'cosmos_calendar_enabled')
