"""Authentication and per-user query scoping (mirrors Long Track)."""
from __future__ import annotations

from flask import abort
from flask_login import LoginManager, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from models import Entry, User, UserPreference

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Sign in to continue."

PUBLIC_ENDPOINTS = frozenset(
    {
        "health",
        "login",
        "setup_password",
        "web_manifest",
        "static",
    }
)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def uid() -> int:
    return current_user.id


def entries_q():
    return Entry.query.filter_by(user_id=uid())


def get_entry(entry_id: int) -> Entry:
    entry = Entry.query.filter_by(id=entry_id, user_id=uid()).first()
    if entry is None:
        abort(404)
    return entry


def set_password(user: User, password: str) -> None:
    user.password_hash = generate_password_hash(password)


def check_password(user: User, password: str) -> bool:
    if not user.password_hash:
        return False
    return check_password_hash(user.password_hash, password)


def get_or_create_preferences(user_id: int | None = None) -> UserPreference:
    user_id = user_id if user_id is not None else uid()
    prefs = UserPreference.query.filter_by(user_id=user_id).first()
    if prefs is None:
        prefs = UserPreference(
            user_id=user_id,
            saved_emotions=[],
            saved_skills=[],
            target_behaviors=[],
        )
        db.session.add(prefs)
        db.session.commit()
    return prefs
