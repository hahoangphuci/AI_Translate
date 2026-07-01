"""OTP generation, hashing, rate limits for register & password reset."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

GMAIL_RE = re.compile(r'^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?@gmail\.com$')
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')

OTP_MAX_WRONG = 5
OTP_MAX_RESEND = 3
OTP_RESEND_WINDOW_MIN = 10
REGISTER_OTP_TTL_MIN = 5
RESET_OTP_TTL_MIN = 10
RESET_TOKEN_TTL_MIN = 15


def normalize_gmail(email: str) -> str:
    return (email or '').strip().lower()


def is_valid_gmail(email: str) -> bool:
    return bool(GMAIL_RE.match(normalize_gmail(email)))


def is_valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match((username or '').strip()))


def generate_otp_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def hash_otp(code: str) -> str:
    return generate_password_hash(str(code).strip())


def verify_otp_code(code: str, otp_hash: str) -> bool:
    if not code or not otp_hash:
        return False
    return check_password_hash(otp_hash, str(code).strip())


def utcnow() -> datetime:
    return datetime.utcnow()


def otp_expired(expires_at: datetime | None) -> bool:
    if not expires_at:
        return True
    return utcnow() >= expires_at


def resend_window_active(record, window_minutes: int = OTP_RESEND_WINDOW_MIN) -> bool:
    start = getattr(record, 'resend_window_start', None)
    if not start:
        return False
    return utcnow() < start + timedelta(minutes=window_minutes)


def can_resend(record, window_minutes: int = OTP_RESEND_WINDOW_MIN) -> tuple[bool, str | None]:
    if not resend_window_active(record, window_minutes):
        return True, None
    count = int(getattr(record, 'resend_count', 0) or 0)
    if count >= OTP_MAX_RESEND:
        return False, f'Bạn đã gửi lại mã tối đa {OTP_MAX_RESEND} lần trong {window_minutes} phút.'
    return True, None


def register_expires_at() -> datetime:
    return utcnow() + timedelta(minutes=REGISTER_OTP_TTL_MIN)


def reset_expires_at() -> datetime:
    return utcnow() + timedelta(minutes=RESET_OTP_TTL_MIN)


def reset_token_expires_at() -> datetime:
    return utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MIN)
