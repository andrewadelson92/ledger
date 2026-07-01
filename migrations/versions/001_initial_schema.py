"""initial entries schema

Revision ID: 001_initial
Revises:
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa


revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("secondary_tag", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("linked_entry_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["linked_entry_id"], ["entries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("entries")
