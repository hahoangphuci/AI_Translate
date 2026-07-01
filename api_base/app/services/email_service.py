"""
Email service — gửi thông báo bất đồng bộ (non-blocking).
Dùng smtplib thuần (không cần package thêm).
Cấu hình qua biến môi trường:
    ADMIN_EMAIL    — địa chỉ nhận thông báo (bắt buộc)
    SMTP_HOST      — default: smtp.gmail.com
    SMTP_PORT      — default: 587
    SMTP_USER      — tài khoản Gmail / SMTP
    SMTP_PASSWORD  — App Password (Gmail: myaccount.google.com/apppasswords)
    SMTP_FROM      — tên hiển thị / địa chỉ gửi, mặc định = SMTP_USER
    SMTP_USE_TLS   — default: true (STARTTLS port 587)
"""
import smtplib
import threading
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from flask import current_app

logger = logging.getLogger(__name__)


def _get_cfg():
    cfg = current_app.config
    return {
        'admin_email':  cfg.get('ADMIN_EMAIL'),
        'smtp_host':    cfg.get('SMTP_HOST', 'smtp.gmail.com'),
        'smtp_port':    int(cfg.get('SMTP_PORT', 587) or 587),
        'smtp_user':    cfg.get('SMTP_USER'),
        'smtp_password':cfg.get('SMTP_PASSWORD'),
        'smtp_from':    cfg.get('SMTP_FROM') or cfg.get('SMTP_USER'),
        'smtp_use_tls': cfg.get('SMTP_USE_TLS', True),
    }


def _send_raw(subject: str, html_body: str, to: str, cfg: dict):
    """Gửi email đồng bộ. Được gọi trong thread riêng."""
    if not cfg.get('smtp_user') or not cfg.get('smtp_password'):
        logger.warning('[email] SMTP chưa được cấu hình, bỏ qua gửi email.')
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = formataddr(('AI Translator', cfg['smtp_from']))
    msg['To']      = to
    msg['Date']    = formatdate(localtime=True)
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        if cfg['smtp_use_tls']:
            server = smtplib.SMTP(cfg['smtp_host'], cfg['smtp_port'], timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(cfg['smtp_host'], cfg['smtp_port'], timeout=10)

        server.login(cfg['smtp_user'], cfg['smtp_password'])
        server.sendmail(cfg['smtp_from'], [to], msg.as_bytes())
        server.quit()
        logger.info(f'[email] Đã gửi email tới {to}')
    except Exception:
        logger.error('[email] Gửi thất bại.')
        raise


def send_async(subject: str, html_body: str, to: str, cfg: dict):
    """Gửi email trong thread nền — không làm chậm response."""
    t = threading.Thread(target=_send_raw, args=(subject, html_body, to, cfg), daemon=True)
    t.start()


def send_sync(subject: str, html_body: str, to: str, cfg: dict | None = None) -> tuple[bool, str]:
    """Gửi email đồng bộ — trả (ok, error_message). Không log nội dung nhạy cảm."""
    cfg = cfg or _get_cfg()
    if not cfg.get('smtp_user') or not cfg.get('smtp_password'):
        return False, 'Chưa cấu hình SMTP (SMTP_USER / SMTP_PASSWORD trong .env).'
    try:
        _send_raw(subject, html_body, to, cfg)
        return True, ''
    except Exception as e:
        logger.error('[email] Gửi OTP thất bại (chi tiết không ghi nội dung nhạy cảm).')
        return False, 'Không gửi được email. Vui lòng thử lại sau.'


def send_otp_email_sync(to: str, otp_code: str, purpose: str) -> tuple[bool, str]:
    """Gửi mã OTP 6 số — đồng bộ, không log OTP."""
    cfg = _get_cfg()
    purpose = (purpose or '').strip().lower()
    if purpose == 'register':
        title = 'Xác thực đăng ký tài khoản'
        intro = 'Mã OTP để hoàn tất đăng ký tài khoản AI Translator của bạn:'
        ttl = '5 phút'
    elif purpose == 'account_delete':
        title = 'Xác nhận yêu cầu xóa tài khoản'
        intro = 'Mã OTP để xác nhận yêu cầu xóa tài khoản AI Translator của bạn:'
        ttl = '5 phút'
    elif purpose == 'account_restore':
        title = 'Xác nhận khôi phục tài khoản'
        intro = 'Mã OTP để khôi phục tài khoản AI Translator của bạn:'
        ttl = '5 phút'
    elif purpose == 'clear_history':
        title = 'Xác nhận xóa lịch sử dịch'
        intro = 'Mã OTP để xác nhận xóa toàn bộ lịch sử dịch AI Translator của bạn:'
        ttl = '5 phút'
    elif purpose == 'password_reset':
        title = 'Khôi phục mật khẩu'
        intro = 'Mã OTP để đặt lại mật khẩu tài khoản AI Translator của bạn:'
        ttl = '10 phút'
    else:
        title = 'Khôi phục mật khẩu'
        intro = 'Mã OTP để đặt lại mật khẩu tài khoản AI Translator của bạn:'
        ttl = '10 phút'

    html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:30px 10px;">
    <table width="520" cellpadding="0" cellspacing="0"
           style="background:#0e1a2b;border-radius:12px;border:1px solid #1e3a5f;">
      <tr><td style="background:linear-gradient(135deg,#007a63,#005fa3);padding:24px 28px;text-align:center;">
        <h1 style="margin:0;color:#00ffd1;font-size:20px;">{title}</h1>
      </td></tr>
      <tr><td style="padding:28px;color:#cfe8f0;font-size:15px;line-height:1.7;">
        <p>{intro}</p>
        <p style="text-align:center;margin:24px 0;">
          <span style="display:inline-block;background:#07161a;border:2px solid #00ffd1;
                       border-radius:10px;padding:16px 28px;font-size:28px;letter-spacing:8px;
                       color:#00ffd1;font-weight:bold;">{otp_code}</span>
        </p>
        <p style="color:#7ecfb3;font-size:13px;">Mã có hiệu lực trong <strong>{ttl}</strong>.
           Không chia sẻ mã này với bất kỳ ai.</p>
      </td></tr>
      <tr><td style="background:#07161a;padding:14px;text-align:center;">
        <p style="margin:0;color:#4a6a7a;font-size:11px;">AI Translator · Email tự động</p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""

    return send_sync(f'[AI Translator] {title}', html, to, cfg)


# ─────────────────────────────────────────
# Email templates
# ─────────────────────────────────────────

def notify_admin_new_contact(contact_msg) -> None:
    """
    Gửi thông báo cho admin khi có tin nhắn liên hệ mới.
    Gọi bên trong request context (có current_app).
    """
    cfg = _get_cfg()
    admin_email = cfg.get('admin_email')
    if not admin_email:
        return

    subject_map = {
        'general':     'Câu hỏi chung',
        'technical':   'Hỗ trợ kỹ thuật',
        'billing':     'Thanh toán & Gói dịch vụ',
        'partnership': 'Hợp tác kinh doanh',
        'other':       'Khác',
    }
    subject_label = subject_map.get(contact_msg.subject, contact_msg.subject)
    created = contact_msg.created_at.strftime('%d/%m/%Y %H:%M') if contact_msg.created_at else ''

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:30px 10px;">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#0e1a2b;border-radius:12px;overflow:hidden;border:1px solid #1e3a5f;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#007a63,#005fa3);padding:24px 32px;">
            <h1 style="margin:0;color:#00ffd1;font-size:20px;letter-spacing:1px;">
              📬 Tin nhắn liên hệ mới
            </h1>
            <p style="margin:6px 0 0;color:#a0c4d8;font-size:13px;">{created}</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px;">

            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:0 0 16px;">
                  <span style="color:#7ecfb3;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Người gửi</span><br>
                  <span style="color:#e8f4f8;font-size:16px;font-weight:bold;">
                    {contact_msg.first_name} {contact_msg.last_name}
                  </span>
                </td>
              </tr>
              <tr>
                <td style="padding:0 0 16px;">
                  <span style="color:#7ecfb3;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Email</span><br>
                  <a href="mailto:{contact_msg.email}"
                     style="color:#00a8ff;font-size:15px;text-decoration:none;">{contact_msg.email}</a>
                </td>
              </tr>
              <tr>
                <td style="padding:0 0 16px;">
                  <span style="color:#7ecfb3;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Chủ đề</span><br>
                  <span style="color:#e8f4f8;font-size:15px;">{subject_label}</span>
                </td>
              </tr>
              <tr>
                <td style="padding:0 0 8px;">
                  <span style="color:#7ecfb3;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Nội dung</span>
                </td>
              </tr>
              <tr>
                <td style="background:#0b0f1a;border-left:3px solid #00ffd1;
                           padding:16px 20px;border-radius:0 8px 8px 0;">
                  <p style="margin:0;color:#cfe8f0;font-size:15px;line-height:1.7;
                             white-space:pre-wrap;">{contact_msg.message}</p>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#07161a;padding:16px 32px;text-align:center;">
            <a href="mailto:{contact_msg.email}?subject=Re: {subject_label}"
               style="display:inline-block;background:#00ffd1;color:#0b0f1a;
                      padding:10px 28px;border-radius:6px;text-decoration:none;
                      font-weight:bold;font-size:14px;margin-right:8px;">
              ↩ Trả lời ngay
            </a>
            <p style="margin:12px 0 0;color:#4a6a7a;font-size:11px;">
              AI Translator · Hệ thống tự động gửi thông báo
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    send_async(
        subject=f'[Liên hệ mới] {contact_msg.first_name} {contact_msg.last_name} — {subject_label}',
        html_body=html,
        to=admin_email,
        cfg=cfg,
    )


def notify_user_contact_received(contact_msg) -> None:
    """
    Gửi email xác nhận cho người dùng vừa liên hệ (tùy chọn).
    Chỉ gửi nếu SMTP được cấu hình.
    """
    cfg = _get_cfg()
    if not cfg.get('smtp_user') or not cfg.get('smtp_password'):
        return

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:30px 10px;">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#0e1a2b;border-radius:12px;overflow:hidden;border:1px solid #1e3a5f;">
        <tr>
          <td style="background:linear-gradient(135deg,#007a63,#005fa3);padding:28px 32px;text-align:center;">
            <h1 style="margin:0;color:#00ffd1;font-size:22px;">✅ Chúng tôi đã nhận được tin nhắn!</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;color:#cfe8f0;font-size:15px;line-height:1.8;">
            <p>Xin chào <strong style="color:#00ffd1;">{contact_msg.first_name}</strong>,</p>
            <p>Cảm ơn bạn đã liên hệ với chúng tôi. Chúng tôi đã nhận được tin nhắn của bạn
               và sẽ phản hồi trong vòng <strong>24 giờ làm việc</strong>.</p>
            <p style="color:#7ecfb3;font-size:13px;font-style:italic;">
              "Nếu bạn cần hỗ trợ khẩn cấp, vui lòng reply trực tiếp email này."
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#07161a;padding:14px 32px;text-align:center;">
            <p style="margin:0;color:#4a6a7a;font-size:11px;">
              AI Translator · Đừng trả lời email này nếu bạn không liên hệ
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    send_async(
        subject='[AI Translator] Chúng tôi đã nhận được tin nhắn của bạn',
        html_body=html,
        to=contact_msg.email,
        cfg=cfg,
    )


def send_admin_reply(contact_msg, reply_text: str) -> None:
    """
    Gửi email phản hồi từ admin tới người dùng.
    """
    cfg = _get_cfg()
    if not cfg.get('smtp_user') or not cfg.get('smtp_password'):
        return

    original_preview = (contact_msg.message or '')[:300]
    if len(contact_msg.message or '') > 300:
        original_preview += '…'

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:30px 10px;">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#0e1a2b;border-radius:12px;overflow:hidden;border:1px solid #1e3a5f;">
        <tr>
          <td style="background:linear-gradient(135deg,#007a63,#005fa3);padding:28px 32px;text-align:center;">
            <h1 style="margin:0;color:#00ffd1;font-size:22px;">💬 Phản hồi từ AI Translator</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;color:#cfe8f0;font-size:15px;line-height:1.8;">
            <p>Xin chào <strong style="color:#00ffd1;">{contact_msg.first_name}</strong>,</p>
            <p>Đội ngũ hỗ trợ của chúng tôi đã xem xét tin nhắn của bạn và có phản hồi sau:</p>
          </td>
        </tr>
        <!-- Reply box -->
        <tr>
          <td style="padding:0 32px 24px;">
            <div style="background:#0b1a24;border-left:4px solid #00ffd1;
                        border-radius:0 8px 8px 0;padding:18px 20px;">
              <p style="margin:0;color:#e8f4f8;font-size:15px;line-height:1.7;
                         white-space:pre-wrap;">{reply_text}</p>
            </div>
          </td>
        </tr>
        <!-- Original message -->
        <tr>
          <td style="padding:0 32px 28px;">
            <p style="margin:0 0 8px;color:#4a6a7a;font-size:12px;text-transform:uppercase;letter-spacing:1px;">
              Tin nhắn gốc của bạn:
            </p>
            <div style="background:#07161a;border:1px solid #1e3a5f;
                        border-radius:8px;padding:14px 18px;">
              <p style="margin:0;color:#7a9fb0;font-size:13px;line-height:1.6;
                         white-space:pre-wrap;">{original_preview}</p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="background:#07161a;padding:14px 32px;text-align:center;">
            <p style="margin:0;color:#4a6a7a;font-size:11px;">
              AI Translator · Bạn nhận email này vì đã liên hệ với chúng tôi
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    send_async(
        subject=f'[AI Translator] Phản hồi tin nhắn của bạn',
        html_body=html,
        to=contact_msg.email,
        cfg=cfg,
    )


def send_account_delete_user_email(user) -> None:
    """Email xác nhận yêu cầu xóa tài khoản gửi cho người dùng."""
    cfg = _get_cfg()
    if not user or not user.email:
        return

    name = (user.name or user.email or 'Người dùng').strip()
    requested = user.delete_requested_at.strftime('%d/%m/%Y %H:%M') if user.delete_requested_at else '—'
    scheduled = user.delete_scheduled_at.strftime('%d/%m/%Y %H:%M') if user.delete_scheduled_at else '—'

    html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:30px 10px;">
    <table width="560" cellpadding="0" cellspacing="0"
           style="background:#0e1a2b;border-radius:12px;border:1px solid #1e3a5f;">
      <tr><td style="background:linear-gradient(135deg,#8b2635,#5a1a24);padding:24px 28px;text-align:center;">
        <h1 style="margin:0;color:#ffb4b4;font-size:20px;">Yêu cầu xóa tài khoản đã được ghi nhận</h1>
      </td></tr>
      <tr><td style="padding:28px;color:#cfe8f0;font-size:15px;line-height:1.8;">
        <p>Xin chào <strong>{name}</strong>,</p>
        <p>Chúng tôi đã ghi nhận yêu cầu xóa tài khoản AI Translator của bạn.</p>
        <ul style="color:#a8c8d8;padding-left:20px;">
          <li><strong>Email tài khoản:</strong> {user.email}</li>
          <li><strong>Thời gian gửi yêu cầu:</strong> {requested}</li>
          <li><strong>Ngày dự kiến xóa:</strong> {scheduled}</li>
        </ul>
        <p style="color:#7ecfb3;">Trong vòng <strong>30 ngày</strong>, bạn có thể đăng nhập lại và chọn
           <strong>Khôi phục tài khoản</strong> nếu thay đổi quyết định.</p>
        <p style="color:#8899aa;font-size:13px;">Sau thời hạn trên, tài khoản sẽ bị xóa hoặc vô hiệu hóa vĩnh viễn.</p>
      </td></tr>
      <tr><td style="background:#07161a;padding:14px;text-align:center;">
        <p style="margin:0;color:#4a6a7a;font-size:11px;">AI Translator · Email tự động</p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""

    send_async(
        subject='Yêu cầu xóa tài khoản đã được ghi nhận',
        html_body=html,
        to=user.email,
        cfg=cfg,
    )


def send_account_delete_admin_email(user) -> None:
    """Thông báo admin khi có yêu cầu xóa tài khoản."""
    cfg = _get_cfg()
    admin_email = cfg.get('admin_email')
    if not admin_email or not user:
        return

    name = (user.name or '—').strip()
    requested = user.delete_requested_at.strftime('%d/%m/%Y %H:%M') if user.delete_requested_at else '—'
    scheduled = user.delete_scheduled_at.strftime('%d/%m/%Y %H:%M') if user.delete_scheduled_at else '—'
    reason = (user.delete_reason or '—').strip()
    if len(reason) > 500:
        reason = reason[:500] + '…'

    html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:30px 10px;">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#0e1a2b;border-radius:12px;border:1px solid #1e3a5f;">
      <tr><td style="background:linear-gradient(135deg,#007a63,#005fa3);padding:24px 28px;">
        <h1 style="margin:0;color:#00ffd1;font-size:20px;">Có yêu cầu xóa tài khoản từ người dùng</h1>
      </td></tr>
      <tr><td style="padding:28px;color:#cfe8f0;font-size:15px;line-height:1.8;">
        <table width="100%" cellpadding="6" cellspacing="0">
          <tr><td style="color:#7a9fb0;width:180px;">ID người dùng</td><td><strong>#{user.id}</strong></td></tr>
          <tr><td style="color:#7a9fb0;">Tên</td><td>{name}</td></tr>
          <tr><td style="color:#7a9fb0;">Email</td><td>{user.email}</td></tr>
          <tr><td style="color:#7a9fb0;">Thời gian yêu cầu</td><td>{requested}</td></tr>
          <tr><td style="color:#7a9fb0;">Ngày dự kiến xóa</td><td>{scheduled}</td></tr>
          <tr><td style="color:#7a9fb0;">Lý do</td><td style="white-space:pre-wrap;">{reason}</td></tr>
          <tr><td style="color:#7a9fb0;">Trạng thái</td><td><strong style="color:#ffb86c;">pending_delete</strong></td></tr>
        </table>
      </td></tr>
      <tr><td style="background:#07161a;padding:14px;text-align:center;">
        <p style="margin:0;color:#4a6a7a;font-size:11px;">AI Translator · Admin notification</p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""

    send_async(
        subject='Có yêu cầu xóa tài khoản từ người dùng',
        html_body=html,
        to=admin_email,
        cfg=cfg,
    )
