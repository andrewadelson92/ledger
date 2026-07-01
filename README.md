# Ledger

A personal DBT/CBT skills practice log — a calm, minimal companion to [Long Track](https://github.com/andrewadelson92/long_track). Log emotions, skills, diary cards, thought records, behavioral activation, exposure work, chain analyses, and journal entries in one place.

Single-user, no auth. Grayscale UI. Runs on Flask + SQLite locally or PostgreSQL on Railway.

## Entry types

| Type | Description |
|------|-------------|
| Emotion Check-In | Quick emotion + intensity log |
| Diary Card | Fixed emotions, target behavior urges, optional linked journal |
| Skill Used | DBT module + skill |
| Thought Record | Before/after emotions with reframing fields |
| ABC Worksheet | Activating event, belief, consequence |
| Behavioral Activation | Two-step: plan joy/sadness levels → complete after activity |
| Chain Analysis | Problem behavior chain with typed links |
| Exposure | Two-step: SUDS before + predicted peak → complete after exposure |
| Journal | Free-form title + entry |

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional
python app.py
```

Open [http://127.0.0.1:5002](http://127.0.0.1:5002).

Migrations run automatically on startup (SQLite). For manual migration commands:

```bash
flask db upgrade
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `LEDGER_ENV` | `development` (default) or `production` |
| `SECRET_KEY` | Required in production |
| `DATABASE_URL` | PostgreSQL URL in production (Railway) |
| `LEDGER_DB_PATH` | SQLite path override for local dev |
| `PORT` | HTTP port (default `5002` for `python app.py`, `8080` for gunicorn) |

See `.env.example` for a starter template.

## Deploy on Railway

Same pattern as Long Track:

1. Push this repo to GitHub.
2. Create a new Railway project from the repo.
3. Add a **PostgreSQL** plugin and link `DATABASE_URL` to the web service.
4. Set `LEDGER_ENV=production` and `SECRET_KEY` on the web service.
5. Railway uses the `Procfile` (`gunicorn app:app`).

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
app.py              Flask routes
config.py           Environment config
models.py           Entry model (polymorphic JSON payloads)
helpers.py          Form parsing, summaries, workflow helpers
constants.py        Entry types, emotion wheel, skills lookup
templates/          Jinja templates + macros
static/             Logo, icons, favicon
migrations/         Alembic migrations
```
