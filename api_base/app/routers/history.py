from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, Translation, User
from app.services.history_clear_service import (
    confirm_clear_history,
    request_clear_history_otp,
)

history_bp = Blueprint('history', __name__)


def _resolve_user(identity):
    """Lookup User from JWT identity (google_id or str(user.id))."""
    user = User.query.filter_by(google_id=identity).first()
    if user:
        return user
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (TypeError, ValueError):
        return None


@history_bp.route('/', methods=['GET'])
@jwt_required()
def get_history():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'translations': [], 'total': 0, 'pages': 0, 'current_page': 1}), 200

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    filter_type = (request.args.get('type') or 'all').strip().lower()
    date_str = (request.args.get('date') or '').strip()

    q = Translation.query.filter(Translation.user_id == user.id)
    if filter_type == 'text':
        q = q.filter(Translation.file_path.is_(None))
    elif filter_type == 'document':
        q = q.filter(Translation.file_path.isnot(None))

    if date_str:
        from datetime import datetime
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            q = q.filter(db.func.date(Translation.created_at) == d)
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    q = q.order_by(Translation.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    history = [{
        'id': t.id,
        'original_text': t.original_text,
        'translated_text': t.translated_text,
        'source_lang': t.source_lang,
        'target_lang': t.target_lang,
        'created_at': t.created_at.isoformat(),
        'has_file': bool(t.file_path)
    } for t in pagination.items]

    return jsonify({
        'translations': history,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    }), 200


@history_bp.route('/clear/request', methods=['POST'])
@jwt_required()
def clear_history_request():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if not user.email:
        return jsonify({'message': 'Tài khoản chưa có email để gửi OTP.'}), 400

    ok, message, meta = request_clear_history_otp(user)
    if not ok:
        return jsonify({'message': message}), 400
    return jsonify({'message': message, **(meta or {})}), 200


@history_bp.route('/clear/confirm', methods=['POST'])
@jwt_required()
def clear_history_confirm():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}
    otp = (data.get('otp') or '').strip()
    if len(otp) != 6 or not otp.isdigit():
        return jsonify({'message': 'Vui lòng nhập đủ 6 chữ số OTP.'}), 400

    ok, message, meta = confirm_clear_history(user, otp)
    if not ok:
        return jsonify({'message': message}), 400
    return jsonify({'message': message, **(meta or {})}), 200


@history_bp.route('/<int:translation_id>', methods=['DELETE'])
@jwt_required()
def delete_translation(translation_id):
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({"error": "User not found"}), 404

    translation = Translation.query.filter_by(id=translation_id, user_id=user.id).first()
    if translation:
        db.session.delete(translation)
        db.session.commit()
        return jsonify({"message": "Translation deleted"}), 200
    return jsonify({"error": "Translation not found"}), 404
