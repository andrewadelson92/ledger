from datetime import datetime

from db import db
from constants import DEFAULT_CATEGORY


class Entry(db.Model):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    category = db.Column(db.String, default=DEFAULT_CATEGORY, nullable=False)
    secondary_tag = db.Column(db.String, nullable=True)
    payload = db.Column(db.JSON, nullable=False)
    linked_entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=True)

    linked_entry = db.relationship(
        "Entry",
        remote_side=[id],
        foreign_keys=[linked_entry_id],
        backref=db.backref("linked_checkins", lazy="dynamic"),
    )
