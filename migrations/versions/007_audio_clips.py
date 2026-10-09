"""audio clips for journal entries

Revision ID: 007_audio_clips
Revises: 006_pref_catalogs
Create Date: 2026-10-09

"""
from alembic import op
import sqlalchemy as sa


revision = "007_audio_clips"
down_revision = "006_pref_catalogs"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "audio_clips" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "audio_clips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("entries.id"), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audio_clips_user_id", "audio_clips", ["user_id"])
    op.create_index("ix_audio_clips_entry_id", "audio_clips", ["entry_id"])


def downgrade():
    bind = op.get_bind()
    if "audio_clips" not in sa.inspect(bind).get_table_names():
        return
    op.drop_index("ix_audio_clips_entry_id", table_name="audio_clips")
    op.drop_index("ix_audio_clips_user_id", table_name="audio_clips")
    op.drop_table("audio_clips")
