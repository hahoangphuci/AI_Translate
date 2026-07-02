from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

db = SQLAlchemy()


def _default_free_tokens():
    try:
        return int(os.getenv('FREE_TRIAL_TOKENS', '5000'))
    except Exception:
        return 5000


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────
class User(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    google_id     = db.Column(db.String(255), unique=True)
    username      = db.Column(db.String(50), unique=True, nullable=True)
    email         = db.Column(db.String(255), nullable=False, unique=True)
    name          = db.Column(db.String(255))
    avatar_url    = db.Column(db.String(500))
    password_hash = db.Column(db.String(255), nullable=True)   # NULL = Google-only account
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    plan          = db.Column(db.String(50),  default='free')   # free | pro | promax
    role          = db.Column(db.String(20),  default='user')   # user | admin
    token_balance = db.Column(db.Integer,     default=_default_free_tokens)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)

    # Account deletion lifecycle (active | pending_delete | deleted)
    account_status         = db.Column(db.String(20),  default='active', nullable=False)
    delete_requested_at    = db.Column(db.DateTime,    nullable=True)
    delete_scheduled_at    = db.Column(db.DateTime,    nullable=True)
    delete_reason          = db.Column(db.Text,        nullable=True)
    delete_otp             = db.Column(db.String(255), nullable=True)   # hashed OTP
    delete_otp_expires_at  = db.Column(db.DateTime,    nullable=True)
    delete_otp_verified    = db.Column(db.Boolean,     default=False, nullable=False)
    delete_otp_wrong_attempts = db.Column(db.Integer,  default=0, nullable=False)
    delete_otp_locked_until   = db.Column(db.DateTime, nullable=True)
    delete_cancelled_at    = db.Column(db.DateTime,    nullable=True)
    deleted_at             = db.Column(db.DateTime,    nullable=True)

    def __init__(
        self,
        *,
        email: str,
        name: str | None = None,
        username: str | None = None,
        google_id: str | None = None,
        avatar_url: str | None = None,
        password_hash: str | None = None,
        email_verified: bool = False,
        plan: str = 'free',
        role: str = 'user',
        token_balance: int | None = None,
        account_status: str = 'active',
    ) -> None:
        self.email = email
        self.name = name
        self.username = username
        self.google_id = google_id
        self.avatar_url = avatar_url
        self.password_hash = password_hash
        self.email_verified = email_verified
        self.plan = plan
        self.role = role
        self.account_status = account_status
        if token_balance is not None:
            self.token_balance = token_balance

    preference    = db.relationship('UserPreference', back_populates='user', uselist=False, cascade='all, delete-orphan')
    login_logs    = db.relationship('UserLoginLog',   back_populates='user', cascade='all, delete-orphan')


class AuthOtp(db.Model):
    """Pending OTP for registration or password reset."""
    __tablename__ = 'auth_otp'

    id = db.Column(db.Integer, primary_key=True)
    purpose = db.Column(db.String(20), nullable=False, index=True)  # register | password_reset
    email = db.Column(db.String(255), nullable=False, index=True)
    username = db.Column(db.String(50), nullable=True)
    name = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    otp_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    wrong_attempts = db.Column(db.Integer, default=0, nullable=False)
    resend_count = db.Column(db.Integer, default=0, nullable=False)
    resend_window_start = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# User preferences  (settings trang /profile)
# ──────────────────────────────────────────────
class UserPreference(db.Model):
    __tablename__ = 'user_preference'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    target_lang = db.Column(db.String(20),  default='vi')
    theme       = db.Column(db.String(20),  default='dark')
    font_size   = db.Column(db.String(20),  default='medium')
    ai_model    = db.Column(db.String(100), default=None)
    updated_at  = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='preference')


# ──────────────────────────────────────────────
# User login history
# ──────────────────────────────────────────────
class UserLoginLog(db.Model):
    __tablename__ = 'user_login_log'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='login_logs')


# ──────────────────────────────────────────────
# Translations  (text / document / image)
# ──────────────────────────────────────────────
class Translation(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    type            = db.Column(db.String(20),  default='text')  # text | document | image
    original_text   = db.Column(db.Text)
    translated_text = db.Column(db.Text)
    source_lang     = db.Column(db.String(20))
    target_lang     = db.Column(db.String(20))
    file_path       = db.Column(db.String(500))
    token_cost      = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# Payments
# ──────────────────────────────────────────────
class Payment(db.Model):
    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_type            = db.Column(db.String(50))   # pro | promax
    amount               = db.Column(db.Float, nullable=False)
    currency             = db.Column(db.String(10), default='VND')
    status               = db.Column(db.String(50),  default='pending')  # pending | completed | failed
    sepay_transaction_id = db.Column(db.String(255))
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# Contact messages  (form liên hệ)
# ──────────────────────────────────────────────
class ContactMessage(db.Model):
    __tablename__ = 'contact_message'
    id         = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name  = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(255), nullable=False)
    subject    = db.Column(db.String(50),  default='general')
    message    = db.Column(db.Text, nullable=False)
    status      = db.Column(db.String(20),  default='unread')  # unread | read | replied
    ip_address  = db.Column(db.String(50))
    admin_reply = db.Column(db.Text, nullable=True)   # nội dung phản hồi từ admin
    replied_at  = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# Newsletter subscribers
# ──────────────────────────────────────────────
class NewsletterSubscriber(db.Model):
    __tablename__ = 'newsletter_subscriber'
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(255), nullable=False, unique=True)
    status     = db.Column(db.String(20),  default='active')  # active | unsubscribed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ──────────────────────────────────────────────
# Admin action log  (audit trail)
# ──────────────────────────────────────────────
class AdminActionLog(db.Model):
    __tablename__ = 'admin_action_log'
    id          = db.Column(db.Integer, primary_key=True)
    admin_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action      = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))   # user | translation | payment | contact_message
    target_id   = db.Column(db.Integer)
    detail      = db.Column(db.Text)         # JSON string
    ip_address  = db.Column(db.String(50))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
