"""extend leads and add lead_interactions for FASE 2.2 lead automation

Revision ID: bd6ae2f9e149
Revises: 3094867bd266
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'bd6ae2f9e149'
down_revision: Union[str, Sequence[str], None] = '3094867bd266'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('leads', sa.Column('telefono', sa.String(length=50), nullable=True))
    op.add_column('leads', sa.Column('ciudad', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('pais', sa.String(length=100), nullable=True))
    op.add_column('leads', sa.Column('plan_interes', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('fuente', sa.String(length=100), nullable=False, server_default='landing_web'))
    op.add_column('leads', sa.Column('estado', sa.String(length=50), nullable=False, server_default='prospecto'))
    op.add_column('leads', sa.Column('notas', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('tenant', sa.String(length=100), nullable=False, server_default='ealumina'))
    op.add_column('leads', sa.Column('idioma', sa.String(length=10), nullable=False, server_default='es'))
    op.add_column('leads', sa.Column('tipo_terapia', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('disponibilidad', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('clasificacion_ia', sa.Text(), nullable=True))

    op.create_table(
        'lead_interactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('lead_interactions')
    op.drop_column('leads', 'clasificacion_ia')
    op.drop_column('leads', 'disponibilidad')
    op.drop_column('leads', 'tipo_terapia')
    op.drop_column('leads', 'idioma')
    op.drop_column('leads', 'tenant')
    op.drop_column('leads', 'notas')
    op.drop_column('leads', 'estado')
    op.drop_column('leads', 'fuente')
    op.drop_column('leads', 'plan_interes')
    op.drop_column('leads', 'pais')
    op.drop_column('leads', 'ciudad')
    op.drop_column('leads', 'telefono')
