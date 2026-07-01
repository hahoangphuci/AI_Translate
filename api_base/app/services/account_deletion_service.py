"""Account deletion request, OTP confirmation, restore, and scheduled purge."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from app.models import db, User, AuthOtp
from app.services.otp_service import (
    OTP_MAX_WRONG,
    generate_otp_code,
    hash_otp,
    otp_expired,
    utcnow,
    verify_otp_code,
)
from app.services.email_service import (
    send_account_delete_admin_email,
    send_account_delete_user_email,
    send_otp_email_sync,
)

ACCOUNT_STATUS_ACTIVE = 'active'
ACCOUNT_STATUS_PENDING_DELETE = 'pending_delete'
ACCOUNT_STATUS_DELETED = 'deleted'

DELETE_GRACE_DAYS = int(os.getenv('ACCOUNT_DELETE_GRACE_DAYS', '30') or 30)
DELETE_OTP_TTL_MIN = int(os.getenv('ACCOUNT_DELETE_OTP_TTL_MIN', '5') or 5)
RESTORE_OTP_TTL_MIN = int(os.getenv('ACCOUNT_RESTORE_OTP_TTL_MIN', '5') or 5)
DELETE_OTP_LOCK_MIN = int(os.getenv('ACCOUNT_DELETE_OTP_LOCK_MIN', '15') or 15)

OTP_PURPOSE_RESTORE = 'account_restore'


def _delete_otp_expires_at() -> datetime:
    return utcnow() + timedelta(minutes=DELETE_OTP_TTL_MIN)


def _restore_otp_expires_at() -> datetime:
    return utcnow() + timedelta(minutes=RESTORE_OTP_TTL_MIN)


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return ''
    return dt.strftime('%d/%m/%Y %H:%M')


def account_status_of(user: User) -> str:
    return (getattr(user, 'account_status', None) or ACCOUNT_STATUS_ACTIVE).strip().lower()


def is_account_deleted(user: User) -> bool:
    return account_status_of(user) == ACCOUNT_STATUS_DELETED


def is_account_pending_delete(user: User) -> bool:
    return account_status_of(user) == ACCOUNT_STATUS_PENDING_DELETE


def login_block_response(user: User | None):
    """Return Flask response tuple if login must be blocked."""
    from flask import jsonify

    if not user:
        return None
    if is_account_deleted(user):
        return jsonify({
            'error': 'account_deleted',
            'message': 'Tài khoản đã bị xóa hoặc vô hiệu hóa. Không thể đăng nhập.',
        }), 403
    return None


def pending_delete_meta(user: User) -> dict:
    if not is_account_pending_delete(user):
        return {}
    meta = {'account_pending_delete': True}
    if user.delete_scheduled_at:
        meta['delete_scheduled_at'] = user.delete_scheduled_at.isoformat() + 'Z'
        meta['delete_scheduled_at_display'] = _fmt_dt(user.delete_scheduled_at)
    return meta


def _clear_delete_otp_fields(user: User) -> None:
    user.delete_otp = None
    user.delete_otp_expires_at = None
    user.delete_otp_verified = False
    user.delete_otp_wrong_attempts = 0
    user.delete_otp_locked_until = None


def _clear_delete_schedule(user: User) -> None:
    user.delete_requested_at = None
    user.delete_scheduled_at = None
    user.delete_reason = None
    user.delete_cancelled_at = None
    _clear_delete_otp_fields(user)


def _delete_restore_otp_records(email: str) -> None:
    AuthOtp.query.filter_by(purpose=OTP_PURPOSE_RESTORE, email=email).delete(synchronize_session=False)


def _is_delete_otp_locked(user: User) -> tuple[bool, str | None]:
    locked_until = getattr(user, 'delete_otp_locked_until', None)
    if locked_until and utcnow() < locked_until:
        mins = max(1, int((locked_until - utcnow()).total_seconds() // 60) + 1)
        return True, f'Bạn đã nhập sai OTP quá nhiều lần. Vui lòng thử lại sau {mins} phút.'
    if locked_until and utcnow() >= locked_until:
        user.delete_otp_locked_until = None
        user.delete_otp_wrong_attempts = 0
    return False, None


def request_account_delete(user: User, reason: str | None = None) -> tuple[bool, str, dict | None]:
    """Step 1–3: validate and send delete confirmation OTP."""
    if is_account_deleted(user):
        return False, 'Tài khoản đã bị xóa.', None
    if is_account_pending_delete(user):
        return False, 'Tài khoản đang trong thời gian chờ xóa.', None
    if (user.role or 'user') == 'admin':
        return False, 'Tài khoản quản trị viên không thể tự yêu cầu xóa qua luồng này.', None

    locked, msg = _is_delete_otp_locked(user)
    if locked:
        return False, msg or 'Tạm khóa xác nhận OTP.', None

    code = generate_otp_code()
    user.delete_otp = hash_otp(code)
    user.delete_otp_expires_at = _delete_otp_expires_at()
    user.delete_otp_verified = False
    user.delete_reason = (reason or '').strip() or None
    user.delete_otp_wrong_attempts = 0
    user.delete_otp_locked_until = None

    ok, err = send_otp_email_sync(user.email, code, 'account_delete')
    if not ok:
        db.session.rollback()
        return False, err or 'Không gửi được email OTP.', None

    db.session.commit()
    return True, 'Mã OTP đã được gửi đến email của bạn.', {
        'expires_in_seconds': DELETE_OTP_TTL_MIN * 60,
        'email': user.email,
    }


def confirm_account_delete(user: User, otp_code: str) -> tuple[bool, str, dict | None]:
    """Step 4–8: verify OTP and mark account pending_delete."""
    if is_account_deleted(user):
        return False, 'Tài khoản đã bị xóa.', None
    if is_account_pending_delete(user):
        return False, 'Yêu cầu xóa đã được ghi nhận trước đó.', None

    locked, msg = _is_delete_otp_locked(user)
    if locked:
        return False, msg or 'Tạm khóa xác nhận OTP.', None

    if not user.delete_otp or user.delete_otp_verified:
        return False, 'Chưa có yêu cầu xóa hoặc OTP đã được sử dụng. Vui lòng gửi lại OTP.', None

    if otp_expired(user.delete_otp_expires_at):
        _clear_delete_otp_fields(user)
        db.session.commit()
        return False, 'OTP đã hết hạn. Vui lòng gửi lại mã mới.', None

    if not verify_otp_code(otp_code, user.delete_otp):
        user.delete_otp_wrong_attempts = int(user.delete_otp_wrong_attempts or 0) + 1
        if user.delete_otp_wrong_attempts >= OTP_MAX_WRONG:
            user.delete_otp_locked_until = utcnow() + timedelta(minutes=DELETE_OTP_LOCK_MIN)
            user.delete_otp_wrong_attempts = 0
            db.session.commit()
            return False, f'Nhập sai OTP quá {OTP_MAX_WRONG} lần. Tạm khóa {DELETE_OTP_LOCK_MIN} phút.', None
        db.session.commit()
        remaining = OTP_MAX_WRONG - int(user.delete_otp_wrong_attempts or 0)
        return False, f'OTP không đúng. Còn {remaining} lần thử.', None

    now = utcnow()
    scheduled = now + timedelta(days=DELETE_GRACE_DAYS)

    user.account_status = ACCOUNT_STATUS_PENDING_DELETE
    user.delete_requested_at = now
    user.delete_scheduled_at = scheduled
    user.delete_otp_verified = True
    user.delete_otp = None
    user.delete_otp_expires_at = None
    user.delete_otp_wrong_attempts = 0
    user.delete_otp_locked_until = None

    db.session.commit()

    send_account_delete_user_email(user)
    send_account_delete_admin_email(user)

    return True, 'Yêu cầu xóa tài khoản đã được ghi nhận.', {
        'account_status': user.account_status,
        'delete_requested_at': user.delete_requested_at.isoformat() + 'Z',
        'delete_scheduled_at': user.delete_scheduled_at.isoformat() + 'Z',
        'delete_scheduled_at_display': _fmt_dt(user.delete_scheduled_at),
    }


def request_account_restore(user: User) -> tuple[bool, str, dict | None]:
    """Send OTP to confirm account restoration."""
    if not is_account_pending_delete(user):
        return False, 'Tài khoản không ở trạng thái chờ xóa.', None

    _delete_restore_otp_records(user.email)
    record = AuthOtp(
        purpose=OTP_PURPOSE_RESTORE,
        email=user.email,
        user_id=user.id,
        otp_hash=hash_otp('000000'),
        expires_at=_restore_otp_expires_at(),
        wrong_attempts=0,
        resend_count=0,
        resend_window_start=utcnow(),
    )
    db.session.add(record)
    db.session.flush()

    code = generate_otp_code()
    record.otp_hash = hash_otp(code)
    ok, err = send_otp_email_sync(user.email, code, 'account_restore')
    if not ok:
        db.session.rollback()
        return False, err or 'Không gửi được email OTP.', None

    db.session.commit()
    return True, 'Mã OTP khôi phục đã được gửi đến email của bạn.', {
        'expires_in_seconds': RESTORE_OTP_TTL_MIN * 60,
        'email': user.email,
    }


def confirm_account_restore(user: User, otp_code: str) -> tuple[bool, str, dict | None]:
    """Verify restore OTP and reactivate account."""
    if not is_account_pending_delete(user):
        return False, 'Tài khoản không ở trạng thái chờ xóa.', None

    record = (
        AuthOtp.query.filter_by(purpose=OTP_PURPOSE_RESTORE, email=user.email)
        .order_by(AuthOtp.id.desc())
        .first()
    )
    if not record:
        return False, 'Chưa có yêu cầu khôi phục. Vui lòng gửi OTP trước.', None

    if otp_expired(record.expires_at):
        _delete_restore_otp_records(user.email)
        db.session.commit()
        return False, 'OTP đã hết hạn. Vui lòng gửi lại mã mới.', None

    if not verify_otp_code(otp_code, record.otp_hash):
        record.wrong_attempts = int(record.wrong_attempts or 0) + 1
        if record.wrong_attempts >= OTP_MAX_WRONG:
            _delete_restore_otp_records(user.email)
            db.session.commit()
            return False, f'Nhập sai OTP quá {OTP_MAX_WRONG} lần. Vui lòng gửi lại OTP mới.', None
        db.session.commit()
        remaining = OTP_MAX_WRONG - int(record.wrong_attempts or 0)
        return False, f'OTP không đúng. Còn {remaining} lần thử.', None

    now = utcnow()
    user.account_status = ACCOUNT_STATUS_ACTIVE
    user.delete_cancelled_at = now
    _clear_delete_schedule(user)
    _delete_restore_otp_records(user.email)
    db.session.commit()

    return True, 'Tài khoản đã được khôi phục thành công.', {
        'account_status': user.account_status,
        'delete_cancelled_at': now.isoformat() + 'Z',
    }


def finalize_scheduled_deletions() -> int:
    """Mark overdue pending_delete accounts as deleted. Returns count processed."""
    now = utcnow()
    users = User.query.filter(
        User.account_status == ACCOUNT_STATUS_PENDING_DELETE,
        User.delete_scheduled_at.isnot(None),
        User.delete_scheduled_at <= now,
    ).all()

    count = 0
    for user in users:
        user.account_status = ACCOUNT_STATUS_DELETED
        user.deleted_at = now
        user.password_hash = None
        _clear_delete_otp_fields(user)
        count += 1

    if count:
        db.session.commit()
    return count
