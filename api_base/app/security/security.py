from flask import jsonify
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from functools import wraps
from datetime import timedelta

jwt = JWTManager()

def init_jwt(app):
    app.config['JWT_SECRET_KEY'] = app.config.get('JWT_SECRET_KEY', 'your-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
    jwt.init_app(app)

    # Custom error handlers so frontend receives a consistent JSON shape
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired", "code": "token_expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        return jsonify({"error": "Invalid token", "code": "token_invalid"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error_string):
        return jsonify({"error": "Missing authorization token", "code": "token_missing"}), 401


def _get_current_user():
    """Helper: resolve the User object from JWT identity.

    Identity is either a Google ID string (Google OAuth users) or
    str(user.id) (email/password users whose google_id is NULL).
    Try google_id first; fall back to numeric id lookup.
    """
    from app.models import User
    identity = get_jwt_identity()
    user = User.query.filter_by(google_id=identity).first()
    if user:
        return user
    # Fallback: email/password users store str(user.id) as identity
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (TypeError, ValueError):
        return None


def admin_required(fn):
    """Decorator: JWT required + role must be 'admin'."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = _get_current_user()
        if not user:
            return jsonify({"error": "User not found", "code": "user_not_found"}), 404
        if (user.role or 'user') != 'admin':
            return jsonify({"error": "Admin access required", "code": "forbidden"}), 403
        return fn(*args, **kwargs)
    return wrapper