# SePay Integration / Tích hợp SePay

Payment gateway for bank transfer (VietQR / SePay QR) with automatic confirmation.

---

## Tiếng Việt

### 1. Tổng quan

**SePay.vn** giúp:

- Theo dõi biến động số dư tài khoản ngân hàng liên kết
- Cung cấp **User API** để poll lịch sử giao dịch
- (Tùy chọn) Gửi **webhook** khi có tiền vào

Hệ thống AI Translation:

1. Tạo hoá đơn `pending` + mã chuyển khoản duy nhất (`HEX_ID`)
2. Hiển thị QR VietQR hoặc SePay QR cho người dùng
3. Xác nhận thanh toán qua **polling** (mặc định) hoặc **webhook**
4. Cộng token / nâng gói Pro khi khớp số tiền + nội dung CK

### 2. Đăng ký SePay

1. Tạo tài khoản tại https://my.sepay.vn  
2. Thêm **tài khoản ngân hàng nhận** (MB, VCB, …)  
3. Cài app ngân hàng trên điện thoại để SePay nhận biến động  
4. Lấy **API Key** (User API)

### 3. Cấu hình `.env`

```env
# SePay User API — bắt buộc cho polling
SEPAY_API_KEY=your-sepay-api-key
SEPAY_BASE_URL=https://my.sepay.vn
SEPAY_HISTORY_ENDPOINT=/userapi/transactions/list

# Webhook (tùy chọn — production khuyến nghị)
SEPAY_WEBHOOK_API_KEY=your-webhook-key
# Nếu không set, mặc định dùng SEPAY_API_KEY

# Tài khoản nhận tiền (VietQR)
PAYMENT_BANK_CODE=MB
PAYMENT_BANK_ACCOUNT=0123456789
PAYMENT_BANK_ACCOUNT_NAME=CONG TY ABC

# Nội dung chuyển khoản
NAME_WEB=AITRANS
PAYMENT_TRANSFER_KEYWORD=NAPTOKEN
PAYMENT_XOR_KEY=0x5EAFB
PAYMENT_EXPIRE_MINUTES=60

# QR style SePay (tùy chọn)
SEPAY_QR_TEMPLATE_URL=https://qr.sepay.vn/img?acc={account_number}&bank={bank_code}&amount={amount}&des={content}&template=compact
```

### 4. Luồng thanh toán

```
User chọn gói → POST /api/payment/create
    → Backend tạo payment (pending)
    → Trả QR + nội dung CK: AITRANSNAPTOKEN{HEX_ID}

User chuyển khoản → SePay ghi nhận giao dịch

Frontend poll GET /api/payment/status/{ref} (5–10s)
    → Backend gọi SePay User API
    → So khớp mã HEX + amount_in >= amount
    → completed → cộng token
```

### 5. Webhook (production)

**Endpoint:** `POST /api/payment/sepay/webhook`

**Xác thực:** Header `Authorization: Apikey <SEPAY_WEBHOOK_API_KEY>`

Cấu hình URL webhook trên dashboard SePay trỏ tới:

```
https://yourdomain.com/api/payment/sepay/webhook
```

Webhook và polling có thể chạy song song; backend idempotent theo `sepay_transaction_id`.

### 6. So khớp giao dịch (reconciliation)

Backend ưu tiên:

1. Trường `tx.code` (SePay auto-detect mã nạp)
2. Nếu không có → parse `tx.content` / `tx.description`

Điều kiện thành công:

- Nội dung chứa prefix `NAME_WEB + PAYMENT_TRANSFER_KEYWORD + HEX_ID`
- `amount_in` ≥ số tiền hoá đơn

Hoá đơn hết hạn (`failed`) vẫn có thể được **reconcile muộn** nếu tiền về đúng mã.

### 7. API endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/api/payment/create` | Tạo hoá đơn + QR |
| GET | `/api/payment/status/{ref}` | Poll trạng thái + sync SePay |
| POST | `/api/payment/sepay/webhook` | Nhận webhook SePay |
| GET | `/api/payment/debug/sepay` | Debug (cần đăng nhập) |

Body `create`:

```json
{
  "package_id": "pro",
  "force_new": false
}
```

`package_id`: `pro` | `promax`

### 8. QR code

- **Mặc định:** VietQR (`img.vietqr.io`) từ `PAYMENT_BANK_*`
- **SePay style:** set `SEPAY_QR_TEMPLATE_URL` (xem https://qr.sepay.vn/)

Frontend cũng có thể build QR URL: `https://qr.sepay.vn/img?...`

### 9. Kiểm thử local

Local **không nhận webhook** (trừ khi dùng ngrok). Dùng **polling**:

1. Set `SEPAY_API_KEY` và thông tin ngân hàng thật
2. Tạo hoá đơn trên Dashboard
3. Chuyển khoản thử số tiền nhỏ
4. Chờ frontend poll — hoặc gọi thủ công `GET /api/payment/status/{hex_id}`

Debug: `GET /api/payment/debug/sepay` (JWT required)

### 10. Tham chiếu code

- `api_base/app/routers/payment.py`
- `api_base/app/services/payment_service.py`
- Chi tiết polling: [PAYMENT_POLLING_SYNC.md](../PAYMENT_POLLING_SYNC.md)

---

## English

### 1. Overview

**SePay.vn** provides:

- Linked bank account balance monitoring
- **User API** to poll transaction history
- Optional **webhooks** on incoming transfers

AI Translation system:

1. Creates a `pending` invoice with unique transfer code (`HEX_ID`)
2. Shows VietQR or SePay QR to the user
3. Confirms payment via **polling** (default) or **webhook**
4. Credits tokens / upgrades Pro plan when amount + description match

### 2. SePay account setup

1. Register at https://my.sepay.vn  
2. Add **receiving bank account** (MB, VCB, etc.)  
3. Install bank app on phone for balance notifications  
4. Copy **API Key** (User API)

### 3. `.env` configuration

```env
SEPAY_API_KEY=your-sepay-api-key
SEPAY_BASE_URL=https://my.sepay.vn
SEPAY_HISTORY_ENDPOINT=/userapi/transactions/list

SEPAY_WEBHOOK_API_KEY=your-webhook-key

PAYMENT_BANK_CODE=MB
PAYMENT_BANK_ACCOUNT=0123456789
PAYMENT_BANK_ACCOUNT_NAME=YOUR COMPANY NAME

NAME_WEB=AITRANS
PAYMENT_TRANSFER_KEYWORD=NAPTOKEN
PAYMENT_XOR_KEY=0x5EAFB
PAYMENT_EXPIRE_MINUTES=60

SEPAY_QR_TEMPLATE_URL=https://qr.sepay.vn/img?acc={account_number}&bank={bank_code}&amount={amount}&des={content}&template=compact
```

### 4. Payment flow

```
User selects plan → POST /api/payment/create
    → pending invoice + transfer note: AITRANSNAPTOKEN{HEX_ID}

User transfers money → SePay records transaction

Frontend polls GET /api/payment/status/{ref}
    → Backend calls SePay User API
    → Matches HEX code + amount_in >= amount
    → completed → credit tokens
```

### 5. Webhook (production)

**Endpoint:** `POST /api/payment/sepay/webhook`

**Auth:** Header `Authorization: Apikey <SEPAY_WEBHOOK_API_KEY>`

Configure in SePay dashboard:

```
https://yourdomain.com/api/payment/sepay/webhook
```

Polling and webhooks can run together; idempotency via `sepay_transaction_id`.

### 6. Reconciliation logic

Backend checks:

1. `tx.code` (SePay payment code detection)
2. Else parse `tx.content` / `tx.description`

Success when:

- Content contains `NAME_WEB + PAYMENT_TRANSFER_KEYWORD + HEX_ID`
- `amount_in` ≥ invoice amount

Expired invoices (`failed`) can still complete if a late transfer matches.

### 7. API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/payment/create` | Create invoice + QR |
| GET | `/api/payment/status/{ref}` | Poll status + sync SePay |
| POST | `/api/payment/sepay/webhook` | SePay webhook receiver |
| GET | `/api/payment/debug/sepay` | Debug (auth required) |

Create body:

```json
{
  "package_id": "pro",
  "force_new": false
}
```

### 8. QR codes

- **Default:** VietQR from `PAYMENT_BANK_*`
- **SePay template:** set `SEPAY_QR_TEMPLATE_URL` — https://qr.sepay.vn/

### 9. Local testing

Webhooks need a public URL (e.g. ngrok). Use **polling** locally:

1. Set real `SEPAY_API_KEY` and bank details
2. Create invoice on Dashboard
3. Transfer a small test amount
4. Wait for frontend poll or call `GET /api/payment/status/{hex_id}`

Debug: `GET /api/payment/debug/sepay`

### 10. Code references

- `api_base/app/routers/payment.py`
- `api_base/app/services/payment_service.py`
- Polling details: [PAYMENT_POLLING_SYNC.md](../PAYMENT_POLLING_SYNC.md)
