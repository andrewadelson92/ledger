"""Pegasus bridge: Ledger <-> Long Track.

Ledger reports facts; Long Track owns interpretation (which claims, rules).
Server-to-server only, authenticated by a shared PEGASUS_TOKEN and matched by email.
Unset env vars make every function here a no-op.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from constants import SKILL_MODULE_LABELS, DIARY_CARD_EMOTIONS
from helpers import (
    behavioral_activation_emotion_rows,
    behavioral_activation_is_complete,
    daily_planner_has_diary,
    entry_summary,
    exposure_is_complete,
    opposite_action_emotion_rows,
    opposite_action_is_complete,
    type_label,
)

log = logging.getLogger(__name__)

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
SEND_TIMEOUT_SECONDS = 3

# Ledger entry types Long Track may treat as an act (completion only).
OCCURRENCE_ENTRY_TYPES = frozenset(
    {
        "daily_planner",
        "diary_card",
        "checkin",
        "journal",
        "daily_goal",
        "skill_used",
        "opposite_action",
        "behavioral_activation",
        "exposure_plan",
        "thought_record",
        "abc",
        "chain_analysis",
    }
)

MANTRA_ACTION_LABELS = {
    "invoke": "today's focus",
    "add": "added",
    "edit": "edited",
    "delete": "deleted",
}

DISCUSS_TYPES = (
    "chain_analysis",
    "thought_record",
    "opposite_action",
    "abc",
    "behavioral_activation",
    "exposure_plan",
    "exposure_checkin",
    "checkin",
    "skill_used",
)


def pegasus_token() -> str:
    return (os.getenv("PEGASUS_TOKEN") or "").strip()


def long_track_url() -> str:
    return (os.getenv("LONG_TRACK_URL") or "").strip().rstrip("/")


def token_ok(auth_header: str | None) -> bool:
    expected = pegasus_token()
    if not expected or not auth_header:
        return False
    prefix = "Bearer "
    if not auth_header.startswith(prefix):
        return False
    return hmac.compare_digest(auth_header[len(prefix):].strip(), expected)


def _local_day(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(LOCAL_TZ).date().isoformat()


def _iso_utc(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _emotion_list(items, key: str = "intensity") -> str:
    parts = []
    for e in items or []:
        if not isinstance(e, dict) or not e.get("name"):
            continue
        v = e.get(key, e.get("intensity"))
        parts.append(f"{e['name']} {v}" if v not in (None, "") else e["name"])
    return ", ".join(parts)


def _before_after(rows) -> str:
    parts = []
    for r in rows or []:
        name = r.get("name") or r.get("label")
        before = r.get("before", r.get("current"))
        after = r.get("after", r.get("new"))
        if not name:
            continue
        if after is None:
            parts.append(f"{name} {before}")
        else:
            parts.append(f"{name} {before} → {after}")
    return ", ".join(parts)


def _fields(pairs) -> list[list[str]]:
    return [[label, str(value)] for label, value in pairs if value not in (None, "", [])]


def _discuss_fields(entry) -> list[list[str]]:
    p = entry.payload or {}
    t = entry.type
    if t == "thought_record":
        return _fields([
            ("Situation", p.get("situation")),
            ("Thoughts", p.get("automatic_thought")),
            ("Emotions before", _emotion_list(p.get("emotions"), "intensity_before")),
            ("Validity", p.get("validity")),
            ("Alternative thought", p.get("alternative_thought")),
            ("Emotions after", _emotion_list(p.get("emotions_after"), "intensity_after")),
        ])
    if t == "chain_analysis":
        links = "; ".join(
            (l.get("text") or "").strip()
            for l in (p.get("chain_links") or [])
            if isinstance(l, dict) and (l.get("text") or "").strip()
        )
        return _fields([
            ("Vulnerability", p.get("vulnerability_factors")),
            ("Prompting event", p.get("prompting_event")),
            ("Links", links),
            ("Problem behavior", p.get("problem_behavior")),
            ("Short-term consequences", p.get("consequences_short_term")),
            ("Long-term consequences", p.get("consequences_long_term")),
            ("Prevention plan", p.get("prevention_plan")),
        ])
    if t == "opposite_action":
        return _fields([
            ("Emotions", _before_after(opposite_action_emotion_rows(p))),
            ("Action urge", p.get("action_urge")),
            ("Fits the facts", p.get("fits_facts")),
            ("Opposite action", p.get("opposite_action")),
            ("Status", "Done" if opposite_action_is_complete(p) else "In progress"),
        ])
    if t == "abc":
        return _fields([
            ("Activating event", p.get("activating_event")),
            ("Belief", p.get("belief")),
            ("Consequence", p.get("consequence")),
            ("Alternate belief", p.get("alternate_belief")),
            ("Alternate consequence", p.get("alternate_consequence")),
        ])
    if t == "behavioral_activation":
        return _fields([
            ("Activity", p.get("activity")),
            ("Levels (now → after)", _before_after(behavioral_activation_emotion_rows(p))),
            ("Thoughts", p.get("additional_thoughts")),
            ("Status", "Done" if behavioral_activation_is_complete(p) else "In progress"),
        ])
    if t == "exposure_plan":
        suds = None
        if p.get("suds_before") is not None:
            suds = f"before {p.get('suds_before')}"
            if p.get("suds_peak") is not None:
                suds += f", peak {p.get('suds_peak')}"
            if p.get("suds_after") is not None:
                suds += f", after {p.get('suds_after')}"
        return _fields([
            ("Situation", p.get("situation")),
            ("SUDS", suds),
            ("Avoidance / safety behaviors", p.get("avoidance_or_safety_behaviors")),
            ("Notes", p.get("notes")),
            ("Status", "Done" if exposure_is_complete(p) else "In progress"),
        ])
    if t == "exposure_checkin":
        return _fields([
            ("SUDS", f"{p.get('suds_before')} → peak {p.get('suds_peak')} → {p.get('suds_after')}"),
            ("Avoidance / safety behaviors", p.get("avoidance_or_safety_behaviors")),
            ("Notes", p.get("notes")),
        ])
    if t == "checkin":
        urges = ", ".join(
            f"{u.get('behavior')} {u.get('intensity')}" for u in (p.get("urges") or []) if isinstance(u, dict)
        )
        return _fields([
            ("Emotions", _emotion_list(p.get("emotions"))),
            ("Urges", urges),
            ("Thoughts", p.get("description")),
        ])
    if t == "skill_used":
        return _fields([
            ("Skill", entry_summary(entry)),
            ("Note", p.get("note")),
        ])
    return []


def _diary_from_entry(entry) -> dict | None:
    p = entry.payload or {}
    if entry.type == "daily_planner":
        if not daily_planner_has_diary(p):
            return None
        emotions = p.get("diary_emotions") or []
        urges = p.get("diary_urges") or []
    elif entry.type == "diary_card":
        emotions = p.get("emotions") or []
        urges = p.get("urges") or []
    else:
        return None
    return {
        "emotions": [
            {"name": e.get("name"), "intensity": e.get("intensity")}
            for e in emotions
            if isinstance(e, dict) and e.get("name")
        ],
        "urges": [
            {"behavior": u.get("behavior"), "intensity": u.get("intensity")}
            for u in urges
            if isinstance(u, dict) and u.get("behavior")
        ],
    }


def _skills_from_entry(entry) -> list[dict]:
    p = entry.payload or {}
    if entry.type == "skill_used":
        raw = [{"module": p.get("module"), "skill": p.get("skill")}]
    elif entry.type == "daily_goal":
        raw = p.get("skills") or []
    else:
        return []
    out = []
    for s in raw:
        if not isinstance(s, dict) or not (s.get("skill") or s.get("module")):
            continue
        module = (s.get("module") or "").strip()
        out.append({
            "module": module,
            "module_label": SKILL_MODULE_LABELS.get(module, module),
            "skill": (s.get("skill") or "").strip(),
        })
    return out


def serialize_period(user, entries, prefs, *, include_journal: bool, base_url: str) -> dict:
    """Read-only snapshot for the week in review. Entries are pre-scoped to user."""
    days: dict[str, dict] = {}

    def day_bucket(key: str) -> dict:
        return days.setdefault(key, {"diary": None, "skills": [], "focus": "", "mantras": []})

    discuss = []
    journal = []
    for e in entries:
        key = _local_day(e.created_at)
        if not key:
            continue
        diary = _diary_from_entry(e)
        if diary is not None:
            diary["at"] = _iso_utc(e.created_at)
            day_bucket(key)["diary"] = diary
        if e.type == "daily_planner":
            focus = ((e.payload or {}).get("focus") or "").strip()
            if focus:
                day_bucket(key)["focus"] = focus
        skills = _skills_from_entry(e)
        if skills:
            day_bucket(key)["skills"].extend({**s, "at": _iso_utc(e.created_at)} for s in skills)
        if e.type in DISCUSS_TYPES:
            discuss.append({
                "entry_id": e.id,
                "type": e.type,
                "type_label": type_label(e.type),
                "day": key,
                "at": _iso_utc(e.created_at),
                "summary": entry_summary(e),
                "fields": _discuss_fields(e),
                "mark_for_review": bool(getattr(e, "mark_for_review", False)),
                "url": f"{base_url}/entry/{e.id}",
            })
        if e.type == "mantra_event":
            p = e.payload or {}
            action = (p.get("action") or "").strip()
            text = (p.get("text") or "").strip()
            if text and action in MANTRA_ACTION_LABELS:
                note = (p.get("journal") or "").strip() if include_journal else ""
                item = {
                    "entry_id": e.id,
                    "action": action,
                    "action_label": MANTRA_ACTION_LABELS[action],
                    "mantra_id": (p.get("mantra_id") or "").strip(),
                    "text": text,
                    "note": note,
                    "at": _iso_utc(e.created_at),
                    "mark_for_review": bool(getattr(e, "mark_for_review", False)),
                }
                day_bucket(key)["mantras"].append(item)
                if item["mark_for_review"]:
                    fields = [["Mantra", text], ["Action", item["action_label"]]]
                    if note:
                        fields.append(["Journal", note])
                    discuss.append({
                        "entry_id": e.id,
                        "type": "mantra_event",
                        "type_label": f"Mantra · {item['action_label']}",
                        "day": key,
                        "at": item["at"],
                        "summary": text,
                        "fields": fields,
                        "mark_for_review": True,
                        "url": f"{base_url}/entry/{e.id}",
                    })
        if include_journal and e.type == "journal":
            text = ((e.payload or {}).get("text") or "").strip()
            if text:
                journal.append({"day": key, "at": _iso_utc(e.created_at), "text": text})

    discuss.sort(key=lambda d: (not d["mark_for_review"], d["at"] or ""))
    tracked = list((prefs.diary_emotions if prefs else None) or DIARY_CARD_EMOTIONS)
    return {
        "ok": True,
        "user_found": True,
        "tracked_emotions": tracked,
        "days": days,
        "discuss": discuss,
        "journal": journal,
        "ledger_url": base_url,
    }


# --- Occurrences (phase 2): Ledger -> Long Track ---------------------------------


def occurrence_for(entry) -> dict | None:
    """Completion facts only. None when this entry is not (or no longer) an act-shaped moment."""
    p = entry.payload or {}
    t = entry.type
    trigger = None
    label = None
    detail: dict = {}
    if t in ("daily_planner", "diary_card"):
        if t == "daily_planner" and not daily_planner_has_diary(p):
            return None
        trigger, label = "diary_card", "Diary card"
    elif t == "checkin":
        trigger, label = "checkin", "Check-in"
    elif t == "journal":
        trigger, label = "journal", "Journal entry"
    elif t in ("skill_used", "daily_goal"):
        skills = _skills_from_entry(entry)
        if not skills:
            return None
        trigger = "skill_used"
        detail = {
            "modules": sorted({s["module"] for s in skills if s["module"]}),
            "skills": [s["skill"] for s in skills if s["skill"]],
        }
        label = "Skill: " + ", ".join(
            f"{s['skill']} ({s['module_label']})" if s["skill"] else s["module_label"] for s in skills
        )
    elif t == "opposite_action":
        if not opposite_action_is_complete(p):
            return None
        trigger, label = "opposite_action", "Opposite action"
    elif t == "behavioral_activation":
        if not behavioral_activation_is_complete(p):
            return None
        trigger, label = "behavioral_activation", "Behavioral activation"
    elif t == "exposure_plan":
        if not exposure_is_complete(p):
            return None
        trigger, label = "exposure", "Exposure"
    elif t in ("thought_record", "abc", "chain_analysis"):
        trigger, label = t, type_label(t)
    else:
        return None
    return {"trigger_type": trigger, "label": label[:255], "detail": detail}


def send_occurrence(entry, *, base_url: str, deleted: bool = False) -> dict | None:
    """Best effort POST to Long Track. Never raises; returns Long Track's JSON or None."""
    lt = long_track_url()
    token = pegasus_token()
    if not lt or not token or entry.type not in OCCURRENCE_ENTRY_TYPES:
        return None
    occ = None if deleted else occurrence_for(entry)
    user = getattr(entry, "user", None)
    if user is None or not getattr(user, "email", None):
        return None
    body = {
        "email": user.email,
        "entry_id": entry.id,
        "entry_type": entry.type,
        "deleted": deleted or occ is None,
        "occurred_at": _iso_utc(entry.created_at),
        "url": f"{base_url.rstrip('/')}/entry/{entry.id}",
    }
    if occ:
        body.update(occ)
    req = urllib.request.Request(
        f"{lt}/api/pegasus/occurrence",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=SEND_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001 — never block a Ledger save
        log.warning("Pegasus occurrence send failed for entry %s: %s", entry.id, exc)
        return None
