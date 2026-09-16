"""add show_feelings_wheel preference

Revision ID: 005_feelings_wheel_pref
Revises: 004_auth_invites
Create Date: 2026-09-15

"""
from alembic import op
import sqlalchemy as sa


revision = "005_feelings_wheel_pref"
down_revision = "004_auth_invites"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_preferences")}
    if "show_feelings_wheel" not in cols:
        with op.batch_alter_table("user_preferences") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "show_feelings_wheel",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                )
            )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_preferences")}
    if "show_feelings_wheel" in cols:
        with op.batch_alter_table("user_preferences") as batch_op:
            batch_op.drop_column("show_feelings_wheel")
