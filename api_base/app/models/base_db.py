#!/usr/bin/env python3
"""
DB setup script: MySQL (XAMPP) with automatic SQLite fallback.
Ensures the database and tables exist (creates them if missing).
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add api_base directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

# Load .env
# IMPORTANT: In Docker, environment variables should win.
# Set DOTENV_OVERRIDE=1 only if you explicitly want .env to override existing env vars.
_override = (os.getenv('DOTENV_OVERRIDE') or '').strip().lower() in ('1', 'true', 'yes', 'on')
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'), override=_override)

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.db_bootstrap import default_sqlite_uri, mask_db_uri, resolve_database_uri, test_mysql_connection


def check_and_create_mysql_db():
    """Kiểm tra và tạo database MySQL (chỉ khi URI là MySQL)."""
    mysql_url = os.getenv('DATABASE_URL', 'mysql+pymysql://root:@localhost:3306/ai_translation')

    if not mysql_url.startswith('mysql+pymysql://'):
        print(f"ℹ️  DATABASE_URL is not MySQL — skip MySQL server setup.")
        print(f"   Active URI: {mask_db_uri(mysql_url)}")
        return True

    parsed = urlparse(mysql_url)
    user = parsed.username or 'root'
    password = parsed.password or ''
    host = parsed.hostname or 'localhost'
    port = parsed.port or 3306
    db_name = parsed.path.lstrip('/') or 'ai_translation'

    print("🔍 Checking MySQL connection...")
    print(f"   Host: {host}:{port}")
    print(f"   User: {user}")
    print(f"   Database: {db_name}")

    if not test_mysql_connection(mysql_url):
        sqlite_uri = default_sqlite_uri()
        print(f"❌ MySQL connection failed.")
        print("   Make sure XAMPP MySQL is running on localhost:3306")
        print(f"   Falling back to SQLite: {mask_db_uri(sqlite_uri)}")
        os.environ['DATABASE_URL'] = sqlite_uri
        return True

    try:
        server_engine = create_engine(
            f"mysql+pymysql://{user}:{password}@{host}:{port}/",
            echo=False
        )
        with server_engine.connect() as conn:
            result = conn.execute(text(f"SHOW DATABASES LIKE '{db_name}'"))
            if not result.fetchone():
                print(f"📝 Creating database '{db_name}'...")
                conn.execute(text(f"CREATE DATABASE {db_name} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                conn.commit()
                print(f"✅ Database '{db_name}' created")
            else:
                print(f"✅ Database '{db_name}' already exists")
        return True
    except OperationalError as e:
        sqlite_uri = default_sqlite_uri()
        print(f"❌ MySQL connection failed: {e}")
        print(f"   Falling back to SQLite: {mask_db_uri(sqlite_uri)}")
        os.environ['DATABASE_URL'] = sqlite_uri
        return True


def create_tables():
    """Tạo bảng (MySQL hoặc SQLite)."""
    print("\n📦 Creating tables...")
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            from app.models import db
            from app.db_migrations import run_schema_migrations
            db.create_all()
            run_schema_migrations(db)
            print("✅ Tables created successfully")
            print(f"   Database: {mask_db_uri(app.config.get('SQLALCHEMY_DATABASE_URI') or '')}")
        return True
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False


def check_only() -> bool:
    """Chỉ kiểm tra kết nối database, không tạo bảng."""
    print("=" * 60)
    print("Database connection check")
    print("=" * 60)

    active_uri, used_fallback = resolve_database_uri()
    print(f"   Active URI: {mask_db_uri(active_uri)}")
    if used_fallback:
        print("   Note: MySQL unavailable — app would use SQLite fallback.")

    if active_uri.startswith("mysql+pymysql://"):
        if test_mysql_connection(active_uri):
            print("[OK] MySQL connection")
            return True
        print("[FAIL] MySQL connection")
        print("   Start MySQL (XAMPP) and verify DATABASE_URL in api_base/.env")
        return False

    print("[OK] SQLite URI resolved")
    return True


def main():
    print("=" * 60)
    print("🚀 Database setup (MySQL / SQLite fallback)")
    print("=" * 60)

    active_uri, used_fallback = resolve_database_uri()
    if used_fallback:
        os.environ['DATABASE_URL'] = active_uri

    if active_uri.startswith('mysql+pymysql://'):
        if not check_and_create_mysql_db():
            return False
    else:
        print(f"✅ Using SQLite: {mask_db_uri(active_uri)}")

    if not create_tables():
        return False

    print("\n" + "=" * 60)
    print("✨ Database and tables are ready!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run: python run_api.py")
    _bp = int(os.getenv("BACKEND_PORT", "5055") or 5055)
    print(f"  2. Access: http://127.0.0.1:{_bp}")
    if active_uri.startswith('mysql+pymysql://'):
        print("  3. Check MySQL: SHOW TABLES IN ai_translation;")
    else:
        print("  3. SQLite file: api_base/instance/translation.db")

    return True


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        success = check_only()
    else:
        success = main()
    sys.exit(0 if success else 1)
