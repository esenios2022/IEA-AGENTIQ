"""add instagram_webhook_events

Revision ID: e34c55db63cd
Revises: b7f4c1e83a92
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e34c55db63cd"
down_revision = "b7f4c1e83a92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comment_id", sa.String(length=64), nullable=False),
        sa.Column("media_id", sa.String(length=64), nullable=True),
        sa.Column("commenter_username", sa.String(length=255), nullable=True),
        sa.Column("matched_keyword", sa.Boolean(), nullable=False),
        sa.Column("public_reply_sent", sa.Boolean(), nullable=False),
        sa.Column("dm_sent", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_instagram_webhook_events_comment_id",
        "instagram_webhook_events",
        ["comment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_instagram_webhook_events_comment_id", table_name="instagram_webhook_events")
    op.drop_table("instagram_webhook_events")
