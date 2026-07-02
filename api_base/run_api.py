import logging
import os
import sys
import importlib.util
import socket
import threading
import webbrowser
import warnings
from dotenv import load_dotenv

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
# Show DEBUG logs from payment service so reconcile details are visible
logging.getLogger("app.services.payment_service").setLevel(logging.DEBUG)
# ────────────────────────────────────────────────────────────────────────────

# Some global environments install chardet>=6, which triggers a noisy
# requests compatibility warning even when runtime still works.
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 .* doesn't match a supported version!",
    category=Warning,
    module=r"requests(\..*)?",
)

# Load .env từ thư mục api_base (nơi có run_api.py) – bắt buộc trước khi import config hoặc TranslationService
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
# IMPORTANT: In Docker, environment variables should win (DATABASE_URL, etc).
# Set DOTENV_OVERRIDE=1 only if you explicitly want backend/.env to override existing env vars.
_override = (os.getenv('DOTENV_OVERRIDE') or '').strip().lower() in ('1', 'true', 'yes', 'on')
load_dotenv(_env_path, override=_override)

_api_dir = os.path.dirname(os.path.abspath(__file__))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from deps_bootstrap import bootstrap_runtime_dependencies, ensure_packages_on_path, has_pdf2docx

ensure_packages_on_path()
_deps_status = bootstrap_runtime_dependencies(install_if_missing=True)

# Azure App Service exposes WEBSITES_PORT; reuse for Flask when BACKEND_PORT unset.
if not os.getenv('BACKEND_PORT') and os.getenv('WEBSITES_PORT'):
    os.environ['BACKEND_PORT'] = os.environ['WEBSITES_PORT']

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from app.routers.auth import auth_bp
from app.routers.translation import translation_bp
from app.routers.payment import payment_bp
from app.routers.history import history_bp
from app.routers.ai import ai_bp
from app.routers.admin import admin_bp
from app.routers.contact import contact_bp
from app.routers.public import public_bp

# Đường dẫn tới thư mục frontend
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
PAGES_DIR = os.path.join(FRONTEND_DIR, 'pages')
STATIC_DIR = FRONTEND_DIR

app = Flask(__name__, static_folder=os.path.join(FRONTEND_DIR, ''))
CORS(app)

# Dev: avoid stale browser cache for JS/CSS during frequent edits
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Configure session for OAuth flow
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Load config
app.config.from_object('app.config.DevelopmentConfig')


from app.db_bootstrap import mask_db_uri

# Preflight: if still on MySQL after bootstrap, ensure PyMySQL is installed.
_db_uri = (app.config.get('SQLALCHEMY_DATABASE_URI') or '').lower()
if 'mysql+pymysql://' in _db_uri and importlib.util.find_spec('pymysql') is None:
    print("\n[ERROR] Missing dependency: 'pymysql' (PyMySQL).")
    print("Your DATABASE_URL uses 'mysql+pymysql://', but PyMySQL is not installed.")
    print("\nFix (run in the SAME interpreter you're using to start the app):")
    print("  python -m pip install PyMySQL")
    print("  # or let the app use SQLite when MySQL/XAMPP is down (default fallback)")
    raise SystemExit(1)

if not has_pdf2docx():
    print("\n[WARN] pdf2docx is not installed — PDF -> DOCX translation will fail.")
    print("Install with: python -m pip install pdf2docx==0.5.7")
    if _deps_status.get("install_error"):
        print(f"[WARN] Azure auto-install failed: {_deps_status['install_error']}")
else:
    print("[deps] pdf2docx OK")

if app.config.get('DB_SQLITE_FALLBACK_USED'):
    print(f"[db] Active database: {mask_db_uri(app.config.get('SQLALCHEMY_DATABASE_URI') or '')}")

# Initialize extensions
from app.models import db
from app.security.security import init_jwt
from sqlalchemy.exc import SQLAlchemyError
db.init_app(app)
init_jwt(app)

# Create database tables
with app.app_context():
    try:
        db.create_all()
    except SQLAlchemyError as e:
        _raw_db_uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        _safe_db_uri = mask_db_uri(_raw_db_uri)
        print("\n[ERROR] Database initialization failed while creating tables.")
        print(f"DATABASE_URL: {_safe_db_uri or '(empty)'}")
        print("If using MySQL/XAMPP: start MySQL and verify api_base/.env credentials.")
        print("Local dev fallback: stop MySQL and restart — app auto-switches to SQLite.")
        raise SystemExit(1) from e

    from app.db_migrations import run_schema_migrations
    try:
        run_schema_migrations(db)
    except Exception as e:
        print(f"[WARN] Schema check/migration failed: {e}")

    # Tạo tài khoản admin mặc định nếu chưa có
    try:
        from app.models import User
        from werkzeug.security import generate_password_hash as _gph
        _ADMIN_EMAIL = os.getenv('ADMIN_ACCOUNT_EMAIL', 'admin@gmail.com')
        _ADMIN_PASS  = os.getenv('ADMIN_ACCOUNT_PASSWORD', 'admin123')
        _admin = User.query.filter_by(email=_ADMIN_EMAIL).first()
        if not _admin:
            _admin = User(
                email=_ADMIN_EMAIL,
                name='Admin',
                password_hash=_gph(_ADMIN_PASS),
                role='admin',
                plan='promax',
                email_verified=True,
            )
            db.session.add(_admin)
            db.session.commit()
            print(f"[init] Đã tạo tài khoản admin mặc định: {_ADMIN_EMAIL}")
        elif _admin.role != 'admin':
            _admin.role = 'admin'
            db.session.commit()
            print(f"[init] Đã nâng quyền admin cho: {_ADMIN_EMAIL}")
    except Exception as e:
        print(f"[WARN] Không thể tạo admin mặc định: {e}")

    # Scheduled account deletion (pending_delete → deleted after grace period)
    try:
        from app.services.account_deletion_service import finalize_scheduled_deletions
        n = finalize_scheduled_deletions()
        if n:
            print(f"[account-delete] Finalized {n} scheduled account deletion(s)")
    except Exception as e:
        print(f"[WARN] Account deletion scheduler (startup): {e}")


def _account_deletion_scheduler_loop():
    import time
    from app.services.account_deletion_service import finalize_scheduled_deletions
    interval = int(os.getenv('ACCOUNT_DELETE_SCHEDULER_SEC', '3600') or 3600)
    while True:
        time.sleep(max(60, interval))
        try:
            with app.app_context():
                n = finalize_scheduled_deletions()
                if n:
                    print(f"[account-delete] Finalized {n} scheduled account deletion(s)")
        except Exception as e:
            print(f"[WARN] Account deletion scheduler: {e}")


threading.Thread(target=_account_deletion_scheduler_loop, daemon=True).start()


# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(translation_bp, url_prefix='/api/translation')
app.register_blueprint(payment_bp, url_prefix='/api/payment')
app.register_blueprint(history_bp, url_prefix='/api/history')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(contact_bp, url_prefix='/api/contact')
app.register_blueprint(public_bp, url_prefix='/api/public')
# AI/config endpoints
app.register_blueprint(ai_bp, url_prefix='/api/ai')

# Route cho trang chủ trả về home.html
@app.route('/')
def home():
    return _serve_page_html('home.html')

# Route cho trang đăng ký/đăng nhập
@app.route('/auth')
def auth_page():
    return _serve_page_html('auth.html')

# Route cho trang dashboard
@app.route('/dashboard')
def dashboard_page():
    return _serve_page_html('dashboard.html')

# Route cho trang about
@app.route('/about')
def about_page():
    return _serve_page_html('about.html')

# Route cho trang contact
@app.route('/contact')
def contact_page():
    return _serve_page_html('contact.html')

# Trang pháp lý (Google Play / App Store)
def _serve_page_html(filename):
    resp = send_from_directory(PAGES_DIR, filename)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/privacy')
def privacy_page():
    return _serve_page_html('privacy.html')

@app.route('/terms')
def terms_page():
    return _serve_page_html('terms.html')

@app.route('/ai-terms')
def ai_terms_page():
    return _serve_page_html('ai-terms.html')

@app.route('/payment-policy')
def payment_policy_page():
    return _serve_page_html('payment-policy.html')

@app.route('/data-deletion')
def data_deletion_page():
    return _serve_page_html('data-deletion.html')

@app.route('/support')
def support_page():
    return _serve_page_html('support.html')

# Trang tài liệu / hướng dẫn
@app.route('/installation')
def installation_page():
    return send_from_directory(PAGES_DIR, 'installation.html')

@app.route('/user-guide')
def user_guide_page():
    return send_from_directory(PAGES_DIR, 'user-guide.html')

# Route cho trang profile
@app.route('/profile')
def profile_page():
    return send_from_directory(PAGES_DIR, 'profile.html')

@app.route('/account-pending-delete')
def account_pending_delete_page():
    return send_from_directory(PAGES_DIR, 'account-pending-delete.html')

# Route cho trang history
@app.route('/history')
def history_page():
    return send_from_directory(PAGES_DIR, 'history.html')

# Route cho trang admin
@app.route('/admin')
def admin_page():
    return send_from_directory(PAGES_DIR, 'admin.html')

# Route phục vụ thư viện tĩnh local (Font Awesome, v.v.)
@app.route('/libs/<path:filename>')
def serve_libs(filename):
    resp = send_from_directory(os.path.join(FRONTEND_DIR, 'libs'), filename)
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp

# Route phục vụ các file tĩnh (css, js, images)
@app.route('/css/<path:filename>')
def serve_css(filename):
    resp = send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)
    resp.headers['Cache-Control'] = 'no-store'
    return resp

@app.route('/js/<path:filename>')
def serve_js(filename):
    resp = send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)
    resp.headers['Cache-Control'] = 'no-store'
    return resp

@app.route('/config/<path:filename>')
def serve_config(filename):
    config_dir = os.path.join(FRONTEND_DIR, 'config')
    resp = send_from_directory(config_dir, filename)
    resp.headers['Cache-Control'] = 'no-store'
    return resp

# Route phục vụ trực tiếp các file HTML (để tương thích với links trong HTML)
@app.route('/<filename>.html')
def serve_html(filename):
    if filename in ['home', 'auth', 'dashboard', 'about', 'contact', 'profile', 'history',
                    'privacy', 'terms', 'ai-terms', 'payment-policy', 'data-deletion', 'support',
                    'installation', 'user-guide']:
        return send_from_directory(PAGES_DIR, f'{filename}.html')
    return jsonify({"error": "Page not found"}), 404

# Route phục vụ file đã dịch từ thư mục utils/download (serve as attachment to avoid opening inline)
@app.route('/downloads/<path:filename>')
def serve_downloads(filename):
    downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils', 'download')
    # Guess mimetype to send correct Content-Type
    import mimetypes
    mimetype, _ = mimetypes.guess_type(filename)
    return send_from_directory(downloads_dir, filename, as_attachment=True, mimetype=mimetype)

@app.route('/avatars/<path:filename>')
def serve_avatars(filename):
    avatars_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils', 'avatars')
    import mimetypes
    mimetype, _ = mimetypes.guess_type(filename)
    resp = send_from_directory(avatars_dir, filename, mimetype=mimetype or 'image/jpeg')
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp

# API cho leaderboard (placeholder)
@app.route('/api/games/leaderboard')
def game_leaderboard():
    leaderboard = [
        {"rank": 1, "username": "Player1", "score": 1000},
        {"rank": 2, "username": "Player2", "score": 950},
        {"rank": 3, "username": "Player3", "score": 900}
    ]
    return jsonify(leaderboard)

if __name__ == '__main__':
    _port = int(os.getenv('BACKEND_PORT', '5055') or 5055)
    # Print plain URLs on their own lines so VS Code terminal can Ctrl+Click reliably.
    _url_loopback = f"http://127.0.0.1:{_port}"
    _url_localhost = f"http://localhost:{_port}"
    print(f"Open URL: {_url_loopback}")
    print(f"Open URL: {_url_localhost}")
    print(f"Public stats API: {_url_loopback}/api/public/stats")

    # Optional auto-open browser for local dev.
    _auto_open = (os.getenv('BACKEND_AUTO_OPEN_BROWSER', '1') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    if _auto_open:
        _open_delay = float(os.getenv('BACKEND_AUTO_OPEN_DELAY_SECONDS', '1.2') or 1.2)

        def _open_browser() -> None:
            try:
                webbrowser.open(_url_loopback, new=2)
            except Exception:
                pass

        threading.Timer(_open_delay, _open_browser).start()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _sock:
            _sock.settimeout(0.5)
            if _sock.connect_ex(('127.0.0.1', _port)) == 0:
                print(f"[ERROR] Port {_port} is already in use. Another backend instance is running.")
                raise SystemExit(1)
    except SystemExit:
        raise
    except OSError:
        pass  # Socket probe failed (permission/network policy); let Flask report if port is unavailable
    app.run(host='0.0.0.0', port=_port, debug=False, use_reloader=False)