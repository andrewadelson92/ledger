# Ledger

A personal DBT/CBT skills practice log — a calm, minimal companion to [Long Track](https://github.com/andrewadelson92/long_track). Log emotions, skills, diary cards, thought records, behavioral activation, exposure work, chain analyses, and journal entries in one place.

Multi-user with email login. Entries and preference catalogs (custom skills, emotions, target behaviors) are scoped per user in the database. Existing local data is backfilled to the owner account on migration.

Grayscale UI. Runs on Flask + SQLite locally or PostgreSQL on Railway.

## Entry types

| Type | Description |
|------|-------------|
| Emotion Check-In | Quick emotion + intensity log |
| Today | Focus, diary card, noted emotions, optional agenda |
| Diary Card | Legacy; diary is now part of Today |
| Skill Used | DBT module + skill |
| Thought Record | Before/after emotions with reframing fields |
| Mantras | Add, set as today’s focus, or delete; each action is logged |
| Opposite Action | Emotion + urge, fit-the-facts check, opposite action, before/after emotions |
| ABC Worksheet | Activating event, belief, consequence |
| Behavioral Activation | Two-step: plan joy/sadness levels → complete after activity |
| Chain Analysis | Problem behavior chain with typed links |
| Exposure | Two-step: SUDS before + predicted peak → complete after exposure |
| Journal | Free-form text and/or microphone recordings (stored in the database) |

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional
python app.py
```

Open [http://127.0.0.1:5002](http://127.0.0.1:5002). First visit: set a password for the owner email (default `andrew.adelson92@gmail.com`, override with `LEDGER_OWNER_EMAIL`).

Migrations run automatically on startup (SQLite). For manual migration commands:

```bash
flask db upgrade
```

### Demo mode (blank slate, separate DB)

```bash
source .venv/bin/activate
python app.py demo          # uses instance/demo_ledger.db
# first-time / hard wipe from the terminal:
python app.py demo clear
```

Open [http://127.0.0.1:5002](http://127.0.0.1:5002). Sign in as `demo@localhost` / `demopass123`.

Between walkthroughs: **Settings → Reset demo** (demo mode only). That wipes demo entries/invites/prefs, restores the blank demo user, and clears browser picker cache. Your personal `ledger.db` is never touched.

### Inviting users

Any signed-in user can open **Settings** → enter an email → **Create invite link**. Share the `/register/<token>` URL; the invitee sets their own password (7-day expiry). No email is sent automatically.

## Environment variables

| Variable | Description |
|----------|-------------|
| `LEDGER_ENV` | `development` (default) or `production` |
| `SECRET_KEY` | Required in production |
| `DATABASE_URL` | PostgreSQL URL in production (Railway) |
| `LEDGER_DB_PATH` | SQLite path override for local dev |
| `LEDGER_OWNER_EMAIL` | Owner email for migration backfill (default `andrew.adelson92@gmail.com`; **required in production**) |
| `PORT` | HTTP port (default `5002` for `python app.py`, `8080` for gunicorn) |
| `PEGASUS_TOKEN` | Shared secret with Long Track (Pegasus bridge). Unset = bridge off |
| `LONG_TRACK_URL` | Long Track base URL; Ledger sends completed moments here |
| `LEDGER_PUBLIC_URL` | Optional public base URL for links sent to Long Track (falls back to the request host) |

See `.env.example` for a starter template.

## Pegasus bridge (Long Track)

Ledger reports facts; Long Track decides what they mean. Full design: Long Track's `docs/pegasus.md`.

- `GET /api/pegasus/entries?email&start&end&include_journal` — token-auth (`Authorization: Bearer $PEGASUS_TOKEN`), feeds Long Track's therapy export. Journal text only when `include_journal=1`.
- On save / edit / outcome / delete of completion-shaped entries (diary card in the daily planner, emotion check-in, skills, opposite action, behavioral activation, exposure, thought record, ABC, chain analysis), Ledger POSTs an occurrence to Long Track (`pegasus.send_occurrence`, 3s timeout, best effort — never blocks a save). The reply is stored on `Entry.pegasus_status` and shown on the entry page.
- **Mark for review** (`Entry.mark_for_review`) lists an entry first in the Pegasus export.
- Test: `PEGASUS_TOKEN=t LEDGER_DB_PATH=/tmp/ledger_pegasus_test.db .venv/bin/python scripts/test_pegasus.py`

## Deploy on Railway

Same pattern as Long Track:

1. Push this repo to GitHub.
2. Create a new Railway project from the repo.
3. Add a **PostgreSQL** plugin and link `DATABASE_URL` to the web service.
4. Set `LEDGER_ENV=production`, `SECRET_KEY`, and `LEDGER_OWNER_EMAIL` on the web service.
5. Railway uses the `Procfile` (`gunicorn app:app`) and `railway.toml` (runs `flask db upgrade` before deploy).

Health check: `GET /health`

## Logo & icons

Source mark: `static/icons/ledger-mark.svg` (green L on black, Long Track proportions).

Regenerate PNGs and favicon after editing the SVG:

```bash
pip install cairosvg pillow
python scripts/generate_icons.py
```

## Project layout

```
app.py              Flask routes + preferences API
auth.py             Flask-Login, invites, password helpers
config.py           Environment config
models.py           User, Invite, UserPreference, Entry
helpers.py          Form parsing, summaries, workflow helpers
constants.py        Entry types, emotion wheel, skills lookup
templates/          Jinja templates + macros
static/             Logo, icons, favicon, ledger_prefs.js
migrations/         Alembic migrations
scripts/demo_user.py  Reset demo blank-slate user
```
