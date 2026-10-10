"""entry mark_for_review + pegasus_status

Revision ID: 008_pegasus
Revises: 007_audio_clips
Create Date: 2026-10-10

"""
from alembic import op
import sqlalchemy as sa


revision = "008_pegasus"
down_revision = "007_audio_clips"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("entries")}
    with op.batch_alter_table("entries") as batch:
        if "mark_for_review" not in cols:
            batch.add_column(
                sa.Column("mark_for_review", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        if "pegasus_status" not in cols:
            batch.add_column(sa.Column("pegasus_status", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("entries") as batch:
        batch.drop_column("pegasus_status")
        batch.drop_column("mark_for_review")
