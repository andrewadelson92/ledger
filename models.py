from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from db import db
from constants import DEFAULT_CATEGORY


class User(UserMixin, db.Model):
    """Account identity. Same email as Long Track is the future cross-app link key."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def needs_password_setup(self) -> bool:
        return not self.password_hash


class UserPreference(db.Model):
    """Per-user picker catalogs (emotions, skills, target behaviors) — server-backed."""

    __tablename__ = "user_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    saved_emotions = db.Column(db.JSON, nullable=False, default=list)
    saved_skills = db.Column(db.JSON, nullable=False, default=list)
    target_behaviors = db.Column(db.JSON, nullable=False, default=list)
    show_feelings_wheel = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = db.relationship("User", lazy=True)


class Invite(db.Model):
    """Email invite token — invitee sets their own password via /register/<token>."""

    __tablename__ = "invites"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship("User", lazy=True)


class Entry(db.Model):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    category = db.Column(db.String, default=DEFAULT_CATEGORY, nullable=False)
    secondary_tag = db.Column(db.String, nullable=True)
    payload = db.Column(db.JSON, nullable=False)
    linked_entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=True)

    user = db.relationship("User", lazy=True)
    linked_entry = db.relationship(
        "Entry",
        remote_side=[id],
        foreign_keys=[linked_entry_id],
        backref=db.backref("linked_checkins", lazy="dynamic"),
    )
