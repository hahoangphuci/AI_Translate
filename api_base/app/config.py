import os
from dotenv import load_dotenv
from .db_bootstrap import engine_options_for_uri, resolve_database_uri

# Load .env từ thư mục api_base (config.py nằm trong app/)
# IMPORTANT: In Docker, environment variables (e.g. DATABASE_URL) should win.
# Set DOTENV_OVERRIDE=1 only if you explicitly want .env to override existing env vars.
_override = (os.getenv('DOTENV_OVERRIDE') or '').strip().lower() in ('1', 'true', 'yes', 'on')
_api_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_api_base_dir, '.env'), override=_override)

_RESOLVED_DB_URI, _SQLITE_FALLBACK_USED = resolve_database_uri()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
    
    # Database (MySQL by default; auto-fallback to SQLite if XAMPP/MySQL is down)
    SQLALCHEMY_DATABASE_URI = _RESOLVED_DB_URI
    DB_SQLITE_FALLBACK_USED = _SQLITE_FALLBACK_USED
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = engine_options_for_uri(_RESOLVED_DB_URI)
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5055/api/auth/google/callback')
    
    # AI Services
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    DEEPL_API_KEY = os.getenv('DEEPL_API_KEY')

    # OpenRouter / AI Integration
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    AI_PROVIDER = os.getenv('AI_PROVIDER', 'openrouter')
    AI_MODEL = os.getenv('AI_MODEL', 'google/gemini-2.5-flash')
    AI_VISION_MODEL = os.getenv('AI_VISION_MODEL', 'google/gemini-2.5-flash')  # Vision-capable model for OCR (auto-detect if empty)
    AI_AVAILABLE_MODELS = os.getenv('AI_AVAILABLE_MODELS', '')
    AI_ENDPOINTS = {
        'chat': os.getenv('AI_ENDPOINT_CHAT'),
        'models': os.getenv('AI_ENDPOINT_MODELS')
    }
    AI_HEADERS = {
        'HTTP-Referer': os.getenv('AI_HEADER_HTTP_REFERER'),
        'X-Title': os.getenv('AI_HEADER_X_TITLE')
    }
    
    # Payment
    SEPAY_API_KEY = os.getenv('SEPAY_API_KEY')
    SEPAY_SECRET = os.getenv('SEPAY_SECRET')

    # Email / SMTP (dùng để gửi thông báo liên hệ cho admin)
    ADMIN_EMAIL    = os.getenv('ADMIN_EMAIL')           # email nhận thông báo
    SMTP_HOST      = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT      = int(os.getenv('SMTP_PORT', '587') or 587)
    SMTP_USER      = os.getenv('SMTP_USER')             # tài khoản gửi
    SMTP_PASSWORD  = os.getenv('SMTP_PASSWORD')         # app password
    SMTP_FROM      = os.getenv('SMTP_FROM')             # nếu để trống sẽ dùng SMTP_USER
    SMTP_USE_TLS   = os.getenv('SMTP_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    
    # File Upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'upload_temp')
    DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'utils', 'download')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # Frontend URL
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False