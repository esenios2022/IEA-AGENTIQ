"""add provider and publication/campaign fields to usage_log (drift fix)

Estas 4 columnas (provider, content_asset_id, publication_id, campaign_id)
existian en src/models.py::UsageLog desde 2026-07-14 pero nunca tuvieron
una migracion real -- confirmado real: produccion (base limpia via
`alembic upgrade head`) tiraba `UndefinedColumn: usage_log.provider does
not exist` en /api/me/executions, mientras que el entorno de desarrollo
local nunca lo noto porque ya tenia estas columnas (agregadas por fuera
del sistema de migraciones en algun momento). Esta migracion cierra ese
drift.

Revision ID: b7f4c1e83a92
Revises: e1a9c4f7b2d6
Create Date: 2026-07-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7f4c1e83a92'
down_revision: Union[str, Sequence[str], None] = 'e1a9c4f7b2d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('usage_log', sa.Column('provider', sa.String(length=20), nullable=False, server_default='claude'))
    op.add_column('usage_log', sa.Column('content_asset_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('usage_log', sa.Column('publication_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('usage_log', sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('usage_log', 'campaign_id')
    op.drop_column('usage_log', 'publication_id')
    op.drop_column('usage_log', 'content_asset_id')
    op.drop_column('usage_log', 'provider')
