"""add users, entries.user_id ownership, user_preferences

Revision ID: 003_add_users
Revises: 002_updated_at
Create Date: 2026-09-15

"""
import os
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "003_add_users"
down_revision = "002_updated_at"
branch_labels = None
depends_on = None

DEFAULT_OWNER_EMAIL = "andrew.adelson92@gmail.com"


def _is_production_env() -> bool:
    env = (
        os.environ.get("LEDGER_ENV")
        or os.environ.get("FLASK_ENV")
        or "development"
    ).strip().lower()
    return env in ("production", "prod")


def _owner_email() -> str:
    email = (os.environ.get("LEDGER_OWNER_EMAIL") or "").strip().lower()
    if email:
        return email
    if _is_production_env():
        raise RuntimeError(
            "LEDGER_OWNER_EMAIL must be set on the web service before "
            "deploying migration 003_add_users in production."
        )
    return DEFAULT_OWNER_EMAIL


def upgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    insp = sa.inspect(bind)

    if not insp.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )

    if not insp.has_table("user_preferences"):
        op.create_table(
            "user_preferences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("saved_emotions", sa.JSON(), nullable=False),
            sa.Column("saved_skills", sa.JSON(), nullable=False),
            sa.Column("target_behaviors", sa.JSON(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=True)

    user_count = bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar()
    if not user_count:
        now = datetime.utcnow()
        bind.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, is_active, created_at) "
                "VALUES (1, :email, NULL, :active, :created_at)"
            ),
            {"email": _owner_email(), "active": True, "created_at": now},
        )

    entry_cols = {c["name"] for c in insp.get_columns("entries")}
    if "user_id" not in entry_cols:
        with op.batch_alter_table("entries") as batch_op:
            batch_op.add_column(
                sa.Column("user_id", sa.Integer(), nullable=True, server_default="1")
            )

    op.execute("UPDATE entries SET user_id = 1 WHERE user_id IS NULL")

    # Re-inspect after column add
    insp = sa.inspect(bind)
    entry_cols = {c["name"]: c for c in insp.get_columns("entries")}
    col = entry_cols.get("user_id")
    if col and col.get("nullable", True):
        with op.batch_alter_table("entries") as batch_op:
            batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

    if not is_sqlite:
        fks = {fk["name"] for fk in insp.get_foreign_keys("entries")}
        if "fk_entries_user_id" not in fks:
            op.create_foreign_key(
                "fk_entries_user_id",
                "entries",
                "users",
                ["user_id"],
                ["id"],
            )
        op.execute("ALTER TABLE entries ALTER COLUMN user_id DROP DEFAULT")

    existing_indexes = {idx["name"] for idx in insp.get_indexes("entries")}
    if "ix_entries_user_id" not in existing_indexes:
        op.create_index("ix_entries_user_id", "entries", ["user_id"])


def downgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    op.drop_index("ix_entries_user_id", table_name="entries")
    if not is_sqlite:
        op.drop_constraint("fk_entries_user_id", "entries", type_="foreignkey")

    with op.batch_alter_table("entries") as batch_op:
        batch_op.drop_column("user_id")

    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
    op.drop_table("users")
