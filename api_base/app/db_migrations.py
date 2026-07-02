"""Cross-dialect schema migrations (MySQL + SQLite)."""

from __future__ import annotations

from sqlalchemy import inspect, text


def _column_exists(db, table: str, column: str) -> bool:
    try:
        insp = inspect(db.engine)
        if table not in insp.get_table_names():
            return False
        return any(col.get("name") == column for col in insp.get_columns(table))
    except Exception:
        return False


def run_schema_migrations(db) -> None:
    """Add columns introduced after initial deploy (safe to run repeatedly)."""
    migrations = [
        ("user", "role", "ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"),
        ("user", "avatar_url", "ALTER TABLE user ADD COLUMN avatar_url VARCHAR(500)"),
        ("user", "token_balance", "ALTER TABLE user ADD COLUMN token_balance INT NOT NULL DEFAULT 5000"),
        ("user", "password_hash", "ALTER TABLE user ADD COLUMN password_hash VARCHAR(255)"),
        ("translation", "type", "ALTER TABLE translation ADD COLUMN type VARCHAR(20) NOT NULL DEFAULT 'text'"),
        ("translation", "token_cost", "ALTER TABLE translation ADD COLUMN token_cost INT NOT NULL DEFAULT 0"),
        ("payment", "plan_type", "ALTER TABLE payment ADD COLUMN plan_type VARCHAR(50)"),
        ("contact_message", "admin_reply", "ALTER TABLE contact_message ADD COLUMN admin_reply TEXT"),
        ("contact_message", "replied_at", "ALTER TABLE contact_message ADD COLUMN replied_at DATETIME"),
        ("user", "username", "ALTER TABLE user ADD COLUMN username VARCHAR(50)"),
        ("user", "email_verified", "ALTER TABLE user ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 1"),
        ("user", "account_status", "ALTER TABLE user ADD COLUMN account_status VARCHAR(20) NOT NULL DEFAULT 'active'"),
        ("user", "delete_requested_at", "ALTER TABLE user ADD COLUMN delete_requested_at DATETIME"),
        ("user", "delete_scheduled_at", "ALTER TABLE user ADD COLUMN delete_scheduled_at DATETIME"),
        ("user", "delete_reason", "ALTER TABLE user ADD COLUMN delete_reason TEXT"),
        ("user", "delete_otp", "ALTER TABLE user ADD COLUMN delete_otp VARCHAR(255)"),
        ("user", "delete_otp_expires_at", "ALTER TABLE user ADD COLUMN delete_otp_expires_at DATETIME"),
        ("user", "delete_otp_verified", "ALTER TABLE user ADD COLUMN delete_otp_verified TINYINT(1) NOT NULL DEFAULT 0"),
        ("user", "delete_otp_wrong_attempts", "ALTER TABLE user ADD COLUMN delete_otp_wrong_attempts INT NOT NULL DEFAULT 0"),
        ("user", "delete_otp_locked_until", "ALTER TABLE user ADD COLUMN delete_otp_locked_until DATETIME"),
        ("user", "delete_cancelled_at", "ALTER TABLE user ADD COLUMN delete_cancelled_at DATETIME"),
        ("user", "deleted_at", "ALTER TABLE user ADD COLUMN deleted_at DATETIME"),
    ]

    dialect = db.engine.dialect.name
    with db.engine.begin() as conn:
        for table, column, ddl in migrations:
            if _column_exists(db, table, column):
                continue
            try:
                conn.execute(text(ddl))
                print(f"[migration] Added column '{column}' to '{table}' ({dialect})")
            except Exception as exc:
                print(f"[migration] Skip '{table}.{column}': {exc}")

        # Add unique index for username separately (SQLite doesn't support ADD COLUMN UNIQUE)
        try:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_username ON user(username)"
            ))
        except Exception:
            pass
