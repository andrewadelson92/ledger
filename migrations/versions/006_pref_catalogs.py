"""per-user diary emotions + backfill catalog defaults

Revision ID: 006_pref_catalogs
Revises: 005_feelings_wheel_pref
Create Date: 2026-09-15

"""
import json
from alembic import op
import sqlalchemy as sa


revision = "006_pref_catalogs"
down_revision = "005_feelings_wheel_pref"
branch_labels = None
depends_on = None

DEFAULT_DIARY_EMOTIONS = [
    "Anxious",
    "Sad",
    "Overwhelmed",
    "Content",
    "Energized",
    "Numb",
]


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_preferences")}

    if "diary_emotions" not in cols:
        with op.batch_alter_table("user_preferences") as batch_op:
            batch_op.add_column(
                sa.Column("diary_emotions", sa.JSON(), nullable=True)
            )

    # Backfill tracked moods for existing users (were previously app-wide constants).
    # Leave target_behaviors alone so browsers can still import localStorage catalogs.
    rows = bind.execute(sa.text("SELECT id, diary_emotions FROM user_preferences")).fetchall()
    for row in rows:
        pref_id, diary_raw = row[0], row[1]
        diary = _as_list(diary_raw)
        if diary:
            continue
        bind.execute(
            sa.text(
                "UPDATE user_preferences SET diary_emotions = :diary WHERE id = :id"
            ),
            {"diary": json.dumps(list(DEFAULT_DIARY_EMOTIONS)), "id": pref_id},
        )

    insp = sa.inspect(bind)
    col = next(
        (c for c in insp.get_columns("user_preferences") if c["name"] == "diary_emotions"),
        None,
    )
    if col and col.get("nullable", True):
        with op.batch_alter_table("user_preferences") as batch_op:
            batch_op.alter_column(
                "diary_emotions",
                existing_type=sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )


def _as_list(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    return []


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("user_preferences")}
    if "diary_emotions" in cols:
        with op.batch_alter_table("user_preferences") as batch_op:
            batch_op.drop_column("diary_emotions")
