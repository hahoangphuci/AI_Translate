"""
Contact router — /api/contact/*
Public endpoints: contact form, newsletter subscribe/unsubscribe.
"""
import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request, get_jwt
from app.models import db, ContactMessage, NewsletterSubscriber
from app.services.email_service import notify_admin_new_contact, notify_user_contact_received

contact_bp = Blueprint('contact', __name__)

_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_VALID_SUBJECTS = {'general', 'technical', 'billing', 'partnership', 'enterprise', 'other'}


def _get_ip():
    return (
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        or request.remote_addr
        or None
    )


# ─────────────────────────────────────────
# Contact form
# ─────────────────────────────────────────

@contact_bp.route('/send', methods=['POST'])
def send_contact():
    """Gửi tin nhắn liên hệ — không cần đăng nhập."""
    data = request.get_json(silent=True) or {}

    first_name = str(data.get('first_name') or '').strip()
    last_name  = str(data.get('last_name')  or '').strip()
    email      = str(data.get('email')      or '').strip().lower()
    subject    = str(data.get('subject')    or 'general').strip().lower()
    message    = str(data.get('message')    or '').strip()

    # Validate
    errors = {}
    if len(first_name) < 2:
        errors['first_name'] = 'Tên phải có ít nhất 2 ký tự'
    if len(last_name) < 2:
        errors['last_name'] = 'Họ phải có ít nhất 2 ký tự'
    if not _EMAIL_RE.match(email):
        errors['email'] = 'Email không hợp lệ'
    if subject not in _VALID_SUBJECTS:
        subject = 'general'
    if len(message) < 10:
        errors['message'] = 'Tin nhắn phải có ít nhất 10 ký tự'
    if len(message) > 1000:
        errors['message'] = 'Tin nhắn không quá 1000 ký tự'

    if errors:
        return jsonify({'error': 'Validation failed', 'fields': errors}), 422

    msg = ContactMessage(
        first_name=first_name[:100],
        last_name=last_name[:100],
        email=email[:255],
        subject=subject,
        message=message,
        ip_address=_get_ip(),
    )
    db.session.add(msg)
    db.session.commit()

    # Gửi email thông báo cho admin + xác nhận cho người dùng (bất đồng bộ)
    try:
        notify_admin_new_contact(msg)
        notify_user_contact_received(msg)
    except Exception:
        pass  # Không để lỗi email ảnh hưởng response

    return jsonify({'message': 'Tin nhắn đã được gửi thành công', 'id': msg.id}), 201


# ─────────────────────────────────────────
# Newsletter
# ─────────────────────────────────────────

@contact_bp.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    """Đăng ký nhận newsletter."""
    data  = request.get_json(silent=True) or {}
    email = str(data.get('email') or '').strip().lower()

    if not _EMAIL_RE.match(email):
        return jsonify({'error': 'Email không hợp lệ'}), 422

    existing = NewsletterSubscriber.query.filter_by(email=email).first()
    if existing:
        if existing.status == 'unsubscribed':
            existing.status = 'active'
            db.session.commit()
            return jsonify({'message': 'Đã đăng ký lại thành công'}), 200
        return jsonify({'message': 'Email đã được đăng ký'}), 200

    sub = NewsletterSubscriber(email=email[:255])
    db.session.add(sub)
    db.session.commit()
    return jsonify({'message': 'Đăng ký thành công'}), 201


@contact_bp.route('/newsletter/unsubscribe', methods=['POST'])
def newsletter_unsubscribe():
    """Hủy đăng ký newsletter."""
    data  = request.get_json(silent=True) or {}
    email = str(data.get('email') or '').strip().lower()

    sub = NewsletterSubscriber.query.filter_by(email=email).first()
    if not sub:
        return jsonify({'error': 'Email không tìm thấy'}), 404

    sub.status = 'unsubscribed'
    db.session.commit()
    return jsonify({'message': 'Đã hủy đăng ký'}), 200


# ─────────────────────────────────────────
# User: xem lịch sử liên hệ của mình
# ─────────────────────────────────────────

@contact_bp.route('/my-messages', methods=['GET'])
@jwt_required(optional=True)
def my_messages():
    """Trả về danh sách tin nhắn liên hệ mà user đã gửi, kèm phản hồi của admin (nếu có)."""
    from app.models import User
    email = None

    identity = get_jwt_identity()
    if identity:
        user = User.query.filter_by(google_id=identity).first()
        if not user:
            try:
                user = User.query.filter_by(id=int(identity)).first()
            except (TypeError, ValueError):
                user = None
        if user:
            email = user.email

    # Fallback: email từ query param
    if not email:
        email = (request.args.get('email') or '').strip().lower()

    if not email:
        return jsonify({'error': 'Cần cung cấp email'}), 400

    msgs = ContactMessage.query.filter_by(email=email)\
               .order_by(ContactMessage.created_at.desc()).all()

    return jsonify({
        'messages': [{
            'id': m.id,
            'subject': m.subject,
            'message': m.message,
            'status': m.status,
            'admin_reply': m.admin_reply,
            'replied_at': m.replied_at.isoformat() + 'Z' if m.replied_at else None,
            'created_at': m.created_at.isoformat() + 'Z' if m.created_at else None,
        } for m in msgs]
    }), 200
