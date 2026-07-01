from flask import Blueprint, request, jsonify, redirect
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import db, User, Translation, UserLoginLog, AuthOtp
from werkzeug.security import generate_password_hash, check_password_hash
import google.auth.transport.requests
import google.oauth2.id_token
import google.oauth2.service_account
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlencode, quote

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

auth_bp = Blueprint('auth', __name__)


def _resolve_user(identity):
    """Lookup User from JWT identity.
    Identity is either google_id (Google OAuth) or str(user.id) (email/password).
    """
    user = User.query.filter_by(google_id=identity).first()
    if user:
        return user
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (TypeError, ValueError):
        return None


def _backend_dotenv_path() -> Path:
    # app/routes/auth.py → parents[2] = backend/
    return Path(__file__).resolve().parents[2] / ".env"


def _google_oauth_credentials():
    """Lấy Client ID/Secret tin cậy cho mọi request.

    Luôn đọc lại api_base/.env để không cần restart khi sửa GOOGLE_*.
    """
    from flask import current_app

    vals = {}
    p = _backend_dotenv_path()
    if p.is_file():
        try:
            from dotenv import dotenv_values
            vals = dotenv_values(p) or {}
        except Exception:
            vals = {}

    cid = (
        (vals.get("GOOGLE_CLIENT_ID") or "").strip()
        or (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
        or (current_app.config.get("GOOGLE_CLIENT_ID") or "").strip()
    )
    sec = (
        (vals.get("GOOGLE_CLIENT_SECRET") or "").strip()
        or (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
        or (current_app.config.get("GOOGLE_CLIENT_SECRET") or "").strip()
    )
    return cid, sec


def _google_client_secret_valid(secret: str) -> bool:
    sec = (secret or '').strip()
    if not sec or len(sec) < 10:
        return False
    upper = sec.upper()
    if upper.startswith('THAY_') or upper.startswith('YOUR_') or upper.startswith('CHANGE_'):
        return False
    if 'CLIENT_SECRET' in upper and 'THAY' in upper:
        return False
    return True

_OAUTH_STATE_SALT = "google-oauth-state-v1"
_OAUTH_STATE_MAX_AGE = 900  # 15 phút


def _oauth_state_sign(secret: str, extra: dict | None = None) -> str:
    payload = {"n": secrets.token_urlsafe(24)}
    if extra:
        payload.update(extra)
    ser = URLSafeTimedSerializer(secret, salt=_OAUTH_STATE_SALT)
    return ser.dumps(payload)


def _oauth_state_load(secret: str, state: str) -> dict | None:
    if not state or not isinstance(state, str):
        return None
    ser = URLSafeTimedSerializer(secret, salt=_OAUTH_STATE_SALT)
    try:
        data = ser.loads(state, max_age=_OAUTH_STATE_MAX_AGE)
        return data if isinstance(data, dict) else None
    except (BadSignature, SignatureExpired):
        return None


def _oauth_state_verify(secret: str, state: str) -> bool:
    return _oauth_state_load(secret, state) is not None


def _mobile_oauth_redirect(callback_scheme: str, **params):
    """Redirect về app mobile qua deep link aitranslator://oauth?..."""
    scheme = (callback_scheme or '').strip()
    if not scheme or not re.fullmatch(r'[a-z][a-z0-9+\-.]{0,62}', scheme):
        return None
    qs = urlencode(params, quote_via=quote)
    return redirect(f'{scheme}://oauth?{qs}')


def _resolve_google_redirect_uri():
    """Redirect URI khớp Google Cloud Console.

    - Web localhost/127.0.0.1 → callback trực tiếp (không cần ngrok).
    - App mobile / IP LAN / origin lạ → GOOGLE_REDIRECT_URI (ngrok) trong .env.
    """
    from flask import current_app, request
    from urllib.parse import urlparse

    vals = {}
    p = _backend_dotenv_path()
    if p.is_file():
        try:
            from dotenv import dotenv_values
            vals = dotenv_values(p) or {}
        except Exception:
            vals = {}
    env_uri = (
        (vals.get('GOOGLE_REDIRECT_URI') or '').strip()
        or (os.getenv('GOOGLE_REDIRECT_URI') or '').strip()
        or (current_app.config.get('GOOGLE_REDIRECT_URI') or '').strip()
    )
    fe = (
        (vals.get('FRONTEND_URL') or '').strip().rstrip('/')
        or (os.getenv('FRONTEND_URL') or '').strip().rstrip('/')
        or (current_app.config.get('FRONTEND_URL') or '').strip().rstrip('/')
    )

    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}

    callback_scheme = (payload.get('callback_scheme') or '').strip().lower()
    origin = (payload.get('origin') or request.headers.get('X-App-Origin') or '').strip().rstrip('/')

    # App mobile: luôn callback qua ngrok (deep link sau khi backend xử lý)
    if callback_scheme and env_uri:
        return env_uri

    local_origins = {
        'http://localhost:5055',
        'http://127.0.0.1:5055',
    }
    if origin in local_origins:
        return f'{origin}/api/auth/google/callback'

    if fe and origin.startswith(fe):
        return f'{fe}/api/auth/google/callback'

    # IP LAN: cùng máy với server → callback 127.0.0.1 (đã đăng ký Google, không cần ngrok)
    if origin.startswith(('http://', 'https://')):
        parsed = urlparse(origin)
        host = (parsed.hostname or '').lower()
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        if port == 5055 and (
            host.startswith('10.')
            or host.startswith('192.168.')
            or host.startswith('172.')
        ):
            remote = (request.remote_addr or '').strip()
            if remote in ('127.0.0.1', '::1', host):
                return 'http://127.0.0.1:5055/api/auth/google/callback'
            if env_uri:
                return env_uri

    if env_uri:
        return env_uri

    if origin.startswith(('http://', 'https://')):
        return f'{origin}/api/auth/google/callback'

    if request and getattr(request, 'host', None):
        scheme = (request.headers.get('X-Forwarded-Proto') or request.scheme or 'http').split(',')[0].strip()
        host = (request.headers.get('X-Forwarded-Host') or request.host or '').split(',')[0].strip()
        if host:
            return f'{scheme}://{host}/api/auth/google/callback'

    return 'http://127.0.0.1:5055/api/auth/google/callback'


def _google_redirect_uri_hints():
    """Gợi ý URI cần thêm vào Google Cloud Console."""
    from flask import current_app

    hints = {
        'http://localhost:5055/api/auth/google/callback',
        'http://127.0.0.1:5055/api/auth/google/callback',
    }
    env_uri = (current_app.config.get('GOOGLE_REDIRECT_URI') or '').strip()
    if env_uri:
        hints.add(env_uri)
    fe = (current_app.config.get('FRONTEND_URL') or os.getenv('FRONTEND_URL') or '').strip().rstrip('/')
    if fe:
        hints.add(f'{fe}/api/auth/google/callback')
    return sorted(hints)

@auth_bp.route('/config', methods=['GET'])
def auth_config():
    from flask import current_app

    rid = _resolve_google_redirect_uri()
    cid, csec = _google_oauth_credentials()
    return jsonify({
        'google_client_id': cid or None,
        'google_redirect_uri': rid,
        'google_redirect_uri_hints': _google_redirect_uri_hints(),
        'google_oauth_ready': bool(cid and csec and _google_client_secret_valid(csec)),
        'google_auth_mode': 'popup',
        'oauth_console_hint': (
            'Google Cloud → Credentials → OAuth 2.0 Client ID → '
            'Authorized JavaScript origins: http://127.0.0.1:5055 và http://localhost:5055. '
            'Redirect URIs vẫn cần cho app mobile/ngrok.'
        ),
    }), 200

@auth_bp.route('/google/authorize', methods=['POST', 'OPTIONS'])
def google_authorize():
    """Initiate Google OAuth flow - backend creates the authorization URL"""
    from flask import current_app

    if request.method == 'OPTIONS':
        return '', 204
    
    client_id, client_secret = _google_oauth_credentials()
    if not client_id:
        return jsonify({"error": "Google Client ID not configured"}), 500

    if not client_secret:
        return jsonify({
            "error": "missing_client_secret",
            "message": (
                "Chưa cấu hình GOOGLE_CLIENT_SECRET trong backend/.env. "
                "Google Cloud → Credentials → OAuth client (đúng Client ID) → Client secret → copy vào .env, rồi restart server."
            ),
        }), 500

    if not _google_client_secret_valid(client_secret):
        return jsonify({
            "error": "invalid_client_secret",
            "message": (
                "GOOGLE_CLIENT_SECRET trong api_base/.env chưa đúng (đang là placeholder). "
                "Google Cloud → OAuth client 1086485437554-... → Client secret → Hiện → copy vào .env → restart run_api.py."
            ),
        }), 500
    # State ký bằng SECRET_KEY — không phụ thuộc cookie session (tránh localhost vs 127.0.0.1).
    sk = current_app.config.get('SECRET_KEY') or ''
    if not sk:
        return jsonify({"error": "SECRET_KEY not configured"}), 500

    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    callback_scheme = (payload.get('callback_scheme') or '').strip().lower()
    redirect_uri = _resolve_google_redirect_uri()
    state_extra = {'ru': redirect_uri}
    if callback_scheme and re.fullmatch(r'[a-z][a-z0-9+\-.]{0,62}', callback_scheme):
        state_extra['cs'] = callback_scheme
    state = _oauth_state_sign(str(sk), state_extra)
    
    # Redirect URI theo domain hiện tại (localhost / ngrok)
    # redirect_uri đã resolve ở trên và lưu vào state
    
    print(f"[DEBUG] Building auth URL:")
    print(f"[DEBUG]   Client ID: {client_id[:20]}...")
    print(f"[DEBUG]   Redirect URI: {redirect_uri}")

    auth_url = (
        'https://accounts.google.com/o/oauth2/v2/auth?'
        + urlencode({
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
        })
    )
    
    print(f"[DEBUG] Full Auth URL: {auth_url[:150]}...")
    return jsonify({'auth_url': auth_url, 'redirect_uri': redirect_uri}), 200

@auth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Handle Google OAuth callback - exchange code for tokens"""
    from flask import current_app
    import requests
    
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    print(f"[DEBUG] Callback received: code={code[:20] if code else 'None'}, state={state}, error={error}")
    
    if error:
        state_payload = _oauth_state_load(
            str(current_app.config.get('SECRET_KEY') or ''), state or ''
        )
        cs = (state_payload or {}).get('cs') or ''
        mobile = _mobile_oauth_redirect(cs, error=error)
        if mobile:
            return mobile
        return redirect(f'/auth?error={error}')
    
    if not code:
        print(f"[WARN] OAuth callback without code; args={dict(request.args)}")
        return redirect('/auth?error=missing_code')
    
    sk = str(current_app.config.get('SECRET_KEY') or '')
    state_payload = _oauth_state_load(sk, state or '')
    if not state_payload:
        print(f"[ERROR] OAuth state invalid or expired (signed state check failed)")
        return redirect('/auth?error=state_mismatch')
    callback_scheme = (state_payload.get('cs') or '').strip()
    redirect_uri = (state_payload.get('ru') or '').strip() or _resolve_google_redirect_uri()

    def _fail(error_code: str):
        mobile = _mobile_oauth_redirect(callback_scheme, error=error_code)
        if mobile:
            return mobile
        return redirect(f'/auth?error={error_code}')
    
    client_id, client_secret = _google_oauth_credentials()
    if not client_id or not client_secret:
        print(
            f"[ERROR] OAuth missing_credentials id_set={bool(client_id)} "
            f"secret_set={bool(client_secret)}"
        )
        return _fail('missing_credentials')
    
    # Exchange code — redirect_uri phải trùng bước authorize (lấy từ state)
    
    print(f"[DEBUG] Token exchange:")
    print(f"[DEBUG]   Code: {code[:20] if code else 'None'}...")
    print(f"[DEBUG]   Redirect URI: {redirect_uri}")
    
    token_url = 'https://oauth2.googleapis.com/token'
    
    try:
        response = requests.post(token_url, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        })
        
        token_data = response.json()
        print(f"[DEBUG] Token response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[ERROR] Token exchange failed: {token_data}")
            return _fail('token_exchange_failed')
        
        id_token = token_data.get('id_token')
        if not id_token:
            print(f"[ERROR] No id_token in response")
            return _fail('no_id_token')
        
        # Verify and decode ID token
        try:
            idinfo = google.oauth2.id_token.verify_oauth2_token(
                id_token,
                google.auth.transport.requests.Request(),
                client_id
            )
            
            user_id = idinfo.get('sub')
            email = idinfo.get('email')
            name = idinfo.get('name')
            
            print(f"[DEBUG] Token verified for user: {user_id}, {email}")
            
            # Create or get user
            user = User.query.filter_by(google_id=user_id).first()
            if not user:
                print(f"[DEBUG] Creating new user: {user_id}")
                user = User(google_id=user_id, email=email, name=name, email_verified=True)
                db.session.add(user)
                db.session.commit()
            elif not user.email_verified:
                user.email_verified = True
                db.session.commit()

            # Save login log
            try:
                ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
                      or request.remote_addr or None)
                db.session.add(UserLoginLog(
                    user_id=user.id,
                    ip_address=ip,
                    user_agent=(request.headers.get('User-Agent') or '')[:500],
                ))
                db.session.commit()
            except Exception:
                pass

            # Create JWT for our app
            from app.services.account_deletion_service import login_block_response
            blocked = login_block_response(user)
            if blocked:
                return redirect('/auth?error=account_deleted')

            access_token = create_access_token(identity=user_id)
            print(f"[DEBUG] JWT created for user: {user_id}")

            if callback_scheme and re.fullmatch(
                r'[a-z][a-z0-9+\-.]{0,62}', callback_scheme
            ):
                return redirect(
                    f'{callback_scheme}://oauth?token={quote(access_token, safe="")}'
                )

            redirect_path = _post_login_redirect_path(user)
            return redirect(f'{redirect_path}?token={access_token}')
            
        except ValueError as e:
            print(f"[ERROR] ID token verification failed: {str(e)}")
            return _fail('token_verification_failed')
            
    except Exception as e:
        print(f"[ERROR] Token exchange exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return _fail('server_error')


def _google_login_from_idinfo(idinfo):
    """Tạo/cập nhật user từ Google idinfo, trả về (user, jwt, error_response)."""
    from app.services.account_deletion_service import login_block_response

    user_id = idinfo.get('sub')
    email = idinfo.get('email')
    name = idinfo.get('name')
    if not user_id or not email:
        return None, None, (jsonify({"error": "Missing user info in token"}), 400)

    user = User.query.filter_by(google_id=user_id).first()
    if not user:
        user = User(google_id=user_id, email=email, name=name, email_verified=True)
        db.session.add(user)
        db.session.commit()
    elif not user.email_verified:
        user.email_verified = True
        db.session.commit()

    blocked = login_block_response(user)
    if blocked:
        return None, None, blocked

    try:
        ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
              or request.remote_addr or None)
        db.session.add(UserLoginLog(
            user_id=user.id,
            ip_address=ip,
            user_agent=(request.headers.get('User-Agent') or '')[:500],
        ))
        db.session.commit()
    except Exception:
        pass

    token = create_access_token(identity=user_id)
    return user, token, None


def _google_login_access_token_from_idinfo(idinfo):
    """Backward-compatible wrapper."""
    user, token, err = _google_login_from_idinfo(idinfo)
    if err:
        return None, err
    return token, None


@auth_bp.route('/google/code', methods=['POST'])
def google_code_exchange():
    """Đổi authorization code từ GSI popup (redirect_uri=postmessage) → JWT app."""
    import requests

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({"error": "Missing code"}), 400

    client_id, client_secret = _google_oauth_credentials()
    if not client_id or not client_secret or not _google_client_secret_valid(client_secret):
        return jsonify({
            "error": "missing_credentials",
            "message": "Chưa cấu hình GOOGLE_CLIENT_SECRET trong api_base/.env",
        }), 500

    try:
        response = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'postmessage',
        })
        token_data = response.json()
        if response.status_code != 200:
            print(f"[ERROR] Popup code exchange failed: {token_data}")
            return jsonify({
                "error": "token_exchange_failed",
                "message": token_data.get('error_description') or token_data.get('error'),
            }), 400

        id_token = token_data.get('id_token')
        if not id_token:
            return jsonify({"error": "no_id_token"}), 400

        idinfo = google.oauth2.id_token.verify_oauth2_token(
            id_token,
            google.auth.transport.requests.Request(),
            client_id,
        )
        user, access_token, err = _google_login_from_idinfo(idinfo)
        if err:
            return err
        return _build_login_json(user, access_token)

    except ValueError as e:
        print(f"[ERROR] Popup ID token verification failed: {e}")
        return jsonify({"error": f"Invalid token: {str(e)}"}), 400
    except Exception as e:
        print(f"[ERROR] google_code_exchange: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "server_error"}), 500

@auth_bp.route('/google', methods=['POST'])
def google_auth():
    try:
        data = request.get_json()
        if not data or not data.get('token'):
            return jsonify({"error": "Missing token"}), 400
        
        token = data.get('token')
        print(f"[DEBUG] Received token: {token[:50]}...")
        
        gcid, _ = _google_oauth_credentials()
        if not gcid:
            return jsonify({"error": "Google Client ID not configured"}), 500
        idinfo = google.oauth2.id_token.verify_oauth2_token(
            token,
            google.auth.transport.requests.Request(),
            gcid,
        )
        
        user_id = idinfo.get('sub')
        email = idinfo.get('email')
        name = idinfo.get('name')
        
        print(f"[DEBUG] Verified user: {user_id}, {email}, {name}")
        
        if not user_id or not email:
            return jsonify({"error": "Missing user info in token"}), 400
        
        user, access_token, err = _google_login_from_idinfo(idinfo)
        if err:
            return err

        print(f"[DEBUG] Token created for user: {user_id}")
        return _build_login_json(user, access_token)
        
    except ValueError as e:
        print(f"[ERROR] Token verification failed: {str(e)}")
        return jsonify({"error": f"Invalid token: {str(e)}"}), 400
    except Exception as e:
        print(f"[ERROR] Unexpected error in google_auth: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = _resolve_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    from app.services.account_deletion_service import is_account_deleted
    if is_account_deleted(user):
        return jsonify({
            'error': 'account_deleted',
            'message': 'Tài khoản đã bị xóa hoặc vô hiệu hóa.',
        }), 403

    plan = user.plan or 'free'
    plan_info = {
        'free': {'name': 'Free'},
        'pro': {'name': 'Pro'},
        'promax': {'name': 'ProMax'}
    }.get(plan, {'name': plan})

    payload = _user_json(user)
    payload['plan_name'] = plan_info['name']
    return jsonify(payload), 200


@auth_bp.route('/profile', methods=['PATCH'])
@jwt_required()
def update_profile():
    """Update mutable profile fields (currently: name)."""
    user_google_id = get_jwt_identity()
    user = _resolve_user(user_google_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name')
    avatar_url = data.get('avatar_url')

    if name is not None:
        name = str(name).strip()
        if len(name) > 255:
            return jsonify({"error": "Name too long"}), 400
        user.name = name

    if avatar_url is not None:
        avatar_url = str(avatar_url).strip()
        if avatar_url and len(avatar_url) > 500:
            return jsonify({"error": "avatar_url too long"}), 400
        # Allow clearing by sending empty string
        user.avatar_url = avatar_url or None

    db.session.commit()

    return jsonify({
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'avatar_url': getattr(user, 'avatar_url', None),
        'plan': user.plan or 'free',
    }), 200


def _avatar_storage_dir() -> Path:
    # api_base/app/routers/auth.py → parents[2] = api_base/
    base = Path(__file__).resolve().parents[2] / 'utils' / 'avatars'
    base.mkdir(parents=True, exist_ok=True)
    return base


def _public_file_url(subpath: str) -> str:
    """Absolute URL for uploaded static files (avatar, …)."""
    from flask import request, current_app

    fe = (
        (os.getenv('FRONTEND_URL') or '').strip().rstrip('/')
        or (current_app.config.get('FRONTEND_URL') or '').strip().rstrip('/')
    )
    if fe:
        return f'{fe}/{subpath.lstrip("/")}'
    root = request.url_root.rstrip('/')
    return f'{root}/{subpath.lstrip("/")}'


@auth_bp.route('/profile/avatar', methods=['POST'])
@jwt_required()
def upload_profile_avatar():
    """Upload avatar image from mobile app (multipart/form-data field: file)."""
    import uuid
    from werkzeug.utils import secure_filename

    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'No file provided'}), 400

    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    allowed = {'.jpg', '.jpeg', '.png', '.webp'}
    if ext not in allowed:
        return jsonify({'error': 'Unsupported image type. Use JPG, PNG or WEBP.'}), 400

    raw = file.read()
    if not raw:
        return jsonify({'error': 'Empty file'}), 400
    if len(raw) > 2 * 1024 * 1024:
        return jsonify({'error': 'File too large (max 2MB)'}), 400

    filename = f'user_{user.id}_{uuid.uuid4().hex[:12]}{ext if ext != ".jpeg" else ".jpg"}'
    dest = _avatar_storage_dir() / filename
    dest.write_bytes(raw)

    user.avatar_url = _public_file_url(f'avatars/{filename}')
    db.session.commit()

    return jsonify({
        'message': 'Avatar updated',
        'avatar_url': user.avatar_url,
        'user': _user_json(user),
    }), 200


# ─────────────────────────────────────────────────────
# Email / Password login (tài khoản nội bộ) + OTP
# ─────────────────────────────────────────────────────

from app.services.otp_service import (
    OTP_MAX_WRONG,
    can_resend,
    generate_otp_code,
    hash_otp,
    is_valid_gmail,
    is_valid_username,
    normalize_gmail,
    otp_expired,
    register_expires_at,
    reset_expires_at,
    reset_token_expires_at,
    RESET_TOKEN_TTL_MIN,
    utcnow,
    verify_otp_code,
)
from app.services.email_service import send_otp_email_sync

_RESET_TOKEN_SALT = 'password-reset-token-v1'
_FORGOT_GENERIC_MSG = (
    'Nếu thông tin hợp lệ, hệ thống đã gửi hướng dẫn khôi phục đến Gmail đã đăng ký.'
)


def _reset_serializer():
    from flask import current_app
    return URLSafeTimedSerializer(str(current_app.config.get('SECRET_KEY') or ''), salt=_RESET_TOKEN_SALT)


def _issue_reset_token(user_id: int) -> str:
    exp = reset_token_expires_at()
    return _reset_serializer().dumps({'uid': user_id, 'exp': exp.isoformat()})


def _load_reset_token(token: str) -> int | None:
    try:
        data = _reset_serializer().loads(token, max_age=RESET_TOKEN_TTL_MIN * 60)
        uid = int(data.get('uid'))
        return uid if uid > 0 else None
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def _delete_otp_records(purpose: str, email: str):
    AuthOtp.query.filter_by(purpose=purpose, email=email).delete(synchronize_session=False)
    db.session.commit()


def _find_user_by_login(identifier: str):
    ident = (identifier or '').strip()
    if not ident:
        return None
    if '@' in ident:
        return User.query.filter_by(email=normalize_gmail(ident)).first()
    return User.query.filter_by(username=ident).first()


def _user_json(user):
    status = (getattr(user, 'account_status', None) or 'active').strip().lower()
    payload = {
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'name': user.name,
        'avatar_url': user.avatar_url,
        'plan': user.plan or 'free',
        'role': user.role or 'user',
        'token_balance': int(user.token_balance or 0),
        'email_verified': bool(user.email_verified),
        'account_status': status,
    }
    if status == 'pending_delete':
        if user.delete_scheduled_at:
            payload['delete_scheduled_at'] = user.delete_scheduled_at.isoformat() + 'Z'
        if user.delete_requested_at:
            payload['delete_requested_at'] = user.delete_requested_at.isoformat() + 'Z'
    return payload


def _post_login_redirect_path(user):
    from app.services.account_deletion_service import is_account_pending_delete
    if is_account_pending_delete(user):
        return '/account-pending-delete'
    return '/dashboard'


def _build_login_json(user, access_token):
    from app.services.account_deletion_service import login_block_response, pending_delete_meta

    blocked = login_block_response(user)
    if blocked:
        return blocked
    payload = {
        'access_token': access_token,
        'user': _user_json(user),
    }
    payload.update(pending_delete_meta(user))
    return jsonify(payload), 200


def _send_otp_record(record: AuthOtp, purpose: str) -> tuple[bool, str]:
    code = generate_otp_code()
    record.otp_hash = hash_otp(code)
    ok, err = send_otp_email_sync(record.email, code, purpose)
    if not ok:
        db.session.rollback()
        return False, err or 'Không gửi được email OTP.'
    db.session.commit()
    return True, ''


@auth_bp.route('/login', methods=['POST'])
def login():
    """Đăng nhập bằng email + mật khẩu."""
    data = request.get_json(silent=True) or {}
    email = normalize_gmail(data.get('email') or '')
    password = str(data.get('password') or '').strip()

    if not email or not password:
        return jsonify({'error': 'Email và mật khẩu không được để trống'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.password_hash:
        return jsonify({'error': 'Email hoặc mật khẩu không đúng'}), 401
    if not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Email hoặc mật khẩu không đúng'}), 401
    if not user.email_verified:
        return jsonify({
            'error': 'email_not_verified',
            'message': 'Tài khoản chưa xác thực Gmail. Vui lòng hoàn tất xác thực OTP khi đăng ký.',
        }), 403

    try:
        ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
              or request.remote_addr or None)
        db.session.add(UserLoginLog(
            user_id=user.id,
            ip_address=ip,
            user_agent=(request.headers.get('User-Agent') or '')[:500],
        ))
        db.session.commit()
    except Exception:
        pass

    access_token = create_access_token(identity=user.google_id or str(user.id))
    return _build_login_json(user, access_token)


@auth_bp.route('/register/request', methods=['POST'])
def register_request():
    """Bước 1: validate + gửi OTP đăng ký (chưa tạo user)."""
    data = request.get_json(silent=True) or {}
    first_name = str(data.get('first_name') or '').strip()
    last_name = str(data.get('last_name') or '').strip()
    username = str(data.get('username') or '').strip()
    email = normalize_gmail(data.get('email') or '')
    password = str(data.get('password') or '').strip()
    confirm = str(data.get('confirm_password') or data.get('confirmPassword') or '').strip()
    agree_terms = bool(data.get('agree_terms') or data.get('agreeTerms'))

    if not first_name or not last_name:
        return jsonify({'error': 'Họ và tên không được để trống'}), 400
    if not username:
        return jsonify({'error': 'Username không được để trống'}), 400
    if not is_valid_username(username):
        return jsonify({'error': 'Username 3–30 ký tự, chỉ chữ, số và dấu _'}), 400
    if not email:
        return jsonify({'error': 'Email không được để trống'}), 400
    if not is_valid_gmail(email):
        return jsonify({'error': 'Chỉ chấp nhận email Gmail (@gmail.com)'}), 400
    if not password or len(password) < 8:
        return jsonify({'error': 'Mật khẩu phải có ít nhất 8 ký tự'}), 400
    if password != confirm:
        return jsonify({'error': 'Mật khẩu xác nhận không khớp'}), 400
    if not agree_terms:
        return jsonify({'error': 'Bạn phải đồng ý điều khoản sử dụng'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email đã được sử dụng'}), 409
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username đã được sử dụng'}), 409

    name = f'{first_name} {last_name}'.strip()
    _delete_otp_records('register', email)

    record = AuthOtp(
        purpose='register',
        email=email,
        username=username,
        name=name,
        password_hash=generate_password_hash(password),
        otp_hash=hash_otp('000000'),
        expires_at=register_expires_at(),
        wrong_attempts=0,
        resend_count=0,
        resend_window_start=utcnow(),
    )
    db.session.add(record)
    db.session.flush()

    ok, err = _send_otp_record(record, 'register')
    if not ok:
        return jsonify({'error': 'email_send_failed', 'message': err}), 502

    return jsonify({
        'message': 'Mã OTP đã được gửi đến Gmail của bạn. Mã có hiệu lực 5 phút.',
        'email': email,
        'expires_in_seconds': 300,
    }), 200


@auth_bp.route('/register/verify', methods=['POST'])
def register_verify():
    data = request.get_json(silent=True) or {}
    email = normalize_gmail(data.get('email') or '')
    otp = str(data.get('otp') or '').strip()

    if not email or not otp:
        return jsonify({'error': 'Email và mã OTP không được để trống'}), 400

    record = AuthOtp.query.filter_by(purpose='register', email=email).order_by(AuthOtp.id.desc()).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy yêu cầu đăng ký. Vui lòng đăng ký lại.'}), 404

    if otp_expired(record.expires_at):
        return jsonify({'error': 'otp_expired', 'message': 'Mã OTP đã hết hạn. Vui lòng gửi lại mã.'}), 400

    if int(record.wrong_attempts or 0) >= OTP_MAX_WRONG:
        return jsonify({'error': 'otp_locked', 'message': 'Bạn đã nhập sai OTP quá 5 lần. Vui lòng gửi lại mã.'}), 429

    if not verify_otp_code(otp, record.otp_hash):
        record.wrong_attempts = int(record.wrong_attempts or 0) + 1
        db.session.commit()
        left = OTP_MAX_WRONG - record.wrong_attempts
        return jsonify({
            'error': 'otp_invalid',
            'message': f'Mã OTP không đúng. Còn {max(left, 0)} lần thử.',
        }), 400

    if User.query.filter_by(email=email).first():
        _delete_otp_records('register', email)
        return jsonify({'error': 'Email đã được sử dụng'}), 409
    if User.query.filter_by(username=record.username).first():
        _delete_otp_records('register', email)
        return jsonify({'error': 'Username đã được sử dụng'}), 409

    user = User(
        email=email,
        username=record.username,
        name=record.name,
        password_hash=record.password_hash,
        email_verified=True,
    )
    db.session.add(user)
    _delete_otp_records('register', email)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    return jsonify({
        'message': 'Đăng ký thành công!',
        'access_token': access_token,
        'user': _user_json(user),
    }), 201


@auth_bp.route('/register/resend', methods=['POST'])
def register_resend():
    data = request.get_json(silent=True) or {}
    email = normalize_gmail(data.get('email') or '')
    if not email:
        return jsonify({'error': 'Email không được để trống'}), 400

    record = AuthOtp.query.filter_by(purpose='register', email=email).order_by(AuthOtp.id.desc()).first()
    if not record:
        return jsonify({'error': 'Không tìm thấy yêu cầu đăng ký'}), 404

    allowed, msg = can_resend(record)
    if not allowed:
        return jsonify({'error': 'resend_limit', 'message': msg}), 429

    if not record.resend_window_start:
        record.resend_window_start = utcnow()
    record.resend_count = int(record.resend_count or 0) + 1
    record.wrong_attempts = 0
    record.expires_at = register_expires_at()

    ok, err = _send_otp_record(record, 'register')
    if not ok:
        return jsonify({'error': 'email_send_failed', 'message': err}), 502

    return jsonify({'message': 'Đã gửi lại mã OTP. Mã có hiệu lực 5 phút.'}), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    """Legacy endpoint — chuyển sang luồng OTP."""
    return jsonify({
        'error': 'use_otp_flow',
        'message': 'Vui lòng dùng /api/auth/register/request và /api/auth/register/verify.',
    }), 400


@auth_bp.route('/forgot-password/request', methods=['POST'])
def forgot_password_request():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier') or data.get('email') or data.get('username') or '').strip()

    generic = {'message': _FORGOT_GENERIC_MSG}

    if not identifier:
        return jsonify(generic), 200

    user = _find_user_by_login(identifier)
    if not user or not user.password_hash or not user.email_verified:
        return jsonify(generic), 200

    email = normalize_gmail(user.email)
    if not is_valid_gmail(email):
        return jsonify(generic), 200

    _delete_otp_records('password_reset', email)
    record = AuthOtp(
        purpose='password_reset',
        email=email,
        user_id=user.id,
        otp_hash=hash_otp('000000'),
        expires_at=reset_expires_at(),
        wrong_attempts=0,
        resend_count=0,
        resend_window_start=utcnow(),
    )
    db.session.add(record)
    db.session.flush()

    ok, err = _send_otp_record(record, 'password_reset')
    if not ok:
        return jsonify({'error': 'email_send_failed', 'message': err}), 502

    return jsonify(generic), 200


@auth_bp.route('/forgot-password/verify', methods=['POST'])
def forgot_password_verify():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier') or data.get('email') or data.get('username') or '').strip()
    otp = str(data.get('otp') or '').strip()

    if not identifier or not otp:
        return jsonify({'error': 'Thông tin và mã OTP không được để trống'}), 400

    user = _find_user_by_login(identifier)
    if not user or not user.email_verified:
        return jsonify({'error': 'otp_invalid', 'message': 'Mã OTP không đúng.'}), 400

    email = normalize_gmail(user.email)
    record = AuthOtp.query.filter_by(purpose='password_reset', email=email).order_by(AuthOtp.id.desc()).first()
    if not record:
        return jsonify({'error': 'otp_invalid', 'message': 'Mã OTP không đúng.'}), 400

    if otp_expired(record.expires_at):
        return jsonify({'error': 'otp_expired', 'message': 'Mã OTP đã hết hạn. Vui lòng gửi lại mã.'}), 400

    if int(record.wrong_attempts or 0) >= OTP_MAX_WRONG:
        return jsonify({'error': 'otp_locked', 'message': 'Bạn đã nhập sai OTP quá 5 lần.'}), 429

    if not verify_otp_code(otp, record.otp_hash):
        record.wrong_attempts = int(record.wrong_attempts or 0) + 1
        db.session.commit()
        return jsonify({'error': 'otp_invalid', 'message': 'Mã OTP không đúng.'}), 400

    reset_token = _issue_reset_token(user.id)
    _delete_otp_records('password_reset', email)

    return jsonify({
        'message': 'Xác thực OTP thành công. Hãy đặt mật khẩu mới.',
        'reset_token': reset_token,
    }), 200


@auth_bp.route('/forgot-password/resend', methods=['POST'])
def forgot_password_resend():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier') or data.get('email') or data.get('username') or '').strip()
    generic = {'message': _FORGOT_GENERIC_MSG}

    if not identifier:
        return jsonify(generic), 200

    user = _find_user_by_login(identifier)
    if not user or not user.password_hash or not user.email_verified:
        return jsonify(generic), 200

    email = normalize_gmail(user.email)
    record = AuthOtp.query.filter_by(purpose='password_reset', email=email).order_by(AuthOtp.id.desc()).first()
    if not record:
        _delete_otp_records('password_reset', email)
        record = AuthOtp(
            purpose='password_reset',
            email=email,
            user_id=user.id,
            otp_hash=hash_otp('000000'),
            expires_at=reset_expires_at(),
            wrong_attempts=0,
            resend_count=0,
            resend_window_start=utcnow(),
        )
        db.session.add(record)
        db.session.flush()

    allowed, msg = can_resend(record)
    if not allowed:
        return jsonify({'error': 'resend_limit', 'message': msg}), 429

    record.resend_count = int(record.resend_count or 0) + 1
    record.wrong_attempts = 0
    record.expires_at = reset_expires_at()

    ok, err = _send_otp_record(record, 'password_reset')
    if not ok:
        return jsonify({'error': 'email_send_failed', 'message': err}), 502

    return jsonify({'message': 'Đã gửi lại mã OTP khôi phục mật khẩu.'}), 200


@auth_bp.route('/forgot-password/reset', methods=['POST'])
def forgot_password_reset():
    data = request.get_json(silent=True) or {}
    reset_token = str(data.get('reset_token') or '').strip()
    password = str(data.get('password') or '').strip()
    confirm = str(data.get('confirm_password') or data.get('confirmPassword') or '').strip()

    if not reset_token or not password:
        return jsonify({'error': 'Token và mật khẩu mới không được để trống'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Mật khẩu phải có ít nhất 8 ký tự'}), 400
    if password != confirm:
        return jsonify({'error': 'Mật khẩu xác nhận không khớp'}), 400

    user_id = _load_reset_token(reset_token)
    if not user_id:
        return jsonify({'error': 'reset_token_invalid', 'message': 'Phiên đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.'}), 400

    user = User.query.get(user_id)
    if not user or not user.email_verified:
        return jsonify({'error': 'reset_token_invalid', 'message': 'Phiên đặt lại mật khẩu không hợp lệ.'}), 400

    user.password_hash = generate_password_hash(password)
    db.session.commit()

    return jsonify({'message': 'Đặt lại mật khẩu thành công. Bạn có thể đăng nhập.'}), 200


# ─────────────────────────────────────────────────────
# Account deletion / restore (30-day grace period)
# ─────────────────────────────────────────────────────

from app.services.account_deletion_service import (
    confirm_account_delete,
    confirm_account_restore,
    request_account_delete,
    request_account_restore,
)


@auth_bp.route('/account/delete/request', methods=['POST'])
@jwt_required()
def account_delete_request():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    reason = str(data.get('reason') or data.get('delete_reason') or '').strip() or None

    ok, message, extra = request_account_delete(user, reason)
    if not ok:
        return jsonify({'error': 'delete_request_failed', 'message': message}), 400

    payload = {'message': message}
    if extra:
        payload.update(extra)
    return jsonify(payload), 200


@auth_bp.route('/account/delete/confirm', methods=['POST'])
@jwt_required()
def account_delete_confirm():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    otp = str(data.get('otp') or data.get('code') or '').strip()
    if not otp:
        return jsonify({'error': 'OTP không được để trống'}), 400

    ok, message, extra = confirm_account_delete(user, otp)
    if not ok:
        return jsonify({'error': 'delete_confirm_failed', 'message': message}), 400

    payload = {'message': message, 'user': _user_json(user)}
    if extra:
        payload.update(extra)
    return jsonify(payload), 200


@auth_bp.route('/account/restore/request', methods=['POST'])
@jwt_required()
def account_restore_request():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    ok, message, extra = request_account_restore(user)
    if not ok:
        return jsonify({'error': 'restore_request_failed', 'message': message}), 400

    payload = {'message': message}
    if extra:
        payload.update(extra)
    return jsonify(payload), 200


@auth_bp.route('/account/restore/confirm', methods=['POST'])
@jwt_required()
def account_restore_confirm():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    otp = str(data.get('otp') or data.get('code') or '').strip()
    if not otp:
        return jsonify({'error': 'OTP không được để trống'}), 400

    ok, message, extra = confirm_account_restore(user, otp)
    if not ok:
        return jsonify({'error': 'restore_confirm_failed', 'message': message}), 400

    payload = {'message': message, 'user': _user_json(user)}
    if extra:
        payload.update(extra)
    return jsonify(payload), 200
