"""add invites table for invite-only account creation

Revision ID: 004_auth_invites
Revises: 003_add_users
Create Date: 2026-09-15

"""
from alembic import op
import sqlalchemy as sa


revision = "004_auth_invites"
down_revision = "003_add_users"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("invites"):
        op.create_table(
            "invites",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("token", sa.String(length=64), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token"),
        )
        op.create_index("ix_invites_token", "invites", ["token"], unique=True)


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("invites"):
        op.drop_index("ix_invites_token", table_name="invites")
        op.drop_table("invites")
