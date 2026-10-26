from flask import Flask, Response, render_template, request, redirect, url_for, flash, abort, jsonify
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import sys
import uuid

_app_root = os.path.dirname(os.path.abspath(__file__))

# Demo mode must set DB path before load_config.
DEMO_USER_EMAIL = "demo@localhost"
DEMO_USER_PASSWORD = "demopass123"
_is_demo = len(sys.argv) >= 2 and sys.argv[1].lower() == "demo"
_demo_clear = (
    len(sys.argv) >= 3
    and sys.argv[1].lower() == "demo"
    and sys.argv[2].lower() == "clear"
)
if _is_demo:
    _demo_db = os.path.join(_app_root, "instance", "demo_ledger.db")
    os.makedirs(os.path.join(_app_root, "instance"), exist_ok=True)
    if _demo_clear:
        try:
            os.remove(_demo_db)
        except FileNotFoundError:
            pass
    os.environ["LEDGER_DB_PATH"] = _demo_db

from db import db
from config import load_config
from models import AudioClip, Entry, Invite, User, UserPreference
from flask_login import login_user, logout_user, current_user
from auth import (
    login_manager,
    PUBLIC_ENDPOINTS,
    uid,
    entries_q,
    get_entry,
    set_password,
    check_password,
    get_or_create_preferences,
    create_invite,
    validate_invite_token,
    cancel_invite,
)
from constants import (
    ENTRY_TYPES,
    ENTRY_TYPE_LABELS,
    HOME_ADD_LABELS,
    MODULE_SKILLS,
    SKILL_MODULE_LABELS,
    EMOTION_WHEEL,
    BEHAVIORAL_ACTIVATION_EMOTIONS,
    DEFAULT_TARGET_BEHAVIORS,
    DIARY_CARD_EMOTIONS,
)
from helpers import (
    type_label,
    entry_summary,
    payload_for_type,
    merge_behavioral_outcome,
    format_datetime_local,
    chain_link_type_label,
    diary_card_emotion_values,
    diary_card_extra_emotions,
    diary_emotion_field_name,
    behavioral_activation_emotion_rows,
    behavioral_activation_needs_outcome,
    behavioral_activation_is_complete,
    behavioral_activation_has_plan,
    parse_behavioral_activation_plan,
    entry_log_label,
    exposure_has_plan,
    exposure_is_complete,
    exposure_needs_outcome,
    exposure_predicted_peak,
    score_max,
    parse_exposure_plan,
    merge_exposure_outcome,
    opposite_action_has_plan,
    opposite_action_needs_outcome,
    opposite_action_emotion_rows,
    parse_opposite_action_plan,
    merge_opposite_action_outcome,
    entry_can_delete,
    linked_journal_for,
    sync_diary_card_journal,
    keep_legacy_diary_journal,
    parse_id_list,
    parse_int,
    parse_journal_fields,
    find_todays_daily_goal,
    find_todays_entry,
    agenda_slots_for_form,
    format_planner_hour,
    emotion_wheel_excluding,
    daily_planner_focus,
    daily_planner_has_diary,
    normalize_committed_actions,
    diary_card_extra_emotions,
    mantra_library_items,
    todays_invoked_mantras,
)

import pegasus

ADD_HIDDEN_TYPES = frozenset({"exposure_checkin", "daily_goal", "diary_card", "mantra_event"})

# Worksheets that can be marked for review (listed first in the week in review).
REVIEWABLE_TYPES = frozenset({
    "mantra_event",
    "checkin",
    "skill_used",
    "thought_record",
    "opposite_action",
    "abc",
    "behavioral_activation",
    "chain_analysis",
    "exposure_plan",
    "exposure_checkin",
    "journal",
})

app = Flask(__name__)
load_config(app)
db.init_app(app)
login_manager.init_app(app)

from flask_migrate import Migrate

migrate = Migrate(app, db, directory=os.path.join(_app_root, "migrations"))

LOCAL_TZ = ZoneInfo("America/Los_Angeles")


@app.template_filter("fmt_local")
def fmt_local(dt):
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(LOCAL_TZ).strftime("%b %d, %Y · %I:%M %p")


@app.template_filter("fmt_date")
def fmt_date(dt):
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(LOCAL_TZ).strftime("%b %d, %Y")


@app.context_processor
def inject_globals():
    target_behaviors = list(DEFAULT_TARGET_BEHAVIORS)
    diary_emotions = list(DIARY_CARD_EMOTIONS)
    if current_user.is_authenticated:
        prefs = get_or_create_preferences()
        if prefs.target_behaviors:
            target_behaviors = list(prefs.target_behaviors)
        if prefs.diary_emotions:
            diary_emotions = list(prefs.diary_emotions)
    nav_tab = None
    if request.endpoint == "index":
        nav_tab = (request.args.get("tab") or "today").strip().lower()
        if nav_tab not in ("today", "log", "add"):
            nav_tab = "today"
    return {
        "entry_type_labels": ENTRY_TYPE_LABELS,
        "skill_module_labels": SKILL_MODULE_LABELS,
        "module_skills": MODULE_SKILLS,
        "emotion_wheel": EMOTION_WHEEL,
        "default_target_behaviors": target_behaviors,
        "diary_card_emotions": diary_emotions,
        "nav_tab": nav_tab,
        "chain_link_type_label": chain_link_type_label,
        "diary_card_emotion_values": diary_card_emotion_values,
        "diary_card_extra_emotions": diary_card_extra_emotions,
        "diary_emotion_field_name": diary_emotion_field_name,
        "behavioral_activation_emotions": BEHAVIORAL_ACTIVATION_EMOTIONS,
        "behavioral_activation_emotion_rows": behavioral_activation_emotion_rows,
        "behavioral_activation_needs_outcome": behavioral_activation_needs_outcome,
        "behavioral_activation_is_complete": behavioral_activation_is_complete,
        "behavioral_activation_has_plan": behavioral_activation_has_plan,
        "exposure_has_plan": exposure_has_plan,
        "exposure_is_complete": exposure_is_complete,
        "exposure_needs_outcome": exposure_needs_outcome,
        "exposure_predicted_peak": exposure_predicted_peak,
        "score_max": score_max,
        "agenda_slots_for_form": agenda_slots_for_form,
        "format_planner_hour": format_planner_hour,
        "daily_planner_focus": daily_planner_focus,
        "daily_planner_has_diary": daily_planner_has_diary,
        "normalize_committed_actions": normalize_committed_actions,
        "current_user": current_user,
        "is_demo": _is_demo,
        "demo_user_email": DEMO_USER_EMAIL if _is_demo else None,
    }


for _name, _fn in (
    ("chain_link_type_label", chain_link_type_label),
    ("diary_card_emotion_values", diary_card_emotion_values),
    ("diary_card_extra_emotions", diary_card_extra_emotions),
    ("diary_emotion_field_name", diary_emotion_field_name),
    ("behavioral_activation_emotion_rows", behavioral_activation_emotion_rows),
    ("behavioral_activation_needs_outcome", behavioral_activation_needs_outcome),
    ("behavioral_activation_is_complete", behavioral_activation_is_complete),
    ("behavioral_activation_has_plan", behavioral_activation_has_plan),
    ("exposure_has_plan", exposure_has_plan),
    ("exposure_is_complete", exposure_is_complete),
    ("exposure_needs_outcome", exposure_needs_outcome),
    ("exposure_predicted_peak", exposure_predicted_peak),
    ("score_max", score_max),
    ("agenda_slots_for_form", agenda_slots_for_form),
    ("format_planner_hour", format_planner_hour),
    ("daily_planner_focus", daily_planner_focus),
    ("daily_planner_has_diary", daily_planner_has_diary),
    ("normalize_committed_actions", normalize_committed_actions),
):
    app.add_template_global(_fn, _name)


def _bootstrap_database():
    """Apply migrations on startup for local SQLite; production uses pre-deploy too."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    is_sqlite = uri.startswith("sqlite")

    from flask_migrate import upgrade

    try:
        upgrade()
    except Exception:
        if is_sqlite:
            db.create_all()
        else:
            raise


def _running_flask_db_command() -> bool:
    if "db" not in sys.argv:
        return False
    migrate_subcmds = {
        "upgrade", "downgrade", "stamp", "migrate",
        "revision", "current", "history", "heads",
    }
    return bool(migrate_subcmds.intersection(sys.argv))


def _ensure_demo_blank_user() -> User:
    """Local demo only: ensure a blank-slate login exists on the demo DB."""
    from constants import DEFAULT_TARGET_BEHAVIORS, DIARY_CARD_EMOTIONS

    user = User.query.filter_by(email=DEMO_USER_EMAIL).first()
    if user is None:
        user = User(email=DEMO_USER_EMAIL, is_active=True)
        db.session.add(user)
        db.session.flush()
    set_password(user, DEMO_USER_PASSWORD)
    user.is_active = True
    db.session.commit()
    prefs = get_or_create_preferences(user.id)
    prefs.saved_emotions = []
    prefs.saved_skills = []
    prefs.target_behaviors = list(DEFAULT_TARGET_BEHAVIORS)
    prefs.diary_emotions = list(DIARY_CARD_EMOTIONS)
    prefs.show_feelings_wheel = True
    prefs.updated_at = datetime.utcnow()
    db.session.commit()
    return user


def _reset_demo_database() -> User:
    """Wipe the demo DB contents and recreate the blank demo login."""
    AudioClip.query.delete()
    Entry.query.delete()
    Invite.query.delete()
    UserPreference.query.delete()
    User.query.delete()
    db.session.commit()
    return _ensure_demo_blank_user()


with app.app_context():
    if not _running_flask_db_command():
        _bootstrap_database()
        if _is_demo:
            _ensure_demo_blank_user()


@app.before_request
def _require_login():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return
    if request.endpoint and request.endpoint.startswith("static"):
        return
    if not current_user.is_authenticated:
        return login_manager.unauthorized()


@app.route("/")
def index():
    tab = request.args.get("tab", "today").strip().lower()
    if tab not in ("today", "log", "add"):
        tab = "today"

    entries = entries_q().order_by(Entry.created_at.desc()).all()
    cards = [
        {
            "entry": e,
            "label": entry_log_label(e),
        }
        for e in entries
        if e.type != "mantras"  # library doc; actions log as mantra_event
    ]
    in_progress_items = []
    for e in entries:
        p = e.payload or {}
        if e.type == "behavioral_activation" and behavioral_activation_needs_outcome(p):
            in_progress_items.append({
                "entry": e,
                "kind": "Behavioral activation",
                "title": p.get("activity"),
            })
        elif e.type == "exposure_plan" and exposure_needs_outcome(p):
            in_progress_items.append({
                "entry": e,
                "kind": "Exposure",
                "title": p.get("situation"),
            })
        elif e.type == "opposite_action" and opposite_action_needs_outcome(p):
            in_progress_items.append({
                "entry": e,
                "kind": "Opposite action",
                "title": p.get("opposite_action") or p.get("action_urge"),
            })
    add_options = [
        {"type": t, "label": HOME_ADD_LABELS.get(t, ENTRY_TYPE_LABELS[t])}
        for t in ENTRY_TYPES
        if t not in ADD_HIDDEN_TYPES and t != "daily_planner"
    ]
    today_label = datetime.now(LOCAL_TZ).strftime("%A, %b %d")
    return render_template(
        "index.html",
        cards=cards,
        tab=tab,
        add_options=add_options,
        in_progress_items=in_progress_items,
        todays_daily_planner=_todays_daily_planner(),
        invoked_mantras=todays_invoked_mantras(entries, LOCAL_TZ),
        mantra_library=mantra_library_items(
            (lib.payload if (lib := _current_mantras()) else None)
        ),
        today_label=today_label,
        daily_planner_focus=daily_planner_focus,
        daily_planner_has_diary=daily_planner_has_diary,
        diary_card_emotion_values=diary_card_emotion_values,
    )


def _get_entry_or_404(entry_id: int) -> Entry:
    return get_entry(entry_id)


def _touch_entry(entry: Entry) -> None:
    entry.updated_at = datetime.utcnow()


def _make_entry(**kwargs) -> Entry:
    kwargs.setdefault("user_id", uid())
    if kwargs.get("type") in REVIEWABLE_TYPES:
        kwargs.setdefault("mark_for_review", "mark_for_review" in request.form)
    return Entry(**kwargs)


def _ledger_base_url() -> str:
    return (os.getenv("LEDGER_PUBLIC_URL") or request.url_root).rstrip("/")


def _pegasus_notify(entry: Entry, deleted: bool = False) -> None:
    """Tell Long Track about a completion-shaped entry; store what it did. Never blocks a save."""
    result = pegasus.send_occurrence(entry, base_url=_ledger_base_url(), deleted=deleted)
    if deleted or not result or not result.get("ok"):
        return
    status = {"status": result.get("status"), "landed": result.get("landed") or []}
    if entry.pegasus_status != status:
        entry.pegasus_status = status
        db.session.commit()


def _exposure_plans():
    return (
        entries_q()
        .filter_by(type="exposure_plan")
        .order_by(Entry.created_at.desc())
        .all()
    )


def _todays_daily_goal():
    candidates = (
        entries_q()
        .filter_by(type="daily_goal")
        .order_by(Entry.created_at.desc())
        .all()
    )
    return find_todays_daily_goal(candidates, LOCAL_TZ)


def _todays_daily_planner():
    candidates = (
        entries_q()
        .filter_by(type="daily_planner")
        .order_by(Entry.created_at.desc())
        .all()
    )
    return find_todays_entry(candidates, "daily_planner", LOCAL_TZ)


def _current_mantras():
    """Return the single mantras library entry for the current user, if any."""
    return (
        entries_q()
        .filter_by(type="mantras")
        .order_by(Entry.updated_at.desc(), Entry.created_at.desc())
        .first()
    )


def _ensure_mantras_library() -> Entry:
    existing = _current_mantras()
    if existing:
        items = mantra_library_items(existing.payload)
        if items != (existing.payload or {}).get("items"):
            existing.payload = {"items": items}
            _touch_entry(existing)
            db.session.commit()
        return existing
    entry = _make_entry(type="mantras", payload={"items": []})
    db.session.add(entry)
    db.session.commit()
    return entry


def _log_mantra_event(action: str, mantra_id: str, text: str, journal: str = "", **extra) -> Entry:
    entry = _make_entry(
        type="mantra_event",
        payload={
            "action": action,
            "mantra_id": mantra_id,
            "text": text,
            "journal": (journal or "").strip(),
        },
        **extra,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def _save_daily_goal(payload: dict) -> Entry:
    existing = _todays_daily_goal()
    if existing:
        existing.payload = payload
        _touch_entry(existing)
        db.session.commit()
        _pegasus_notify(existing)
        return existing
    entry = _make_entry(type="daily_goal", payload=payload)
    db.session.add(entry)
    db.session.commit()
    _pegasus_notify(entry)
    return entry


def _save_daily_planner(payload: dict) -> Entry:
    existing = _todays_daily_planner()
    if existing:
        existing.payload = keep_legacy_diary_journal(payload, existing.payload)
        _touch_entry(existing)
        db.session.commit()
        _pegasus_notify(existing)
        return existing
    entry = _make_entry(type="daily_planner", payload=payload)
    db.session.add(entry)
    db.session.commit()
    _pegasus_notify(entry)
    return entry


def _form_render_ctx(entry_type: str, payload: dict | None, entry=None, form=None, **extra):
    ctx = {
        "entry_type": entry_type,
        "entry_label": type_label(entry_type),
        "payload": payload or {},
        **extra,
    }
    if entry_type in REVIEWABLE_TYPES:
        if request.method == "POST":
            ctx["mark_for_review"] = "mark_for_review" in request.form
        elif entry is not None:
            ctx["mark_for_review"] = bool(entry.mark_for_review)
        elif extra.get("entry_id"):
            existing = entries_q().filter_by(id=extra["entry_id"]).first()
            ctx["mark_for_review"] = bool(existing and existing.mark_for_review)
        else:
            ctx["mark_for_review"] = False
    if entry_type == "daily_planner":
        prefs = get_or_create_preferences()
        tracked = list(prefs.diary_emotions or DIARY_CARD_EMOTIONS)
        payload = dict(ctx["payload"])
        # Fold legacy diary-card extras into noted emotions (intensity is optional there).
        noted = list(payload.get("noted_emotions") or [])
        seen = {(e.get("name") or "").strip().lower() for e in noted if isinstance(e, dict)}
        for extra_e in diary_card_extra_emotions(payload.get("diary_emotions"), tracked):
            name = (extra_e.get("name") or "").strip()
            if name and name.lower() not in seen:
                noted.append({"name": name, "intensity": extra_e.get("intensity")})
                seen.add(name.lower())
        payload["noted_emotions"] = noted
        ctx["payload"] = payload
        ctx["agenda_slots"] = agenda_slots_for_form(payload)
        ctx["noted_emotion_wheel"] = emotion_wheel_excluding(tracked)
        ctx["diary_card_emotions"] = tracked
        ctx["default_target_behaviors"] = list(
            prefs.target_behaviors or DEFAULT_TARGET_BEHAVIORS
        )
    if entry_type == "diary_card":
        prefs = get_or_create_preferences()
        tracked = list(prefs.diary_emotions or DIARY_CARD_EMOTIONS)
        ctx["diary_card_emotions"] = tracked
        ctx["default_target_behaviors"] = list(
            prefs.target_behaviors or DEFAULT_TARGET_BEHAVIORS
        )
        ctx["extra_emotions"] = diary_card_extra_emotions(
            ctx["payload"].get("emotions"), tracked
        )
        if form is not None:
            ctx["journal_payload"] = {"text": parse_journal_fields(form).get("text", "")}
        elif entry is not None:
            linked = linked_journal_for(entry)
            journal_payload = dict(linked.payload) if linked and linked.payload else {}
            ctx["journal_payload"] = {"text": journal_payload.get("text", "")}
        else:
            ctx["journal_payload"] = {}
    if entry_type == "journal":
        ctx["audio_clips"] = _clips_for_ids(ctx["payload"].get("audio_clip_ids"))
    if entry_type == "checkin":
        prefs = get_or_create_preferences()
        tracked = list(prefs.diary_emotions or DIARY_CARD_EMOTIONS)
        ctx["show_feelings_wheel"] = bool(prefs.show_feelings_wheel)
        ctx["diary_card_emotions"] = tracked
        ctx["extra_emotions"] = diary_card_extra_emotions(
            ctx["payload"].get("emotions"), tracked
        )
        ctx["default_target_behaviors"] = list(
            prefs.target_behaviors or DEFAULT_TARGET_BEHAVIORS
        )
    return ctx


def _save_entry(entry: Entry, entry_type: str | None = None) -> None:
    db.session.add(entry)
    if (entry_type or entry.type) == "journal":
        _sync_journal_audio(entry, (entry.payload or {}).get("audio_clip_ids") or [])
    if (entry_type or entry.type) == "diary_card":
        db.session.flush()
        sync_diary_card_journal(entry, request.form)
    db.session.commit()
    _pegasus_notify(entry)


AUDIO_MAX_BYTES = 25 * 1024 * 1024
AUDIO_ORPHAN_TTL = timedelta(days=1)


def _owned_clip_ids(ids: list[int], entry_id: int | None = None) -> list[int]:
    """Clip ids the current user may attach: unattached uploads or clips already on this entry."""
    if not ids:
        return []
    clips = AudioClip.query.filter(AudioClip.user_id == uid(), AudioClip.id.in_(ids)).all()
    allowed = {c.id for c in clips if c.entry_id is None or c.entry_id == entry_id}
    return [i for i in ids if i in allowed]


def _clips_for_ids(ids) -> list[AudioClip]:
    ids = [i for i in (ids or []) if isinstance(i, int)]
    if not ids:
        return []
    by_id = {
        c.id: c
        for c in AudioClip.query.filter(AudioClip.user_id == uid(), AudioClip.id.in_(ids))
    }
    return [by_id[i] for i in ids if i in by_id]


def _sync_journal_audio(entry: Entry, ids: list[int]) -> None:
    keep = set(ids)
    for clip in list(entry.audio_clips):
        if clip.id not in keep:
            entry.audio_clips.remove(clip)
    attached = {c.id for c in entry.audio_clips}
    for clip in _clips_for_ids([i for i in ids if i not in attached]):
        entry.audio_clips.append(clip)


def _audio_mime(raw: str | None) -> str | None:
    base = (raw or "").split(";")[0].strip().lower()
    if base.startswith("video/"):
        base = "audio/" + base.split("/", 1)[1]
    return base if base.startswith("audio/") else None


@app.route("/api/audio", methods=["POST"])
def audio_upload():
    upload = request.files.get("audio")
    if upload is None:
        return jsonify({"error": "No audio received."}), 400
    mime = _audio_mime(upload.mimetype)
    if not mime:
        return jsonify({"error": "Unsupported audio format."}), 400
    data = upload.read(AUDIO_MAX_BYTES + 1)
    if not data:
        return jsonify({"error": "Recording was empty."}), 400
    if len(data) > AUDIO_MAX_BYTES:
        return jsonify({"error": "Recording is too long."}), 413

    AudioClip.query.filter(
        AudioClip.user_id == uid(),
        AudioClip.entry_id.is_(None),
        AudioClip.created_at < datetime.utcnow() - AUDIO_ORPHAN_TTL,
    ).delete(synchronize_session=False)

    clip = AudioClip(
        user_id=uid(),
        mime_type=mime,
        duration_ms=parse_int(request.form.get("duration_ms")),
        size_bytes=len(data),
        data=data,
    )
    db.session.add(clip)
    db.session.commit()
    return jsonify({
        "id": clip.id,
        "url": url_for("audio_file", clip_id=clip.id),
        "duration_ms": clip.duration_ms,
    })


@app.route("/audio/<int:clip_id>")
def audio_file(clip_id):
    clip = AudioClip.query.filter_by(id=clip_id, user_id=uid()).first()
    if clip is None:
        abort(404)
    data = bytes(clip.data)
    total = len(data)
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"}
    byte_range = request.range.range_for_length(total) if request.range else None
    if request.range and byte_range is None:
        headers["Content-Range"] = f"bytes */{total}"
        return Response(status=416, headers=headers)
    if byte_range:
        start, stop = byte_range
        headers["Content-Range"] = f"bytes {start}-{stop - 1}/{total}"
        return Response(data[start:stop], status=206, mimetype=clip.mime_type, headers=headers)
    return Response(data, mimetype=clip.mime_type, headers=headers)


@app.route("/health")
def health():
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    db_kind = "postgres" if uri.startswith("postgresql") else "sqlite"
    return jsonify({"ok": True, "db": db_kind})


@app.route("/api/pegasus/entries", methods=["GET"])
def api_pegasus_entries():
    """Read-only period snapshot for Long Track's week in review (token auth, by email)."""
    if not pegasus.pegasus_token():
        abort(404)
    if not pegasus.token_ok(request.headers.get("Authorization")):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    email = (request.args.get("email") or "").strip().lower()
    try:
        start = datetime.fromisoformat(request.args.get("start") or "")
        end = datetime.fromisoformat(request.args.get("end") or "")
    except ValueError:
        return jsonify({"ok": False, "error": "start and end must be ISO datetimes (UTC)"}), 400
    user = User.query.filter(db.func.lower(User.email) == email).first() if email else None
    if user is None or not user.is_active:
        return jsonify({"ok": True, "user_found": False})
    entries = (
        Entry.query.filter(
            Entry.user_id == user.id,
            Entry.created_at >= start,
            Entry.created_at <= end,
            Entry.type != "mantras",
        )
        .order_by(Entry.created_at.asc())
        .all()
    )
    prefs = UserPreference.query.filter_by(user_id=user.id).first()
    return jsonify(
        pegasus.serialize_period(
            user,
            entries,
            prefs,
            include_journal=request.args.get("include_journal") == "1",
            base_url=_ledger_base_url(),
        )
    )


@app.route("/new")
def new_picker():
    return redirect(url_for("index", tab="add"))


@app.route("/new/<entry_type>", methods=["GET", "POST"])
def new_entry(entry_type):
    if entry_type not in ENTRY_TYPES or entry_type in ADD_HIDDEN_TYPES:
        abort(404)

    if request.method == "POST":
        payload, linked_entry_id, secondary_tag = payload_for_type(entry_type, request.form)
        if entry_type == "journal":
            payload["audio_clip_ids"] = _owned_clip_ids(
                parse_id_list(request.form.get("audio_clip_ids"))
            )
            if not payload.get("text") and not payload["audio_clip_ids"]:
                flash("Write something or record audio.")
                return render_template(
                    f"forms/{entry_type}.html",
                    **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
                )
        if entry_type == "behavioral_activation":
            if not payload.get("activity") or not payload.get("planned_datetime"):
                flash("Activity and planned date & time are required.")
            elif not behavioral_activation_has_plan(payload):
                flash("Rate current and predicted levels for joy and sadness.")
            else:
                entry = _make_entry(
                    type=entry_type,
                    payload=payload,
                    linked_entry_id=linked_entry_id,
                    secondary_tag=secondary_tag,
                )
                db.session.add(entry)
                db.session.commit()
                flash("Behavioral activation in progress.")
                return redirect(url_for("index", tab="today"))
            return render_template(
                f"forms/{entry_type}.html",
                **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
            )
        if entry_type == "exposure_plan":
            if not payload.get("situation"):
                flash("Situation is required.")
            elif not exposure_has_plan(payload):
                flash("Rate SUDS before and predicted peak SUDS.")
            else:
                entry = _make_entry(
                    type=entry_type,
                    payload=payload,
                    linked_entry_id=linked_entry_id,
                    secondary_tag=secondary_tag,
                )
                db.session.add(entry)
                db.session.commit()
                flash("Exposure in progress.")
                return redirect(url_for("index", tab="today"))
            return render_template(
                f"forms/{entry_type}.html",
                **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
            )
        if entry_type == "opposite_action":
            if not opposite_action_has_plan(payload):
                flash("Add an emotion and describe the opposite action.")
                return render_template(
                    f"forms/{entry_type}.html",
                    **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
                )
            entry = _make_entry(
                type=entry_type,
                payload=payload,
                linked_entry_id=linked_entry_id,
                secondary_tag=secondary_tag,
            )
            db.session.add(entry)
            db.session.commit()
            flash("Opposite action in progress.")
            return redirect(url_for("index", tab="today"))
        if entry_type == "daily_goal":
            if not payload.get("goal"):
                flash("Daily goal is required.")
                return render_template(
                    f"forms/{entry_type}.html",
                    **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
                )
            if not payload.get("skills"):
                flash("Add at least one skill used for your daily goal.")
                return render_template(
                    f"forms/{entry_type}.html",
                    **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
                )
            _save_daily_goal(payload)
            flash("Daily goal saved.")
            return redirect(url_for("index", tab="today"))
        if entry_type == "daily_planner":
            if not payload.get("focus"):
                flash("How I show up is required.")
                return render_template(
                    f"forms/{entry_type}.html",
                    **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
                )
            _save_daily_planner(payload)
            flash("Today saved.")
            return redirect(url_for("index", tab="today"))
        entry = _make_entry(
            type=entry_type,
            payload=payload,
            linked_entry_id=linked_entry_id,
            secondary_tag=secondary_tag,
        )
        _save_entry(entry, entry_type)
        flash(f"{type_label(entry_type)} saved.")
        return redirect(url_for("entry_detail", entry_id=entry.id))

    if entry_type == "daily_goal":
        existing = _todays_daily_goal()
        if existing:
            return redirect(url_for("entry_edit", entry_id=existing.id))

    if entry_type == "daily_planner":
        existing = _todays_daily_planner()
        if existing:
            return redirect(url_for("entry_edit", entry_id=existing.id))

    if entry_type == "mantras":
        return redirect(url_for("mantras_hub"))

    return render_template(
        f"forms/{entry_type}.html",
        **_form_render_ctx(
            entry_type,
            {},
            is_edit=False,
            exposure_plans=_exposure_plans() if entry_type == "exposure_checkin" else [],
        ),
    )


@app.route("/mantras")
def mantras_hub():
    library = _ensure_mantras_library()
    items = mantra_library_items(library.payload)
    invoked_ids = {
        m["id"] for m in todays_invoked_mantras(
            entries_q()
            .filter_by(type="mantra_event")
            .order_by(Entry.created_at.desc())
            .all(),
            LOCAL_TZ,
        )
    }
    return render_template(
        "mantras.html",
        items=items,
        invoked_ids=invoked_ids,
    )


@app.route("/mantras/add", methods=["POST"])
def mantras_add():
    text = (request.form.get("text") or "").strip()
    journal = (request.form.get("journal") or "").strip()
    if not text:
        flash("Mantra text is required.")
        return redirect(url_for("mantras_hub"))
    library = _ensure_mantras_library()
    items = mantra_library_items(library.payload)
    mantra_id = str(uuid.uuid4())
    items.append({"id": mantra_id, "text": text})
    library.payload = {"items": items}
    _touch_entry(library)
    db.session.commit()
    event = _log_mantra_event("add", mantra_id, text, journal)
    if request.form.get("set_focus"):
        _log_mantra_event("invoke", mantra_id, text, mark_for_review=False)
        flash("Mantra added to today’s focus.")
        if request.form.get("next") == "today":
            return redirect(url_for("index", tab="today"))
        return redirect(url_for("mantras_hub"))
    flash("Mantra added.")
    return redirect(url_for("entry_detail", entry_id=event.id))


@app.route("/mantras/invoke", methods=["POST"])
def mantras_invoke():
    mantra_id = (request.form.get("mantra_id") or "").strip()
    journal = (request.form.get("journal") or "").strip()
    library = _ensure_mantras_library()
    items = mantra_library_items(library.payload)
    match = next((i for i in items if i["id"] == mantra_id), None)
    if not match:
        flash("Mantra not found.")
        return redirect(url_for("mantras_hub"))
    event = _log_mantra_event("invoke", match["id"], match["text"], journal)
    flash("Mantra set as today’s focus.")
    if request.form.get("next") == "today":
        return redirect(url_for("index", tab="today"))
    return redirect(url_for("entry_detail", entry_id=event.id))


@app.route("/mantras/edit", methods=["POST"])
def mantras_edit():
    mantra_id = (request.form.get("mantra_id") or "").strip()
    text = (request.form.get("text") or "").strip()
    journal = (request.form.get("journal") or "").strip()
    if not text:
        flash("Mantra text is required.")
        return redirect(url_for("mantras_hub"))
    library = _ensure_mantras_library()
    items = mantra_library_items(library.payload)
    match = next((i for i in items if i["id"] == mantra_id), None)
    if not match:
        flash("Mantra not found.")
        return redirect(url_for("mantras_hub"))
    match["text"] = text
    library.payload = {"items": items}
    _touch_entry(library)
    db.session.commit()
    event = _log_mantra_event("edit", match["id"], text, journal)
    flash("Mantra updated.")
    return redirect(url_for("entry_detail", entry_id=event.id))


@app.route("/mantras/delete", methods=["POST"])
def mantras_delete():
    mantra_id = (request.form.get("mantra_id") or "").strip()
    library = _ensure_mantras_library()
    items = mantra_library_items(library.payload)
    match = next((i for i in items if i["id"] == mantra_id), None)
    if not match:
        flash("Mantra not found.")
        return redirect(url_for("mantras_hub"))
    library.payload = {"items": [i for i in items if i["id"] != mantra_id]}
    _touch_entry(library)
    db.session.commit()
    event = _log_mantra_event("delete", match["id"], match["text"], "")
    flash("Mantra deleted.")
    return redirect(url_for("entry_detail", entry_id=event.id))


@app.route("/entry/<int:entry_id>/review", methods=["POST"])
def entry_toggle_review(entry_id):
    """Mantra events have no edit form; mark / unmark for review from the detail page."""
    entry = _get_entry_or_404(entry_id)
    if entry.type != "mantra_event":
        abort(404)
    entry.mark_for_review = request.form.get("mark_for_review") == "1"
    db.session.commit()
    return redirect(url_for("entry_detail", entry_id=entry.id))


@app.route("/entry/<int:entry_id>")
def entry_detail(entry_id):
    entry = _get_entry_or_404(entry_id)
    if entry.type == "mantras":
        return redirect(url_for("mantras_hub"))
    linked_plan = None
    linked_journal = None
    linked_diary_card = None
    if entry.type == "exposure_checkin" and entry.linked_entry_id:
        linked_plan = entries_q().filter_by(id=entry.linked_entry_id).first()
    if entry.type == "diary_card":
        linked_journal = linked_journal_for(entry)
    if entry.type == "journal" and entry.linked_entry_id:
        parent = entries_q().filter_by(id=entry.linked_entry_id).first()
        if parent and parent.type == "diary_card":
            linked_diary_card = parent
    needs_ba_outcome = (
        entry.type == "behavioral_activation"
        and behavioral_activation_needs_outcome(entry.payload or {})
    )
    needs_exposure_outcome = (
        entry.type == "exposure_plan"
        and exposure_needs_outcome(entry.payload or {})
    )
    needs_opposite_action_outcome = (
        entry.type == "opposite_action"
        and opposite_action_needs_outcome(entry.payload or {})
    )
    return render_template(
        "entry_detail.html",
        entry=entry,
        linked_plan=linked_plan,
        linked_journal=linked_journal,
        linked_diary_card=linked_diary_card,
        can_delete=entry_can_delete(entry),
        needs_outcome=needs_ba_outcome or needs_exposure_outcome or needs_opposite_action_outcome,
        needs_ba_outcome=needs_ba_outcome,
        needs_exposure_outcome=needs_exposure_outcome,
        needs_opposite_action_outcome=needs_opposite_action_outcome,
        summary=entry_summary(entry),
        label=entry_log_label(entry),
        ba_emotions=behavioral_activation_emotion_rows(entry.payload or {})
        if entry.type == "behavioral_activation"
        else [],
        oa_emotions=opposite_action_emotion_rows(entry.payload or {})
        if entry.type == "opposite_action"
        else [],
    )


@app.route("/entry/<int:entry_id>/outcome", methods=["POST"])
def entry_outcome(entry_id):
    entry = _get_entry_or_404(entry_id)
    p = entry.payload or {}
    if entry.type == "behavioral_activation" and behavioral_activation_needs_outcome(p):
        entry.payload = merge_behavioral_outcome(p, request.form)
    elif entry.type == "exposure_plan" and exposure_needs_outcome(p):
        entry.payload = merge_exposure_outcome(p, request.form)
    elif entry.type == "opposite_action" and opposite_action_needs_outcome(p):
        entry.payload = merge_opposite_action_outcome(p, request.form)
    else:
        abort(400)
    _touch_entry(entry)
    db.session.commit()
    _pegasus_notify(entry)
    flash("Outcome recorded.")
    return redirect(url_for("entry_detail", entry_id=entry.id))


@app.route("/entry/<int:entry_id>/delete", methods=["POST"])
def entry_delete(entry_id):
    entry = _get_entry_or_404(entry_id)
    if not entry_can_delete(entry):
        abort(400)
    kind = type_label(entry.type)
    _pegasus_notify(entry, deleted=True)
    db.session.delete(entry)
    db.session.commit()
    flash(f"{kind} deleted.")
    return redirect(url_for("index", tab="today"))


@app.route("/entry/<int:entry_id>/edit", methods=["GET", "POST"])
def entry_edit(entry_id):
    entry = _get_entry_or_404(entry_id)
    if entry.type in ("mantras", "mantra_event"):
        return redirect(url_for("mantras_hub"))

    if request.method == "POST":
        if entry.type == "behavioral_activation":
            payload = parse_behavioral_activation_plan(request.form, existing=entry.payload or {})
            linked_entry_id = entry.linked_entry_id
            secondary_tag = entry.secondary_tag
        elif entry.type == "exposure_plan":
            payload = parse_exposure_plan(request.form, existing=entry.payload or {})
            linked_entry_id = entry.linked_entry_id
            secondary_tag = entry.secondary_tag
        elif entry.type == "opposite_action":
            payload = parse_opposite_action_plan(request.form, existing=entry.payload or {})
            linked_entry_id = entry.linked_entry_id
            secondary_tag = entry.secondary_tag
        elif entry.type == "journal":
            payload = parse_journal_fields(request.form, existing=entry.payload or {})
            payload["audio_clip_ids"] = _owned_clip_ids(
                parse_id_list(request.form.get("audio_clip_ids")), entry.id
            )
            linked_entry_id = entry.linked_entry_id
            secondary_tag = entry.secondary_tag
        else:
            payload, linked_entry_id, secondary_tag = payload_for_type(entry.type, request.form)
        if entry.type == "journal" and not payload.get("text") and not payload.get("audio_clip_ids"):
            flash("Write something or record audio.")
            return render_template(
                f"forms/{entry.type}.html",
                **_form_render_ctx(
                    entry.type,
                    payload,
                    is_edit=True,
                    entry_id=entry.id,
                    exposure_plans=[],
                    linked_entry_id=entry.linked_entry_id,
                    secondary_tag=entry.secondary_tag,
                ),
            )
        if entry.type == "behavioral_activation":
            if not payload.get("activity") or not payload.get("planned_datetime"):
                flash("Activity and planned date & time are required.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
            if not behavioral_activation_has_plan(payload):
                flash("Rate current and predicted levels for joy and sadness.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
        if entry.type == "exposure_plan":
            if not payload.get("situation"):
                flash("Situation is required.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
            if not exposure_has_plan(payload):
                flash("Rate SUDS before and predicted peak SUDS.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
        if entry.type == "opposite_action":
            if not opposite_action_has_plan(payload):
                flash("Add an emotion and describe the opposite action.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
        if entry.type == "daily_goal":
            if not payload.get("goal"):
                flash("Daily goal is required.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
            if not payload.get("skills"):
                flash("Add at least one skill used for your daily goal.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
        if entry.type == "daily_planner":
            if not payload.get("focus"):
                flash("How I show up is required.")
                return render_template(
                    f"forms/{entry.type}.html",
                    **_form_render_ctx(
                        entry.type,
                        payload,
                        is_edit=True,
                        entry_id=entry.id,
                        exposure_plans=[],
                        linked_entry_id=entry.linked_entry_id,
                        secondary_tag=entry.secondary_tag,
                    ),
                )
        if entry.type == "daily_planner":
            payload = keep_legacy_diary_journal(payload, entry.payload)
        entry.payload = payload
        entry.linked_entry_id = linked_entry_id
        entry.secondary_tag = secondary_tag
        if entry.type in REVIEWABLE_TYPES:
            entry.mark_for_review = "mark_for_review" in request.form
        _touch_entry(entry)
        if entry.type == "diary_card":
            sync_diary_card_journal(entry, request.form)
        if entry.type == "journal":
            _sync_journal_audio(entry, payload.get("audio_clip_ids") or [])
        db.session.commit()
        _pegasus_notify(entry)
        flash("Entry updated.")
        if entry.type in ("daily_goal", "daily_planner"):
            return redirect(url_for("index", tab="today"))
        return redirect(url_for("entry_detail", entry_id=entry.id))

    return render_template(
        f"forms/{entry.type}.html",
        **_form_render_ctx(
            entry.type,
            entry.payload,
            entry=entry,
            is_edit=True,
            entry_id=entry.id,
            exposure_plans=_exposure_plans() if entry.type == "exposure_checkin" else [],
            linked_entry_id=entry.linked_entry_id,
            secondary_tag=entry.secondary_tag,
        ),
    )


@app.route("/history")
def history():
    return redirect(url_for("index", tab="log"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user is None or not user.is_active or not check_password(user, password):
            flash("Invalid email or password.")
            show_setup = User.query.filter(User.password_hash.is_(None)).count() > 0
            return render_template("login.html", show_setup_link=show_setup), 401
        login_user(user, remember=True)
        get_or_create_preferences(user.id)
        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("index"))
    show_setup = User.query.filter(User.password_hash.is_(None)).count() > 0
    return render_template("login.html", show_setup_link=show_setup)


@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("Signed out.")
    return redirect(url_for("login"))


@app.route("/guide")
def guide():
    return render_template("guide.html")


@app.route("/settings", methods=["GET", "POST"])
def settings():
    prefs = get_or_create_preferences()
    if request.method == "POST":
        form_kind = (request.form.get("form_kind") or "invite").strip()
        if form_kind == "display":
            prefs.show_feelings_wheel = request.form.get("show_feelings_wheel") == "1"
            prefs.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Display settings saved.")
            return redirect(url_for("settings"))

        if form_kind == "catalogs":
            diary = _parse_lines_list(request.form.get("diary_emotions_text"))
            targets = _parse_lines_list(request.form.get("target_behaviors_text"))
            if not diary:
                flash("Add at least one tracked emotion.")
                return redirect(url_for("settings"))
            prefs.diary_emotions = diary
            prefs.target_behaviors = targets
            prefs.updated_at = datetime.utcnow()
            db.session.commit()
            flash("Tracked emotions and target behaviors saved.")
            return redirect(url_for("settings"))

        invite_email = (request.form.get("invite_email") or "").strip().lower()
        if not invite_email:
            flash("Enter an email for the invite.")
            return redirect(url_for("settings"))
        if "@" not in invite_email:
            flash("Enter a valid email for the invite.")
            return redirect(url_for("settings"))
        existing_user = User.query.filter_by(email=invite_email).first()
        if existing_user is not None:
            flash("That email already has an account.")
            return redirect(url_for("settings"))
        pending = Invite.query.filter_by(
            email=invite_email, used_at=None
        ).filter(Invite.expires_at > datetime.utcnow()).first()
        if pending is not None:
            invite_url = url_for("register", token=pending.token, _external=True)
            flash(f"An invite for {invite_email} is already pending. Share this link: {invite_url}")
            return redirect(url_for("settings"))
        invite = create_invite(invite_email, uid())
        invite_url = url_for("register", token=invite.token, _external=True)
        flash(f"Invite created for {invite_email}. Share this link: {invite_url}")
        return redirect(url_for("settings"))

    pending_invites = (
        Invite.query.filter_by(created_by_user_id=uid(), used_at=None)
        .order_by(Invite.created_at.desc())
        .all()
    )
    return render_template(
        "settings.html",
        pending_invites=pending_invites,
        show_feelings_wheel=bool(prefs.show_feelings_wheel),
        diary_emotions_text="\n".join(prefs.diary_emotions or []),
        target_behaviors_text="\n".join(prefs.target_behaviors or []),
    )


@app.route("/demo/reset", methods=["POST"])
def demo_reset():
    """Blank-slate the separate demo DB. Never available outside demo mode."""
    if not _is_demo:
        abort(404)
    user = _reset_demo_database()
    logout_user()
    login_user(user, remember=True)
    flash("Demo reset. Blank slate ready.")
    return render_template("demo_reset.html")


def _parse_lines_list(raw: str | None) -> list[str]:
    seen = set()
    out = []
    for line in (raw or "").splitlines():
        name = line.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


@app.route("/settings/invite/<int:invite_id>/cancel", methods=["POST"])
def cancel_invite_route(invite_id: int):
    inv = cancel_invite(invite_id, uid())
    if inv is None:
        flash("Invite not found or already used.")
    else:
        flash(f"Invite cancelled for {inv.email}.")
    return redirect(url_for("settings"))


@app.route("/register/<token>", methods=["GET", "POST"])
def register(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    invite = validate_invite_token(token)
    if invite is None:
        flash("This invite link is invalid or expired.")
        return redirect(url_for("login"))
    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("password_confirm") or ""
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("register.html", token=token, invite_email=invite.email), 400
        if password != confirm:
            flash("Passwords do not match.")
            return render_template("register.html", token=token, invite_email=invite.email), 400
        existing = User.query.filter_by(email=invite.email).first()
        if existing is not None:
            flash("An account with this email already exists. Sign in instead.")
            return redirect(url_for("login"))
        user = User(email=invite.email, is_active=True)
        set_password(user, password)
        db.session.add(user)
        invite.used_at = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=True)
        get_or_create_preferences(user.id)
        flash("Account created.")
        return redirect(url_for("index"))
    return render_template("register.html", token=token, invite_email=invite.email)


@app.route("/setup-password", methods=["GET", "POST"])
def setup_password():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("password_confirm") or ""
        user = User.query.filter_by(email=email).first()
        if user is None or not user.is_active:
            flash("No account found for that email.")
            return render_template("setup_password.html"), 400
        if user.password_hash:
            flash("This account already has a password. Sign in instead.")
            return redirect(url_for("login"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("setup_password.html"), 400
        if password != confirm:
            flash("Passwords do not match.")
            return render_template("setup_password.html"), 400
        set_password(user, password)
        db.session.commit()
        login_user(user, remember=True)
        get_or_create_preferences(user.id)
        flash("Password saved.")
        return redirect(url_for("index"))
    return render_template("setup_password.html")


def _prefs_payload(prefs: UserPreference) -> dict:
    return {
        "saved_emotions": prefs.saved_emotions or [],
        "saved_skills": prefs.saved_skills or [],
        "target_behaviors": prefs.target_behaviors or [],
        "diary_emotions": prefs.diary_emotions or [],
        "show_feelings_wheel": bool(prefs.show_feelings_wheel),
    }


@app.route("/api/preferences", methods=["GET"])
def api_preferences_get():
    prefs = get_or_create_preferences()
    return jsonify(_prefs_payload(prefs))


@app.route("/api/preferences/<kind>", methods=["PUT"])
def api_preferences_put(kind):
    if kind not in (
        "saved_emotions",
        "saved_skills",
        "target_behaviors",
        "diary_emotions",
    ):
        abort(404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "items" not in data:
        abort(400)
    items = data.get("items")
    if not isinstance(items, list):
        abort(400)
    cleaned = []
    seen = set()
    for item in items:
        if kind == "saved_skills":
            if not isinstance(item, dict):
                continue
            mod = (item.get("module") or "").strip()
            skill = (item.get("skill") or "").strip()
            if not mod or not skill:
                continue
            key = (mod.lower(), skill.lower())
            if key in seen:
                continue
            seen.add(key)
            cleaned.append({"module": mod, "skill": skill})
        else:
            name = (item if isinstance(item, str) else (item.get("name") if isinstance(item, dict) else "") or "")
            name = str(name).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(name)
    if kind == "diary_emotions" and not cleaned:
        abort(400)
    prefs = get_or_create_preferences()
    setattr(prefs, kind, cleaned)
    prefs.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "items": getattr(prefs, kind) or []})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    if _is_demo:
        print("Running in DEMO mode (database: instance/demo_ledger.db)")
        print(f"  Sign in: {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")
        print("  Reset blank slate: python app.py demo clear")
        print("  Or: python scripts/demo_user.py reset")
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
