"""Pegasus endpoint + occurrence checks on a throwaway SQLite DB.

    PEGASUS_TOKEN=t LEDGER_DB_PATH=/tmp/ledger_pegasus_test.db .venv/bin/python scripts/test_pegasus.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PEGASUS_TOKEN", "test-token")
db_path = os.environ.setdefault("LEDGER_DB_PATH", "/tmp/ledger_pegasus_test.db")
if os.path.exists(db_path):
    os.remove(db_path)

from app import app, db  # noqa: E402
from models import Entry, User  # noqa: E402
import pegasus  # noqa: E402

TOKEN = os.environ["PEGASUS_TOKEN"]

with app.app_context():
    me = User(email="me@example.com", is_active=True)
    other = User(email="other@example.com", is_active=True)
    db.session.add_all([me, other])
    db.session.commit()
    now = datetime.utcnow()
    db.session.add_all([
        Entry(user_id=me.id, type="daily_planner", created_at=now - timedelta(days=1), payload={
            "focus": "Be kind",
            "diary_emotions": [{"name": "Content", "intensity": 4}],
            "diary_urges": [{"behavior": "Laying in bed", "intensity": 2}],
        }),
        Entry(user_id=me.id, type="skill_used", created_at=now, payload={"module": "M", "skill": "Observe", "note": ""}),
        Entry(user_id=me.id, type="thought_record", created_at=now, mark_for_review=True, payload={
            "situation": "Meeting", "automatic_thought": "They hate it",
            "emotions": [{"name": "Anxious", "intensity_before": 4}],
            "emotions_after": [{"name": "Anxious", "intensity_after": 2}],
        }),
        Entry(user_id=me.id, type="journal", created_at=now, payload={"text": "Private words"}),
        Entry(user_id=other.id, type="skill_used", created_at=now, payload={"module": "DT", "skill": "STOP"}),
    ])
    db.session.commit()

c = app.test_client()
start = (datetime.utcnow() - timedelta(days=7)).isoformat()
end = (datetime.utcnow() + timedelta(minutes=1)).isoformat()
q = f"/api/pegasus/entries?email=me@example.com&start={start}&end={end}"

r = c.get(q)
assert r.status_code == 401, r.status_code
r = c.get(q, headers={"Authorization": "Bearer wrong"})
assert r.status_code == 401, r.status_code

r = c.get(q, headers={"Authorization": f"Bearer {TOKEN}"})
assert r.status_code == 200, r.status_code
data = r.get_json()
assert data["user_found"] is True
skills = [s["skill"] for d in data["days"].values() for s in d["skills"]]
assert skills == ["Observe"], skills  # other user's STOP never appears
assert any(d["diary"] for d in data["days"].values())
assert data["discuss"][0]["type"] == "thought_record" and data["discuss"][0]["mark_for_review"]
assert data["journal"] == [], "journal excluded by default"

r = c.get(q + "&include_journal=1", headers={"Authorization": f"Bearer {TOKEN}"})
assert r.get_json()["journal"][0]["text"] == "Private words"

r = c.get(q.replace("me@example.com", "nobody@example.com"), headers={"Authorization": f"Bearer {TOKEN}"})
assert r.get_json()["user_found"] is False

with app.app_context():
    me_id = User.query.filter_by(email="me@example.com").one().id
    by_type = {e.type: e for e in Entry.query.filter_by(user_id=me_id).all()}
    assert pegasus.occurrence_for(by_type["daily_planner"])["trigger_type"] == "diary_card"
    occ = pegasus.occurrence_for(by_type["skill_used"])
    assert occ["trigger_type"] == "skill_used" and occ["detail"]["modules"] == ["M"], occ
    assert pegasus.occurrence_for(by_type["journal"]) is None
    checkin = pegasus.occurrence_for(Entry(type="checkin", payload={"emotions": [{"name": "Fear", "intensity": 4}]}))
    assert checkin == {"trigger_type": "checkin", "label": "Emotion check-in", "detail": {}}, checkin

print("ledger pegasus OK")
