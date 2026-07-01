"""
Admin router — /api/admin/*
All endpoints require JWT + role == 'admin'.
Admin inherits all user capabilities and additionally manages the system.
"""
import json
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from app.models import (
    db, User, Translation, Payment,
    ContactMessage, NewsletterSubscriber,
    AdminActionLog, UserLoginLog,
)
from app.security.security import admin_required

admin_bp = Blueprint('admin', __name__)


# ─────────────────────────────────────────
# Helper
# ─────────────────────────────────────────

def _get_admin_id():
    """Lấy admin_id từ JWT identity."""
    identity = get_jwt_identity()
    admin = User.query.filter_by(google_id=identity).first()
    if not admin:
        try:
            admin = User.query.get(int(identity))
        except (TypeError, ValueError):
            pass
    return admin.id if admin else None

def _serialize_user(u):
    return {
        'id': u.id,
        'google_id': u.google_id,
        'email': u.email,
        'name': u.name,
        'avatar_url': u.avatar_url,
        'plan': u.plan or 'free',
        'role': u.role or 'user',
        'token_balance': int(u.token_balance or 0),
        'created_at': u.created_at.isoformat() + 'Z' if u.created_at else None,
    }


def _serialize_payment(p):
    return {
        'id': p.id,
        'user_id': p.user_id,
        'amount': float(p.amount or 0),
        'currency': p.currency,
        'status': p.status,
        'sepay_transaction_id': p.sepay_transaction_id,
        'created_at': p.created_at.isoformat() + 'Z' if p.created_at else None,
    }


def _serialize_translation(t):
    return {
        'id': t.id,
        'user_id': t.user_id,
        'source_lang': t.source_lang,
        'target_lang': t.target_lang,
        'original_text': (t.original_text or '')[:300],
        'translated_text': (t.translated_text or '')[:300],
        'has_file': bool(t.file_path),
        'created_at': t.created_at.isoformat() + 'Z' if t.created_at else None,
    }


# ─────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────

def _active_users_query():
    """Users that still exist in the system (exclude permanently deleted accounts)."""
    return User.query.filter(User.account_status != 'deleted')


def _plan_distribution_counts() -> dict:
    """Count users by plan; buckets are mutually exclusive and sum to active users."""
    plan_counts = {'free': 0, 'pro': 0, 'promax': 0}
    rows = (
        db.session.query(func.lower(User.plan), func.count(User.id))
        .filter(User.account_status != 'deleted')
        .group_by(func.lower(User.plan))
        .all()
    )
    for plan, cnt in rows:
        key = (plan or 'free').strip().lower()
        if key in plan_counts:
            plan_counts[key] += int(cnt or 0)
        else:
            plan_counts['free'] += int(cnt or 0)
    return plan_counts


def _chart_series_last_days(days: int = 7):
    """Số liệu theo ngày cho biểu đồ admin (7 ngày gần nhất)."""
    days = max(1, min(int(days or 7), 30))
    today = datetime.utcnow().date()
    labels = []
    translations = []
    users = []
    revenue = []

    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        labels.append(day.strftime('%d/%m'))

        translations.append(
            Translation.query.filter(func.date(Translation.created_at) == day).count()
        )
        users.append(
            _active_users_query().filter(func.date(User.created_at) == day).count()
        )
        rev = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.status == 'completed',
            func.date(Payment.created_at) == day,
        ).scalar()
        revenue.append(float(rev or 0))

    return {
        'labels': labels,
        'translations_per_day': translations,
        'users_per_day': users,
        'revenue_per_day': revenue,
    }


@admin_bp.route('/stats', methods=['GET'])
@admin_required
def admin_stats():
    """Tổng quan hệ thống."""
    active_users = _active_users_query()
    total_users = active_users.count()
    total_translations = Translation.query.count()
    total_payments = Payment.query.count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    admin_count = active_users.filter(User.role == 'admin').count()
    member_count = active_users.filter(User.role != 'admin').count()
    plan_counts = _plan_distribution_counts()
    charts = _chart_series_last_days(7)
    charts['plan_distribution'] = plan_counts
    return jsonify({
        'total_users': total_users,
        'admin_count': admin_count,
        'member_count': member_count,
        'total_translations': total_translations,
        'total_payments': total_payments,
        'total_revenue_vnd': float(total_revenue),
        'plan_distribution': plan_counts,
        'role_distribution': {
            'admin': admin_count,
            'member': member_count,
        },
        'charts': charts,
    }), 200


# ─────────────────────────────────────────
# User management
# ─────────────────────────────────────────

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    """Danh sách tất cả người dùng (phân trang)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    search = (request.args.get('q') or '').strip()
    role_filter = (request.args.get('role') or '').strip().lower()
    plan_filter = (request.args.get('plan') or '').strip().lower()

    q = User.query
    if search:
        like = f'%{search}%'
        q = q.filter(db.or_(User.email.ilike(like), User.name.ilike(like)))
    if role_filter in ('user', 'admin'):
        q = q.filter(User.role == role_filter)
    if plan_filter in ('free', 'pro', 'promax'):
        q = q.filter(User.plan == plan_filter)

    q = q.order_by(User.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'users': [_serialize_user(u) for u in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
    }), 200


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """Chi tiết một user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(_serialize_user(user)), 200


@admin_bp.route('/users/<int:user_id>', methods=['PATCH'])
@admin_required
def update_user(user_id):
    """
    Cập nhật user: name, plan, role, token_balance.
    Admin không thể tự hạ cấp role của chính mình.
    """
    admin_google_id = get_jwt_identity()
    admin_self = User.query.filter_by(google_id=admin_google_id).first()

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(silent=True) or {}

    if 'name' in data:
        name = str(data['name']).strip()
        if len(name) > 255:
            return jsonify({'error': 'Name too long'}), 400
        user.name = name

    if 'plan' in data:
        plan = str(data['plan']).strip().lower()
        if plan not in ('free', 'pro', 'promax'):
            return jsonify({'error': 'Invalid plan. Choose: free, pro, promax'}), 400
        user.plan = plan

    if 'role' in data:
        role = str(data['role']).strip().lower()
        if role not in ('user', 'admin'):
            return jsonify({'error': 'Invalid role. Choose: user, admin'}), 400
        # Prevent admin from demoting themselves
        if admin_self and admin_self.id == user.id and role != 'admin':
            return jsonify({'error': 'Cannot remove your own admin role'}), 400
        user.role = role

    if 'token_balance' in data:
        try:
            bal = int(data['token_balance'])
            if bal < 0:
                return jsonify({'error': 'token_balance must be >= 0'}), 400
            user.token_balance = bal
        except (ValueError, TypeError):
            return jsonify({'error': 'token_balance must be an integer'}), 400

    db.session.commit()
    _log_admin_action(_get_admin_id(), 'update_user', 'user', user.id,
                      {k: data[k] for k in ('name','plan','role','token_balance') if k in data})
    return jsonify(_serialize_user(user)), 200


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Xóa user và toàn bộ dữ liệu liên quan."""
    admin_google_id = get_jwt_identity()
    admin_self = User.query.filter_by(google_id=admin_google_id).first()

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if admin_self and admin_self.id == user.id:
        return jsonify({'error': 'Cannot delete your own admin account'}), 400

    _log_admin_action(_get_admin_id(), 'delete_user', 'user', user.id,
                      {'email': user.email, 'name': user.name})
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {user_id} deleted'}), 200


@admin_bp.route('/users/<int:user_id>/grant-admin', methods=['POST'])
@admin_required
def grant_admin(user_id):
    """Cấp quyền admin cho user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user.role = 'admin'
    db.session.commit()
    _log_admin_action(_get_admin_id(), 'grant_admin', 'user', user.id,
                      {'email': user.email})
    return jsonify({'message': f'Granted admin to user {user_id}', 'user': _serialize_user(user)}), 200


@admin_bp.route('/users/<int:user_id>/revoke-admin', methods=['POST'])
@admin_required
def revoke_admin(user_id):
    """Thu hồi quyền admin của user."""
    identity = get_jwt_identity()
    admin_self = User.query.filter_by(google_id=identity).first()
    if not admin_self:
        try:
            admin_self = User.query.get(int(identity))
        except (TypeError, ValueError):
            pass

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if admin_self and admin_self.id == user.id:
        return jsonify({'error': 'Cannot revoke your own admin role'}), 400
    user.role = 'user'
    db.session.commit()
    _log_admin_action(_get_admin_id(), 'revoke_admin', 'user', user.id,
                      {'email': user.email})
    return jsonify({'message': f'Revoked admin from user {user_id}', 'user': _serialize_user(user)}), 200


# ─────────────────────────────────────────
# Translation management
# ─────────────────────────────────────────

@admin_bp.route('/translations', methods=['GET'])
@admin_required
def list_translations():
    """Danh sách tất cả bản dịch (phân trang)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    user_id = request.args.get('user_id', type=int)

    q = Translation.query
    if user_id:
        q = q.filter(Translation.user_id == user_id)
    q = q.order_by(Translation.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'translations': [_serialize_translation(t) for t in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
    }), 200


@admin_bp.route('/translations/<int:translation_id>', methods=['DELETE'])
@admin_required
def delete_translation(translation_id):
    """Xóa một bản dịch bất kỳ."""
    t = Translation.query.get(translation_id)
    if not t:
        return jsonify({'error': 'Translation not found'}), 404
    _log_admin_action(_get_admin_id(), 'delete_translation', 'translation', translation_id, {})
    db.session.delete(t)
    db.session.commit()
    return jsonify({'message': f'Translation {translation_id} deleted'}), 200


# ─────────────────────────────────────────
# Payment management
# ─────────────────────────────────────────

@admin_bp.route('/payments', methods=['GET'])
@admin_required
def list_payments():
    """Danh sách tất cả thanh toán (phân trang, lọc theo status)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status_filter = (request.args.get('status') or '').strip().lower()
    user_id = request.args.get('user_id', type=int)

    q = Payment.query
    if status_filter in ('pending', 'completed', 'failed'):
        q = q.filter(Payment.status == status_filter)
    if user_id:
        q = q.filter(Payment.user_id == user_id)
    q = q.order_by(Payment.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'payments': [_serialize_payment(p) for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
    }), 200


@admin_bp.route('/payments/<int:payment_id>', methods=['PATCH'])
@admin_required
def update_payment(payment_id):
    """Cập nhật trạng thái payment thủ công."""
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({'error': 'Payment not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'status' in data:
        status = str(data['status']).strip().lower()
        if status not in ('pending', 'completed', 'failed'):
            return jsonify({'error': 'Invalid status'}), 400
        payment.status = status

    db.session.commit()
    _log_admin_action(_get_admin_id(), 'update_payment', 'payment', payment_id,
                      {'status': data.get('status')})
    return jsonify(_serialize_payment(payment)), 200


# ─────────────────────────────────────────
# Contact messages management
# ─────────────────────────────────────────

def _serialize_contact(c):
    return {
        'id': c.id,
        'first_name': c.first_name,
        'last_name': c.last_name,
        'email': c.email,
        'subject': c.subject,
        'message': c.message,
        'status': c.status,
        'ip_address': c.ip_address,
        'admin_reply': c.admin_reply,
        'replied_at': c.replied_at.isoformat() + 'Z' if c.replied_at else None,
        'created_at': c.created_at.isoformat() + 'Z' if c.created_at else None,
    }


@admin_bp.route('/contacts/<int:contact_id>', methods=['GET'])
@admin_required
def get_contact(contact_id):
    """Lấy chi tiết một tin nhắn liên hệ."""
    msg = ContactMessage.query.get(contact_id)
    if not msg:
        return jsonify({'error': 'Contact message not found'}), 404
    # Đánh dấu 'read' nếu đang là 'unread'
    if msg.status == 'unread':
        msg.status = 'read'
        db.session.commit()
    return jsonify(_serialize_contact(msg)), 200


@admin_bp.route('/contacts', methods=['GET'])
@admin_required
def list_contacts():
    """Danh sách tin nhắn liên hệ."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status_filter = (request.args.get('status') or '').strip().lower()

    q = ContactMessage.query
    if status_filter in ('unread', 'read', 'replied'):
        q = q.filter(ContactMessage.status == status_filter)
    q = q.order_by(ContactMessage.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'contacts': [_serialize_contact(c) for c in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'unread_count': ContactMessage.query.filter_by(status='unread').count(),
    }), 200


@admin_bp.route('/contacts/<int:contact_id>', methods=['PATCH'])
@admin_required
def update_contact(contact_id):
    """Cập nhật trạng thái tin nhắn liên hệ (unread → read → replied)."""
    msg = ContactMessage.query.get(contact_id)
    if not msg:
        return jsonify({'error': 'Contact message not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'status' in data:
        status = str(data['status']).strip().lower()
        if status not in ('unread', 'read', 'replied'):
            return jsonify({'error': 'Invalid status'}), 400
        msg.status = status

    db.session.commit()
    return jsonify(_serialize_contact(msg)), 200


@admin_bp.route('/contacts/<int:contact_id>', methods=['DELETE'])
@admin_required
def delete_contact(contact_id):
    """Xóa tin nhắn liên hệ."""
    msg = ContactMessage.query.get(contact_id)
    if not msg:
        return jsonify({'error': 'Contact message not found'}), 404
    db.session.delete(msg)
    db.session.commit()
    _log_admin_action(_get_admin_id(), 'delete_contact', 'contact_message', contact_id, {})
    return jsonify({'message': f'Contact message {contact_id} deleted'}), 200


@admin_bp.route('/contacts/<int:contact_id>/reply', methods=['POST'])
@admin_required
def reply_contact(contact_id):
    """Gửi email trả lời tới người dùng và đánh dấu 'replied'."""
    msg = ContactMessage.query.get(contact_id)
    if not msg:
        return jsonify({'error': 'Contact message not found'}), 404

    data = request.get_json(silent=True) or {}
    reply_text = str(data.get('reply') or '').strip()
    if not reply_text:
        return jsonify({'error': 'Nội dung trả lời không được để trống'}), 400

    from datetime import datetime as _dt
    msg.admin_reply = reply_text
    msg.status = 'replied'
    msg.replied_at = _dt.utcnow()
    db.session.commit()

    _log_admin_action(_get_admin_id(), 'reply_contact', 'contact_message', contact_id,
                      {'email': msg.email, 'subject': msg.subject})

    # Gửi email phản hồi cho người dùng
    try:
        from app.services.email_service import send_admin_reply
        send_admin_reply(msg, reply_text)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'[reply email] {e}')

    return jsonify(_serialize_contact(msg)), 200


# ─────────────────────────────────────────
# Newsletter management
# ─────────────────────────────────────────

@admin_bp.route('/newsletter', methods=['GET'])
@admin_required
def list_newsletter():
    """Danh sách người đăng ký newsletter."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    status_filter = (request.args.get('status') or 'active').strip().lower()

    q = NewsletterSubscriber.query
    if status_filter in ('active', 'unsubscribed'):
        q = q.filter(NewsletterSubscriber.status == status_filter)
    q = q.order_by(NewsletterSubscriber.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'subscribers': [
            {
                'id': s.id,
                'email': s.email,
                'status': s.status,
                'created_at': s.created_at.isoformat() + 'Z' if s.created_at else None,
            }
            for s in pagination.items
        ],
        'total': pagination.total,
        'active_count': NewsletterSubscriber.query.filter_by(status='active').count(),
    }), 200


# ─────────────────────────────────────────
# User login history
# ─────────────────────────────────────────

@admin_bp.route('/users/<int:user_id>/logins', methods=['GET'])
@admin_required
def user_login_history(user_id):
    """Lịch sử đăng nhập của một user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    pagination = (
        UserLoginLog.query
        .filter_by(user_id=user_id)
        .order_by(UserLoginLog.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        'logs': [
            {
                'id': l.id,
                'ip_address': l.ip_address,
                'user_agent': l.user_agent,
                'created_at': l.created_at.isoformat() + 'Z' if l.created_at else None,
            }
            for l in pagination.items
        ],
        'total': pagination.total,
    }), 200


# ─────────────────────────────────────────
# Admin audit log
# ─────────────────────────────────────────

@admin_bp.route('/audit-log', methods=['GET'])
@admin_required
def list_audit_log():
    """Lịch sử hành động của tất cả admin."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 30, type=int), 100)
    admin_id = request.args.get('admin_id', type=int)

    q = AdminActionLog.query
    if admin_id:
        q = q.filter(AdminActionLog.admin_id == admin_id)
    q = q.order_by(AdminActionLog.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'logs': [
            {
                'id': l.id,
                'admin_id': l.admin_id,
                'admin_email': User.query.get(l.admin_id).email if User.query.get(l.admin_id) else '—',
                'action': l.action,
                'target_type': l.target_type,
                'target_id': l.target_id,
                'detail': l.detail,
                'ip_address': l.ip_address,
                'created_at': l.created_at.isoformat() + 'Z' if l.created_at else None,
            }
            for l in pagination.items
        ],
        'total': pagination.total,
        'pages': pagination.pages,
    }), 200


# ─── Site / policy config (JSON + HTML files, no DB) ─────────

@admin_bp.route('/site-config', methods=['GET'])
@jwt_required()
@admin_required
def get_site_config():
    from app.services.site_config_service import load_site_config, list_legal_pages
    return jsonify({
        'config': load_site_config(),
        'legal_pages': list_legal_pages(),
    }), 200


@admin_bp.route('/site-config', methods=['PUT'])
@jwt_required()
@admin_required
def put_site_config():
    from app.services.site_config_service import update_site_config
    data = request.get_json(silent=True) or {}
    ok, message, meta = update_site_config(data)
    if not ok:
        return jsonify({'message': message}), 400
    _log_admin_action(
        _get_admin_id(),
        'site_config_update',
        target_type='site_config',
        detail={'html_files_updated': (meta or {}).get('html_files_updated')},
    )
    return jsonify({'message': message, **(meta or {})}), 200


@admin_bp.route('/site-config/pages/<slug>', methods=['GET'])
@jwt_required()
@admin_required
def get_site_config_page(slug):
    from app.services.site_config_service import get_legal_page_content
    lang = request.args.get('lang', 'vi')
    ok, message, meta = get_legal_page_content(slug, lang=lang)
    if not ok:
        return jsonify({'message': message}), 404
    return jsonify(meta), 200


@admin_bp.route('/site-config/pages/<slug>', methods=['PUT'])
@jwt_required()
@admin_required
def put_site_config_page(slug):
    from app.services.site_config_service import save_legal_page_content
    data = request.get_json(silent=True) or {}
    content = data.get('content', '')
    lang = data.get('lang', 'vi')
    ok, message = save_legal_page_content(slug, content, lang=lang)
    if not ok:
        return jsonify({'message': message}), 400
    _log_admin_action(
        _get_admin_id(),
        'legal_page_update',
        target_type='legal_page',
        target_id=slug,
    )
    return jsonify({'message': message, 'slug': slug}), 200


@admin_bp.route('/translation-config', methods=['GET'])
@jwt_required()
@admin_required
def get_translation_config():
    from app.services.translation_config_service import admin_translation_config
    return jsonify({'config': admin_translation_config()}), 200


@admin_bp.route('/translation-config', methods=['PUT'])
@jwt_required()
@admin_required
def put_translation_config():
    from app.services.translation_config_service import update_translation_config
    data = request.get_json(silent=True) or {}
    ok, message, meta = update_translation_config(data)
    if not ok:
        return jsonify({'message': message}), 400
    _log_admin_action(
        _get_admin_id(),
        'translation_config_update',
        target_type='translation_config',
    )
    return jsonify({'message': message, **(meta or {})}), 200


def _log_admin_action(admin_id, action, target_type=None, target_id=None, detail=None):
    """Helper: ghi audit log sau mỗi hành động admin quan trọng."""
    try:
        ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
              or request.remote_addr or None)
        log = AdminActionLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
            ip_address=ip,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        pass
