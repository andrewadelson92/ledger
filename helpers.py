"""Entry summaries, form parsing, and display helpers."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from constants import (
    ENTRY_TYPE_LABELS,
    SKILL_MODULE_LABELS,
    DIARY_CARD_EMOTIONS,
    BEHAVIORAL_ACTIVATION_EMOTIONS,
)


def type_label(entry_type: str) -> str:
    return ENTRY_TYPE_LABELS.get(entry_type, entry_type.replace("_", " ").title())


def entry_local_date(dt: datetime, tz: ZoneInfo) -> datetime.date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tz).date()


def find_todays_daily_goal(entries, tz: ZoneInfo, today=None):
    """Return the most recent daily_goal entry for the local calendar day, if any."""
    today = today or datetime.now(tz).date()
    for entry in entries:
        if entry.type != "daily_goal":
            continue
        if entry_local_date(entry.created_at, tz) == today:
            return entry
    return None


def entry_log_label(entry) -> str:
    label = type_label(entry.type)
    p = entry.payload or {}
    if entry.type == "behavioral_activation" and behavioral_activation_needs_outcome(p):
        return f"{label} · In progress"
    if entry.type == "exposure_plan" and exposure_needs_outcome(p):
        return f"{label} · In progress"
    return label


def _truncate(text: str | None, length: int = 80) -> str:
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


def entry_summary(entry) -> str:
    p = entry.payload or {}
    t = entry.type

    if t == "checkin":
        emotions = p.get("emotions") or []
        if emotions:
            names = ", ".join(e.get("name", "?") for e in emotions[:3])
            if len(emotions) > 3:
                names += f" +{len(emotions) - 3}"
            return names
        return _truncate(p.get("description")) or "Check-in"

    if t == "daily_goal":
        goal = _truncate(p.get("goal"), 60)
        skills = p.get("skills") or []
        if goal and skills:
            return f"{goal} · {len(skills)} skill{'s' if len(skills) != 1 else ''}"
        return goal or "Daily goal"

    if t == "diary_card":
        emotions = p.get("emotions") or []
        urges = p.get("urges") or []
        parts = []
        if emotions:
            parts.append(f"{len(emotions)} emotion{'s' if len(emotions) != 1 else ''}")
        if urges:
            parts.append(f"{len(urges)} urge{'s' if len(urges) != 1 else ''}")
        return " · ".join(parts) if parts else "Diary card"

    if t == "skill_used":
        module = p.get("module", "")
        skill = p.get("skill", "")
        mod_label = SKILL_MODULE_LABELS.get(module, module)
        return f"{mod_label}: {skill}" if skill else mod_label

    if t == "thought_record":
        return _truncate(p.get("automatic_thought") or p.get("situation")) or "Thought record"

    if t == "abc":
        return _truncate(p.get("activating_event") or p.get("belief")) or "ABC worksheet"

    if t == "behavioral_activation":
        activity = p.get("activity", "")
        if behavioral_activation_is_complete(p):
            return f"{_truncate(activity, 50)} — done"
        if behavioral_activation_has_plan(p):
            return f"In progress: {_truncate(activity, 50)}"
        return f"Planned: {_truncate(activity, 60)}"

    if t == "chain_analysis":
        return _truncate(p.get("problem_behavior") or p.get("prompting_event")) or "Chain analysis"

    if t == "exposure_plan":
        sit = _truncate(p.get("situation"), 60)
        if exposure_is_complete(p):
            before = p.get("suds_before")
            after = p.get("suds_after")
            if before is not None and after is not None:
                return f"SUDS {before} → {after}: {sit}"
            return f"{sit} — done"
        if exposure_has_plan(p):
            return f"In progress: {sit}"
        suds = p.get("predicted_peak_suds", p.get("predicted_suds"))
        return f"SUDS {suds}: {sit}" if suds is not None else sit or "Exposure"

    if t == "exposure_checkin":
        before = p.get("suds_before")
        after = p.get("suds_after")
        if before is not None and after is not None:
            return f"SUDS {before} → {after}"
        return _truncate(p.get("notes")) or "Exposure check-in"

    if t == "journal":
        if p.get("title"):
            return _truncate(p.get("title"))
        return _truncate(p.get("text")) or "Journal"

    return type_label(t)


def parse_skills_json(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    skills = []
    for item in data:
        if not isinstance(item, dict):
            continue
        module = (item.get("module") or "").strip()
        skill = (item.get("skill") or "").strip()
        if module and skill:
            skills.append({"module": module, "skill": skill})
    return skills


def parse_emotions_json(
    raw: str | None,
    intensity_key: str = "intensity",
    include_intensity: bool = True,
) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        entry: dict[str, Any] = {"name": name}
        if include_intensity:
            try:
                intensity = int(item.get(intensity_key, item.get("intensity", 1)))
            except (TypeError, ValueError):
                intensity = 1
            entry[intensity_key] = intensity
        out.append(entry)
    return out


def diary_card_emotion_values(emotions: list | None = None) -> list[tuple[str, int]]:
    by_name = {
        e.get("name"): e.get("intensity")
        for e in (emotions or [])
        if isinstance(e, dict) and e.get("name")
    }
    return [
        (name, max(1, min(5, int(by_name[name]) if by_name.get(name) is not None else 3)))
        for name in DIARY_CARD_EMOTIONS
    ]


def diary_card_extra_emotions(emotions: list | None = None) -> list[dict]:
    fixed = {name.lower() for name in DIARY_CARD_EMOTIONS}
    out = []
    for item in emotions or []:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name or name.lower() in fixed:
            continue
        intensity = item.get("intensity")
        try:
            intensity = max(1, min(5, int(intensity)))
        except (TypeError, ValueError):
            intensity = 3
        out.append({"name": name, "intensity": intensity})
    return out


def diary_emotion_field_name(emotion: str) -> str:
    return "diary_emotion_" + emotion.lower().replace(" ", "_")


def parse_diary_card_emotions(form) -> list[dict]:
    out = []
    for name in DIARY_CARD_EMOTIONS:
        key = diary_emotion_field_name(name)
        intensity = parse_int(form.get(key), default=3) or 3
        out.append({"name": name, "intensity": max(1, min(5, intensity))})
    fixed_lower = {name.lower() for name in DIARY_CARD_EMOTIONS}
    for item in parse_emotions_json(form.get("extra_emotions_json")):
        name = item.get("name", "").strip()
        if name and name.lower() not in fixed_lower:
            intensity = item.get("intensity", 3)
            try:
                intensity = max(1, min(5, int(intensity)))
            except (TypeError, ValueError):
                intensity = 3
            out.append({"name": name, "intensity": intensity})
    return out


def parse_journal_fields(form, existing: dict | None = None) -> dict:
    existing = existing or {}
    return {
        "title": (existing.get("title") or "").strip(),
        "text": (form.get("text") or "").strip(),
    }


def linked_journal_for(entry) -> Any | None:
    from models import Entry

    if entry.type != "diary_card":
        return None
    return Entry.query.filter_by(type="journal", linked_entry_id=entry.id).first()


def sync_diary_card_journal(diary_entry, form) -> None:
    from db import db
    from models import Entry

    fields = parse_journal_fields(form)
    existing = linked_journal_for(diary_entry)
    existing_payload = (existing.payload or {}) if existing else {}

    if not fields["text"]:
        if existing:
            db.session.delete(existing)
        return

    payload = parse_journal_fields(form, existing_payload)
    if existing:
        existing.payload = payload
        existing.updated_at = datetime.utcnow()
        return

    db.session.add(
        Entry(
            type="journal",
            payload=payload,
            linked_entry_id=diary_entry.id,
        )
    )


def parse_urges_json(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        behavior = (item.get("behavior") or "").strip()
        if not behavior:
            continue
        try:
            intensity = int(item.get("intensity", 1))
        except (TypeError, ValueError):
            intensity = 1
        intensity = max(1, min(5, intensity))
        out.append({"behavior": behavior, "intensity": intensity})
    return out


def parse_chain_links(form_data) -> list[dict]:
    valid_types = {"thought", "feeling", "body_sensation", "action"}
    links = []
    idx = 0
    while True:
        link_type = (form_data.get(f"chain_type_{idx}") or "").strip()
        text = (form_data.get(f"chain_text_{idx}") or "").strip()
        if not text:
            if idx == 0:
                idx += 1
                continue
            break
        if link_type not in valid_types:
            link_type = "thought"
        links.append({"type": link_type, "text": text})
        idx += 1
    return links


CHAIN_LINK_TYPE_LABELS = {
    "thought": "Thought",
    "feeling": "Feeling",
    "body_sensation": "Body sensation",
    "action": "Action",
}


def chain_link_type_label(link_type: str) -> str:
    return CHAIN_LINK_TYPE_LABELS.get(link_type, link_type.replace("_", " ").title())


def parse_datetime_local(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_int(value: str | None, default: int | None = None) -> int | None:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def payload_for_type(entry_type: str, form) -> tuple[dict[str, Any], int | None, str | None]:
    """Parse POST form into payload, optional linked_entry_id, optional secondary_tag."""
    linked_entry_id = None
    secondary_tag = None

    if entry_type == "checkin":
        payload = {
            "emotions": parse_emotions_json(form.get("emotions_json"), include_intensity=False),
            "description": (form.get("description") or "").strip(),
        }

    elif entry_type == "daily_goal":
        payload = {
            "goal": (form.get("goal") or "").strip(),
            "skills": parse_skills_json(form.get("skills_json")),
        }

    elif entry_type == "diary_card":
        payload = {
            "emotions": parse_diary_card_emotions(form),
            "urges": parse_urges_json(form.get("urges_json")),
        }

    elif entry_type == "skill_used":
        module = (form.get("module") or "").strip()
        payload = {
            "module": module,
            "skill": (form.get("skill") or "").strip(),
            "note": (form.get("note") or "").strip(),
        }
        if module == "IE" and form.get("involved_person"):
            secondary_tag = "People"

    elif entry_type == "thought_record":
        payload = {
            "situation": (form.get("situation") or "").strip(),
            "automatic_thought": (form.get("automatic_thought") or "").strip(),
            "emotions": parse_emotions_json(form.get("emotions_before_json"), "intensity_before"),
            "evidence_for": (form.get("evidence_for") or "").strip(),
            "evidence_against": (form.get("evidence_against") or "").strip(),
            "alternative_thought": (form.get("alternative_thought") or "").strip(),
            "emotions_after": parse_emotions_json(form.get("emotions_after_json"), "intensity_after"),
        }

    elif entry_type == "abc":
        payload = {
            "activating_event": (form.get("activating_event") or "").strip(),
            "belief": (form.get("belief") or "").strip(),
            "consequence": (form.get("consequence") or "").strip(),
            "alternate_belief": (form.get("alternate_belief") or "").strip(),
            "alternate_consequence": (form.get("alternate_consequence") or "").strip(),
        }

    elif entry_type == "behavioral_activation":
        payload = parse_behavioral_activation_plan(form)

    elif entry_type == "chain_analysis":
        payload = {
            "vulnerability_factors": (form.get("vulnerability_factors") or "").strip(),
            "prompting_event": (form.get("prompting_event") or "").strip(),
            "chain_links": parse_chain_links(form),
            "problem_behavior": (form.get("problem_behavior") or "").strip(),
            "consequences_short_term": (form.get("consequences_short_term") or "").strip(),
            "consequences_long_term": (form.get("consequences_long_term") or "").strip(),
            "prevention_plan": (form.get("prevention_plan") or "").strip(),
        }

    elif entry_type == "exposure_plan":
        payload = parse_exposure_plan(form)

    elif entry_type == "exposure_checkin":
        linked_entry_id = parse_int(form.get("linked_entry_id"))
        payload = {
            "suds_before": parse_int(form.get("suds_before")),
            "suds_peak": parse_int(form.get("suds_peak")),
            "suds_after": parse_int(form.get("suds_after")),
            "avoidance_or_safety_behaviors": (form.get("avoidance_or_safety_behaviors") or "").strip(),
            "notes": (form.get("notes") or "").strip(),
        }

    elif entry_type == "journal":
        payload = parse_journal_fields(form)

    else:
        payload = {}

    return payload, linked_entry_id, secondary_tag


def behavioral_activation_emotion_rows(payload: dict | None = None) -> list[dict]:
    stored = (payload or {}).get("emotions") or {}
    rows = []
    for spec in BEHAVIORAL_ACTIVATION_EMOTIONS:
        key = spec["key"]
        levels = stored.get(key) or {}
        rows.append({
            "key": key,
            "label": spec["label"],
            "current": levels.get("current"),
            "predicted": levels.get("predicted"),
            "new": levels.get("new"),
        })
    return rows


def behavioral_activation_has_plan(payload: dict | None = None) -> bool:
    for row in behavioral_activation_emotion_rows(payload):
        if row["current"] is None or row["predicted"] is None:
            return False
    return True


def behavioral_activation_is_complete(payload: dict | None = None) -> bool:
    p = payload or {}
    if p.get("actual_mood") is not None:
        return True
    emotions = p.get("emotions")
    if not emotions:
        return False
    for row in behavioral_activation_emotion_rows(p):
        if row["new"] is None:
            return False
    return True


def behavioral_activation_needs_outcome(payload: dict | None = None) -> bool:
    p = payload or {}
    if p.get("actual_mood") is not None:
        return False
    return behavioral_activation_has_plan(p) and not behavioral_activation_is_complete(p)


def parse_behavioral_activation_plan(form, existing: dict | None = None) -> dict:
    existing = existing or {}
    planned = parse_datetime_local(form.get("planned_datetime"))
    emotions = dict(existing.get("emotions") or {})
    for spec in BEHAVIORAL_ACTIVATION_EMOTIONS:
        key = spec["key"]
        prior = emotions.get(key) or {}
        emotions[key] = {
            "current": parse_int(form.get(f"{key}_current")),
            "predicted": parse_int(form.get(f"{key}_predicted")),
            "new": prior.get("new"),
        }
    return {
        "activity": (form.get("activity") or "").strip(),
        "planned_datetime": planned.isoformat() if planned else None,
        "emotions": emotions,
        "additional_thoughts": (existing.get("additional_thoughts") or "").strip(),
    }


def merge_behavioral_outcome(existing: dict, form) -> dict:
    payload = dict(existing)
    emotions = dict(payload.get("emotions") or {})
    for spec in BEHAVIORAL_ACTIVATION_EMOTIONS:
        key = spec["key"]
        levels = dict(emotions.get(key) or {})
        new_level = parse_int(form.get(f"{key}_new"))
        if new_level is not None:
            levels["new"] = new_level
        emotions[key] = levels
    payload["emotions"] = emotions
    thoughts = (form.get("additional_thoughts") or "").strip()
    if thoughts:
        payload["additional_thoughts"] = thoughts
    return payload


def exposure_predicted_peak(payload: dict | None) -> int | None:
    p = payload or {}
    peak = p.get("predicted_peak_suds")
    if peak is not None:
        return peak
    return p.get("predicted_suds")


def exposure_has_plan(payload: dict | None = None) -> bool:
    p = payload or {}
    if not p.get("situation"):
        return False
    return p.get("suds_before") is not None and exposure_predicted_peak(p) is not None


def exposure_is_complete(payload: dict | None = None) -> bool:
    p = payload or {}
    return p.get("suds_peak") is not None and p.get("suds_after") is not None


def exposure_needs_outcome(payload: dict | None = None) -> bool:
    return exposure_has_plan(payload) and not exposure_is_complete(payload)


def parse_exposure_plan(form, existing: dict | None = None) -> dict:
    existing = existing or {}
    planned = parse_datetime_local(form.get("planned_datetime"))
    return {
        "situation": (form.get("situation") or "").strip(),
        "planned_datetime": planned.isoformat() if planned else None,
        "suds_before": parse_int(form.get("suds_before")),
        "predicted_peak_suds": parse_int(form.get("predicted_peak_suds")),
        "suds_peak": existing.get("suds_peak"),
        "suds_after": existing.get("suds_after"),
        "avoidance_or_safety_behaviors": (existing.get("avoidance_or_safety_behaviors") or "").strip(),
        "notes": (existing.get("notes") or "").strip(),
    }


def merge_exposure_outcome(existing: dict, form) -> dict:
    payload = dict(existing)
    payload["suds_peak"] = parse_int(form.get("suds_peak"))
    payload["suds_after"] = parse_int(form.get("suds_after"))
    avoidance = (form.get("avoidance_or_safety_behaviors") or "").strip()
    if avoidance:
        payload["avoidance_or_safety_behaviors"] = avoidance
    notes = (form.get("notes") or "").strip()
    if notes:
        payload["notes"] = notes
    return payload


def entry_in_progress_can_delete(entry) -> bool:
    p = entry.payload or {}
    if entry.type == "behavioral_activation":
        return behavioral_activation_needs_outcome(p)
    if entry.type == "exposure_plan":
        return exposure_needs_outcome(p)
    return False


def format_datetime_local(iso_value: str | None) -> str:
    if not iso_value:
        return ""
    try:
        dt = datetime.fromisoformat(iso_value)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return ""
