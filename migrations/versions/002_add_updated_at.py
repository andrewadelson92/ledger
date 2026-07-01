"""add updated_at to entries

Revision ID: 002_updated_at
Revises: 001_initial
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa


revision = "002_updated_at"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE entries SET updated_at = created_at WHERE updated_at IS NULL")

    with op.batch_alter_table("entries", schema=None) as batch_op:
        batch_op.alter_column("updated_at", nullable=False)


def downgrade():
    with op.batch_alter_table("entries", schema=None) as batch_op:
        batch_op.drop_column("updated_at")
