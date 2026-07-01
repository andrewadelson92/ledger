"""Environment-based configuration for local dev and production."""
import os

_APP_ROOT = os.path.dirname(os.path.abspath(__file__))


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def load_config(app) -> None:
    env = (
        os.getenv("LEDGER_ENV")
        or os.getenv("FLASK_ENV")
        or "development"
    ).strip().lower()
    app.config["LEDGER_ENV"] = env
    app.config["DEBUG"] = env not in ("production", "prod")
    is_prod = env in ("production", "prod")

    secret = os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY")
    if secret:
        app.config["SECRET_KEY"] = secret
    elif is_prod:
        raise RuntimeError("SECRET_KEY must be set in production")
    else:
        app.config["SECRET_KEY"] = "dev"

    db_uri = os.getenv("LEDGER_DATABASE_URI") or os.getenv("DATABASE_URL")
    db_path = os.getenv("LEDGER_DB_PATH")
    if db_uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_database_url(db_uri)
    elif is_prod:
        raise RuntimeError(
            "DATABASE_URL must be set in production. "
            "Link Postgres on the web service (Variables → reference Postgres.DATABASE_URL)."
        )
    elif db_path:
        p = os.path.expanduser(db_path)
        if not os.path.isabs(p):
            p = os.path.join(_APP_ROOT, p)
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{p}"
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(_APP_ROOT, 'ledger.db')}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
