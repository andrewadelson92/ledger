#!/usr/bin/env python3
"""
Local demo user helpers for blank-slate walkthroughs.

Uses the separate demo DB only (instance/demo_ledger.db) — never your
personal ledger.db.

Usage (from project root):

  .venv/bin/python scripts/demo_user.py reset
  .venv/bin/python scripts/demo_user.py ensure
  .venv/bin/python scripts/demo_user.py status

Then start the app:

  .venv/bin/python app.py demo
  # or after reset:
  .venv/bin/python app.py demo clear

Sign in as demo@localhost / demopass123
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_VENV_HINT = (
    "Missing app dependencies (e.g. flask_login). "
    "Use the project venv:\n"
    "  .venv/bin/python scripts/demo_user.py reset"
)

DEMO_DB = os.path.join(ROOT, "instance", "demo_ledger.db")
DEMO_EMAIL = "demo@localhost"
DEMO_PASSWORD = "demopass123"


def _point_at_demo_db(*, clear: bool = False) -> None:
    os.makedirs(os.path.join(ROOT, "instance"), exist_ok=True)
    if clear:
        try:
            os.remove(DEMO_DB)
            print(f"Removed {DEMO_DB}")
        except FileNotFoundError:
            print("No existing demo DB to remove.")
    os.environ["LEDGER_DB_PATH"] = DEMO_DB
    sys.argv = [sys.argv[0]]


def _load_app():
    try:
        from app import app, db  # noqa: WPS433
    except ModuleNotFoundError as exc:
        raise SystemExit(f"{exc}\n\n{_VENV_HINT}") from None
    return app, db


def cmd_ensure() -> None:
    try:
        from app import DEMO_USER_EMAIL, DEMO_USER_PASSWORD, _ensure_demo_blank_user
        from models import Entry, User
    except ModuleNotFoundError as exc:
        raise SystemExit(f"{exc}\n\n{_VENV_HINT}") from None

    app, db = _load_app()
    with app.app_context():
        user = _ensure_demo_blank_user()
        n_entries = Entry.query.filter_by(user_id=user.id).count()
        print(f"Demo DB: {DEMO_DB}")
        print(f"User:    {DEMO_USER_EMAIL} (id={user.id})")
        print(f"Password:{DEMO_USER_PASSWORD}")
        print(f"Entries: {n_entries}")
        if n_entries:
            print("Note: demo DB still has data. Run `reset` for a true blank slate.")


def cmd_reset() -> None:
    _point_at_demo_db(clear=True)
    if "app" in sys.modules:
        del sys.modules["app"]
    cmd_ensure()
    print("Blank slate ready. Start with: python app.py demo")


def cmd_status() -> None:
    _point_at_demo_db(clear=False)
    if "app" in sys.modules:
        del sys.modules["app"]
    from models import Entry, User

    app, db = _load_app()
    with app.app_context():
        print(f"Demo DB: {DEMO_DB}")
        print(f"Exists:  {os.path.exists(DEMO_DB)}")
        users = User.query.order_by(User.id.asc()).all()
        if not users:
            print("No users yet. Run: python scripts/demo_user.py reset")
            return
        for u in users:
            n = Entry.query.filter_by(user_id=u.id).count()
            tag = " ← demo login" if u.email == DEMO_EMAIL else ""
            print(f"- {u.email} id={u.id} entries={n}{tag}")


def main() -> None:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if cmd not in ("reset", "ensure", "status"):
        print(__doc__.strip())
        sys.exit(2)

    if cmd == "reset":
        cmd_reset()
        return

    _point_at_demo_db(clear=False)
    if "app" in sys.modules:
        del sys.modules["app"]
    if cmd == "ensure":
        cmd_ensure()
    else:
        cmd_status()


if __name__ == "__main__":
    main()
