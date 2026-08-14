"""add marketing pipeline scheduling fields to clients

Revision ID: 4ca939ab2888
Revises: e34c55db63cd
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ca939ab2888'
down_revision: Union[str, Sequence[str], None] = 'e34c55db63cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('clients', sa.Column('marketing_pipeline_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('clients', sa.Column('marketing_pipeline_frequency', sa.String(length=20), nullable=True))
    op.add_column('clients', sa.Column('marketing_pipeline_next_run_at', sa.DateTime(), nullable=True))
    op.add_column('clients', sa.Column('marketing_pipeline_last_run_at', sa.DateTime(), nullable=True))
    op.add_column('clients', sa.Column('marketing_pipeline_last_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clients', 'marketing_pipeline_last_error')
    op.drop_column('clients', 'marketing_pipeline_last_run_at')
    op.drop_column('clients', 'marketing_pipeline_next_run_at')
    op.drop_column('clients', 'marketing_pipeline_frequency')
    op.drop_column('clients', 'marketing_pipeline_enabled')
