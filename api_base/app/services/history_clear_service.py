"""OTP-confirmed bulk delete of user translation history."""

from __future__ import annotations

import os
from datetime import timedelta

from app.models import db, User, AuthOtp, Translation
from app.services.otp_service import (
    OTP_MAX_WRONG,
    generate_otp_code,
    hash_otp,
    otp_expired,
    utcnow,
    verify_otp_code,
)
from app.services.email_service import send_otp_email_sync

OTP_PURPOSE_CLEAR_HISTORY = 'clear_history'
CLEAR_HISTORY_OTP_TTL_MIN = int(os.getenv('CLEAR_HISTORY_OTP_TTL_MIN', '5') or 5)


def _otp_expires_at():
    return utcnow() + timedelta(minutes=CLEAR_HISTORY_OTP_TTL_MIN)


def _delete_otp_records(email: str) -> None:
    AuthOtp.query.filter_by(purpose=OTP_PURPOSE_CLEAR_HISTORY, email=email).delete(
        synchronize_session=False
    )


def request_clear_history_otp(user: User) -> tuple[bool, str, dict | None]:
    if not user or not user.email:
        return False, 'Không tìm thấy email tài khoản.', None

    _delete_otp_records(user.email)
    record = AuthOtp(
        purpose=OTP_PURPOSE_CLEAR_HISTORY,
        email=user.email,
        user_id=user.id,
        otp_hash=hash_otp('000000'),
        expires_at=_otp_expires_at(),
        wrong_attempts=0,
        resend_count=0,
        resend_window_start=utcnow(),
    )
    db.session.add(record)
    db.session.flush()

    code = generate_otp_code()
    record.otp_hash = hash_otp(code)
    ok, err = send_otp_email_sync(user.email, code, OTP_PURPOSE_CLEAR_HISTORY)
    if not ok:
        db.session.rollback()
        return False, err or 'Không gửi được email OTP.', None

    db.session.commit()
    return True, 'Mã OTP đã được gửi đến email của bạn.', {
        'expires_in_seconds': CLEAR_HISTORY_OTP_TTL_MIN * 60,
        'email': user.email,
    }


def confirm_clear_history(user: User, otp_code: str) -> tuple[bool, str, dict | None]:
    if not user or not user.email:
        return False, 'Không tìm thấy tài khoản.', None

    record = (
        AuthOtp.query.filter_by(purpose=OTP_PURPOSE_CLEAR_HISTORY, email=user.email)
        .order_by(AuthOtp.id.desc())
        .first()
    )
    if not record:
        return False, 'Chưa có yêu cầu xóa lịch sử. Vui lòng gửi OTP trước.', None

    if otp_expired(record.expires_at):
        _delete_otp_records(user.email)
        db.session.commit()
        return False, 'OTP đã hết hạn. Vui lòng gửi lại mã mới.', None

    if not verify_otp_code(otp_code, record.otp_hash):
        record.wrong_attempts = int(record.wrong_attempts or 0) + 1
        if record.wrong_attempts >= OTP_MAX_WRONG:
            _delete_otp_records(user.email)
            db.session.commit()
            return False, f'Nhập sai OTP quá {OTP_MAX_WRONG} lần. Vui lòng gửi lại OTP mới.', None
        db.session.commit()
        remaining = OTP_MAX_WRONG - int(record.wrong_attempts or 0)
        return False, f'OTP không đúng. Còn {remaining} lần thử.', None

    deleted = Translation.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    _delete_otp_records(user.email)
    db.session.commit()

    return True, f'Đã xóa {deleted} bản dịch khỏi lịch sử.', {'deleted_count': deleted}
