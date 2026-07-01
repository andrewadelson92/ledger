from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import sys

from db import db
from config import load_config
from models import Entry
from constants import (
    ENTRY_TYPES,
    ENTRY_TYPE_LABELS,
    HOME_ADD_LABELS,
    MODULE_SKILLS,
    SKILL_MODULE_LABELS,
    EMOTION_WHEEL,
    BEHAVIORAL_ACTIVATION_EMOTIONS,
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
    parse_exposure_plan,
    merge_exposure_outcome,
    entry_in_progress_can_delete,
    linked_journal_for,
    sync_diary_card_journal,
    parse_journal_fields,
)

ADD_HIDDEN_TYPES = frozenset({"exposure_checkin"})

_app_root = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
load_config(app)
db.init_app(app)

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
    return {
        "entry_type_labels": ENTRY_TYPE_LABELS,
        "skill_module_labels": SKILL_MODULE_LABELS,
        "module_skills": MODULE_SKILLS,
        "emotion_wheel": EMOTION_WHEEL,
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


with app.app_context():
    if not _running_flask_db_command():
        _bootstrap_database()


@app.route("/")
def index():
    tab = request.args.get("tab", "add").strip().lower()
    if tab not in ("log", "add"):
        tab = "add"

    entries = Entry.query.order_by(Entry.created_at.desc()).all()
    cards = [
        {
            "entry": e,
            "label": entry_log_label(e),
        }
        for e in entries
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
    add_options = [
        {"type": t, "label": HOME_ADD_LABELS.get(t, ENTRY_TYPE_LABELS[t])}
        for t in ENTRY_TYPES
        if t not in ADD_HIDDEN_TYPES
    ]
    return render_template(
        "index.html",
        cards=cards,
        tab=tab,
        add_options=add_options,
        in_progress_items=in_progress_items,
    )


def _get_entry_or_404(entry_id: int) -> Entry:
    entry = Entry.query.get(entry_id)
    if not entry:
        abort(404)
    return entry


def _touch_entry(entry: Entry) -> None:
    entry.updated_at = datetime.utcnow()


def _exposure_plans():
    return Entry.query.filter_by(type="exposure_plan").order_by(Entry.created_at.desc()).all()


def _form_render_ctx(entry_type: str, payload: dict | None, entry=None, form=None, **extra):
    ctx = {
        "entry_type": entry_type,
        "entry_label": type_label(entry_type),
        "payload": payload or {},
        **extra,
    }
    if entry_type == "diary_card":
        ctx["extra_emotions"] = diary_card_extra_emotions(ctx["payload"].get("emotions"))
        if form is not None:
            ctx["journal_payload"] = {"text": parse_journal_fields(form).get("text", "")}
        elif entry is not None:
            linked = linked_journal_for(entry)
            journal_payload = dict(linked.payload) if linked and linked.payload else {}
            ctx["journal_payload"] = {"text": journal_payload.get("text", "")}
        else:
            ctx["journal_payload"] = {}
    return ctx


def _save_entry(entry: Entry, entry_type: str | None = None) -> None:
    db.session.add(entry)
    if (entry_type or entry.type) == "diary_card":
        db.session.flush()
        sync_diary_card_journal(entry, request.form)
    db.session.commit()


@app.route("/health")
def health():
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    db_kind = "postgres" if uri.startswith("postgresql") else "sqlite"
    return jsonify({"ok": True, "db": db_kind})


@app.route("/new")
def new_picker():
    return redirect(url_for("index", tab="add"))


@app.route("/new/<entry_type>", methods=["GET", "POST"])
def new_entry(entry_type):
    if entry_type not in ENTRY_TYPES or entry_type in ADD_HIDDEN_TYPES:
        abort(404)

    if request.method == "POST":
        payload, linked_entry_id, secondary_tag = payload_for_type(entry_type, request.form)
        if entry_type == "journal" and not payload.get("text"):
            flash("Journal text is required.")
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
                entry = Entry(
                    type=entry_type,
                    payload=payload,
                    linked_entry_id=linked_entry_id,
                    secondary_tag=secondary_tag,
                )
                db.session.add(entry)
                db.session.commit()
                flash("Behavioral activation in progress.")
                return redirect(url_for("index", tab="add"))
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
                entry = Entry(
                    type=entry_type,
                    payload=payload,
                    linked_entry_id=linked_entry_id,
                    secondary_tag=secondary_tag,
                )
                db.session.add(entry)
                db.session.commit()
                flash("Exposure in progress.")
                return redirect(url_for("index", tab="add"))
            return render_template(
                f"forms/{entry_type}.html",
                **_form_render_ctx(entry_type, payload, is_edit=False, exposure_plans=[]),
            )
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
        entry = Entry(
            type=entry_type,
            payload=payload,
            linked_entry_id=linked_entry_id,
            secondary_tag=secondary_tag,
        )
        _save_entry(entry, entry_type)
        flash(f"{type_label(entry_type)} saved.")
        return redirect(url_for("entry_detail", entry_id=entry.id))

    return render_template(
        f"forms/{entry_type}.html",
        **_form_render_ctx(
            entry_type,
            {},
            is_edit=False,
            exposure_plans=_exposure_plans() if entry_type == "exposure_checkin" else [],
        ),
    )


@app.route("/entry/<int:entry_id>")
def entry_detail(entry_id):
    entry = _get_entry_or_404(entry_id)
    linked_plan = None
    linked_journal = None
    linked_diary_card = None
    if entry.type == "exposure_checkin" and entry.linked_entry_id:
        linked_plan = Entry.query.get(entry.linked_entry_id)
    if entry.type == "diary_card":
        linked_journal = linked_journal_for(entry)
    if entry.type == "journal" and entry.linked_entry_id:
        parent = Entry.query.get(entry.linked_entry_id)
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
    return render_template(
        "entry_detail.html",
        entry=entry,
        linked_plan=linked_plan,
        linked_journal=linked_journal,
        linked_diary_card=linked_diary_card,
        needs_outcome=needs_ba_outcome or needs_exposure_outcome,
        needs_ba_outcome=needs_ba_outcome,
        needs_exposure_outcome=needs_exposure_outcome,
        summary=entry_summary(entry),
        label=type_label(entry.type),
        ba_emotions=behavioral_activation_emotion_rows(entry.payload or {})
        if entry.type == "behavioral_activation"
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
    else:
        abort(400)
    _touch_entry(entry)
    db.session.commit()
    flash("Outcome recorded.")
    return redirect(url_for("entry_detail", entry_id=entry.id))


@app.route("/entry/<int:entry_id>/delete", methods=["POST"])
def entry_delete(entry_id):
    entry = _get_entry_or_404(entry_id)
    if not entry_in_progress_can_delete(entry):
        abort(400)
    kind = type_label(entry.type)
    db.session.delete(entry)
    db.session.commit()
    flash(f"{kind} deleted.")
    return redirect(url_for("index", tab="add"))


@app.route("/entry/<int:entry_id>/edit", methods=["GET", "POST"])
def entry_edit(entry_id):
    entry = _get_entry_or_404(entry_id)

    if request.method == "POST":
        if entry.type == "behavioral_activation":
            payload = parse_behavioral_activation_plan(request.form, existing=entry.payload or {})
            linked_entry_id = entry.linked_entry_id
            secondary_tag = entry.secondary_tag
        elif entry.type == "exposure_plan":
            payload = parse_exposure_plan(request.form, existing=entry.payload or {})
            linked_entry_id = entry.linked_entry_id
            secondary_tag = entry.secondary_tag
        elif entry.type == "journal":
            payload = parse_journal_fields(request.form, existing=entry.payload or {})
            linked_entry_id = entry.linked_entry_id
            secondary_tag = entry.secondary_tag
        else:
            payload, linked_entry_id, secondary_tag = payload_for_type(entry.type, request.form)
        if entry.type == "journal" and not payload.get("text"):
            flash("Journal text is required.")
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
        entry.payload = payload
        entry.linked_entry_id = linked_entry_id
        entry.secondary_tag = secondary_tag
        _touch_entry(entry)
        if entry.type == "diary_card":
            sync_diary_card_journal(entry, request.form)
        db.session.commit()
        flash("Entry updated.")
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
