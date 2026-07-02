"""Resolve DATABASE_URL with optional automatic SQLite fallback when MySQL/XAMPP is down."""

from __future__ import annotations

import importlib.util
import os
from typing import Tuple
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError


def _api_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_sqlite_uri() -> str:
    """Absolute SQLite URI under api_base/instance/translation.db."""
    instance_dir = os.path.join(_api_base_dir(), "instance")
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, "translation.db").replace("\\", "/")
    return f"sqlite:///{db_path}"


def mask_db_uri(db_uri: str) -> str:
    if not db_uri:
        return ""
    try:
        parsed = urlsplit(db_uri)
        if not parsed.scheme:
            return db_uri
        netloc = parsed.netloc
        if "@" in netloc:
            creds, host = netloc.rsplit("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                netloc = f"{user}:***@{host}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        return db_uri


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _is_azure_host() -> bool:
    return bool(os.getenv("WEBSITE_SITE_NAME") or os.getenv("WEBSITES_PORT"))


def _connect_timeout_seconds() -> int:
    default = "3" if _is_azure_host() else "8"
    try:
        return int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", default) or default)
    except Exception:
        return 3 if _is_azure_host() else 8


def mysql_engine_options(timeout: int | None = None) -> dict:
    timeout = timeout if timeout is not None else _connect_timeout_seconds()
    return {
        "pool_pre_ping": True,
        "connect_args": {
            "connect_timeout": timeout,
            "read_timeout": timeout,
            "write_timeout": timeout,
        },
    }


def sqlite_engine_options() -> dict:
    return {"pool_pre_ping": True}


def engine_options_for_uri(db_uri: str) -> dict:
    if (db_uri or "").startswith("mysql+pymysql://"):
        return mysql_engine_options()
    return sqlite_engine_options()


def test_mysql_connection(mysql_uri: str, timeout: int | None = None) -> bool:
    if not (mysql_uri or "").startswith("mysql+pymysql://"):
        return False
    if importlib.util.find_spec("pymysql") is None:
        return False
    timeout = timeout if timeout is not None else _connect_timeout_seconds()
    engine = create_engine(
        mysql_uri,
        echo=False,
        **mysql_engine_options(timeout),
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (OperationalError, SQLAlchemyError, Exception):
        return False
    finally:
        engine.dispose()


def resolve_database_uri() -> Tuple[str, bool]:
    """
    Pick the active database URI.

    Returns (uri, used_sqlite_fallback).
    """
    try:
        requested = os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://root:@localhost:3306/ai_translation",
        ).strip()

        if requested.startswith("sqlite"):
            return requested, False

        if _env_truthy("DB_FORCE_SQLITE"):
            sqlite_uri = os.getenv("SQLITE_DATABASE_URL", "").strip() or default_sqlite_uri()
            print("[db] DB_FORCE_SQLITE=1 — using SQLite.")
            print(f"[db] SQLite path: {mask_db_uri(sqlite_uri)}")
            return sqlite_uri, True

        if _env_truthy("DB_DISABLE_SQLITE_FALLBACK"):
            return requested, False

        if requested.startswith("mysql+pymysql://"):
            if importlib.util.find_spec("pymysql") is None:
                sqlite_uri = os.getenv("SQLITE_DATABASE_URL", "").strip() or default_sqlite_uri()
                print("\n[WARN] DATABASE_URL uses mysql+pymysql but PyMySQL is missing — using SQLite.")
                print(f"[db] Fallback:  {mask_db_uri(sqlite_uri)}")
                return sqlite_uri, True

            if test_mysql_connection(requested):
                return requested, False

            sqlite_uri = os.getenv("SQLITE_DATABASE_URL", "").strip() or default_sqlite_uri()
            print("\n[WARN] MySQL/XAMPP is unavailable — switching to SQLite fallback.")
            print(f"[db] Requested: {mask_db_uri(requested)}")
            print(f"[db] Fallback:  {mask_db_uri(sqlite_uri)}")
            print("[db] Start XAMPP MySQL and set DATABASE_URL to use MySQL again.")
            print("[db] To disable auto-fallback: DB_DISABLE_SQLITE_FALLBACK=1\n")
            return sqlite_uri, True

        return requested, False
    except Exception as exc:
        sqlite_uri = os.getenv("SQLITE_DATABASE_URL", "").strip() or default_sqlite_uri()
        print(f"\n[WARN] Database URI resolution failed ({exc}) — using SQLite.")
        print(f"[db] Fallback:  {mask_db_uri(sqlite_uri)}")
        return sqlite_uri, True
