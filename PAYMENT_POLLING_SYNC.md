# Kỹ thuật chuyên sâu: Hệ thống Thanh toán (Polling & Sync)

> **Bilingual doc:** See [docs/SEPAY_INTEGRATION.md](docs/SEPAY_INTEGRATION.md) (Tiếng Việt + English).

Tài liệu này giải thích chi tiết luồng **nạp tiền tự động không qua Webhook** (dựa trên polling) đang được triển khai trong dự án.

> Ghi chú: Dự án **có hỗ trợ Webhook** (`POST /api/payment/sepay/webhook`) nhưng phần dưới tập trung vào cơ chế polling/sync vì có thể chạy ổn ngay cả khi môi trường local không nhận được webhook.

## 1) Luồng xử lý (Payment Flow Sequence)

### 1.1 Khởi tạo hoá đơn

Frontend gọi:

- `POST /api/payment/create`

Body JSON:

- `package_id`: `pro` | `promax`
- `force_new` (optional): `true` để ép tạo hoá đơn mới

Backend sẽ:

- Tạo record `payments` (status: `pending`, currency: `VND`, amount theo gói)
- Trả về `hex_id` (ID hoá đơn đã XOR/obfuscate)
- Trả về nội dung chuyển khoản: `{NAME_WEB}{PAYMENT_TRANSFER_KEYWORD}{HEX_ID}`
- Trả về `qr_image_url` + thông tin ngân hàng nhận (`bank.code`, `bank.account_number`, `bank.account_name`)

Frontend hiển thị:

- QR chuyển khoản + thông tin nhận tiền + “Nội dung CK” để người dùng chuyển khoản đúng.

### 1.2 Polling (vòng lặp kiểm tra trạng thái)

Frontend gọi theo chu kỳ (gợi ý 5–10 giây):

- `GET /api/payment/status/{payment_ref}`

Trong đó `payment_ref` hỗ trợ:

- ID số (vd: `123`)
- hoặc `HEX_ID` (vd: `A1B2C3...`) — backend sẽ decode ra ID thật

Backend nhận request sẽ:

1. Gọi SePay User API lấy lịch sử giao dịch gần nhất.
2. Duyệt các giao dịch trả về.
3. So khớp để tìm giao dịch “thu tiền vào” có:
   - đúng **mã nạp** (`HEX_ID`) trong trường `code` hoặc `content`
   - và số tiền `amount_in` >= số tiền yêu cầu
4. Nếu trùng khớp → cập nhật hoá đơn `completed` + nạp token/cập nhật plan cho user.

## 2) Logic so khớp (Reconciliation Logic)

### 2.1 Từ khoá và regex bóc tách HEX

Prefix được tạo từ:

- `NAME_WEB` (mặc định: `AITRANS`)
- `PAYMENT_TRANSFER_KEYWORD` (mặc định: `NAPTOKEN`)

Chuỗi chuyển khoản (frontend hiển thị cho user):

- `{NAME_WEB}{PAYMENT_TRANSFER_KEYWORD}{HEX_ID}`

Backend bóc `HEX_ID` bằng regex (không phân biệt hoa/thường):

- `prefix = NAME_WEB + PAYMENT_TRANSFER_KEYWORD`
- `pattern = prefix + ([A-Fa-f0-9]+)`

### 2.2 Nguồn dữ liệu để match

Khi polling, backend ưu tiên match theo thứ tự:

1. `tx.code` (nếu SePay đã cấu hình auto-detect “mã nạp” theo nội dung)
2. nếu không có `code` thì dùng `tx.content` / `tx.description`

Sau khi bóc ra `found_hex`, backend so sánh:

- `found_hex == target_hex` (mã của hoá đơn hiện tại)
- `amount_in >= payment.amount`

Nếu đạt → trả về thành công và lưu `sepay_transaction_id` để idempotent.

## 3) Quản lý trạng thái (State Machine)

Các trạng thái chính:

- `pending`: đang chờ tiền về
- `completed`: đã nhận đủ tiền, đã nạp token/cập nhật gói
- `failed`: hoá đơn hết hạn

Hết hạn:

- Backend đánh dấu `failed` khi polling thấy hoá đơn `pending` đã quá hạn (`PAYMENT_EXPIRE_MINUTES`, mặc định 60 phút).

Tính “linh hoạt” (quan trọng):

- Dù hoá đơn đã `failed`, backend **vẫn tiếp tục reconcile** khi client gọi status.
- Nếu tiền về muộn mà match đúng mã & số tiền, backend vẫn có thể chuyển `failed -> completed`.

## 4) Bảo mật mã nạp (XOR Obfuscation)

Không dùng ID thuần (`1,2,3...`) để tránh người dùng đoán ID của người khác.

- `PAYMENT_XOR_KEY` (mặc định: `0x5EAFB`)

Ý tưởng:

- `HEX_ID = payment_id XOR SECRET_XOR_KEY` rồi chuyển sang hex.
- Decode ngược lại để tìm đúng record.

## 5) Cấu hình SePay Dashboard (để polling hoạt động)

Tại SePay.vn cần:

- Thêm ngân hàng nhận (MB, VCB...)
- Cài app ngân hàng trên điện thoại để SePay nhận biến động số dư
- Lấy API Key và đặt vào biến môi trường

### Biến môi trường liên quan (backend)

- `SEPAY_API_KEY`: dùng cho **User API** (poll lịch sử giao dịch)
- `SEPAY_BASE_URL` (optional): mặc định `https://my.sepay.vn`
- `SEPAY_HISTORY_ENDPOINT` (optional): mặc định `/userapi/transactions/list`

## 6) Cấu hình QR “của bạn” (nhận tiền)

Backend tạo QR dựa vào các biến nhận tiền:

- `PAYMENT_BANK_CODE` (vd: `MB`)
- `PAYMENT_BANK_ACCOUNT` (số tài khoản)
- `PAYMENT_BANK_ACCOUNT_NAME` (tên chủ tài khoản)

Tuỳ chọn QR SePay-style:

- `SEPAY_QR_TEMPLATE_URL`

Ví dụ:

```env
SEPAY_QR_TEMPLATE_URL=https://qr.sepay.vn/img?acc={account_number}&bank={bank_code}&amount={amount}&des={content}&template=compact
```

Nếu không set template, backend sẽ fallback VietQR (`img.vietqr.io`).

## 7) Tham chiếu code

- Backend endpoints: `api_base/app/routers/payment.py`
- Reconciliation + QR generator + XOR: `api_base/app/services/payment_service.py`
