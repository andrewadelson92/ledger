"""Authentication and per-user query scoping (mirrors Long Track)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from flask import abort
from flask_login import LoginManager, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from models import Entry, Invite, User, UserPreference

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Sign in to continue."

PUBLIC_ENDPOINTS = frozenset(
    {
        "health",
        "login",
        "setup_password",
        "register",
        "web_manifest",
        "static",
    }
)

INVITE_TTL_DAYS = 7


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
            show_feelings_wheel=True,
        )
        db.session.add(prefs)
        db.session.commit()
    return prefs


def create_invite(email: str, created_by_user_id: int) -> Invite:
    token = secrets.token_urlsafe(32)
    inv = Invite(
        email=email.strip().lower(),
        token=token,
        created_by_user_id=created_by_user_id,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_TTL_DAYS),
    )
    db.session.add(inv)
    db.session.commit()
    return inv


def validate_invite_token(token: str) -> Invite | None:
    inv = Invite.query.filter_by(token=token).first()
    if not inv or inv.used_at is not None:
        return None
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        return None
    return inv


def cancel_invite(invite_id: int, user_id: int) -> Invite | None:
    inv = Invite.query.filter_by(
        id=invite_id, created_by_user_id=user_id, used_at=None
    ).first()
    if not inv:
        return None
    db.session.delete(inv)
    db.session.commit()
    return inv
