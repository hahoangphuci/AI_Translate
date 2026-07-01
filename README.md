# AI Translation System - Giữ Định Dạng Gốc

Hệ thống dịch văn bản và tài liệu sử dụng trí tuệ nhân tạo tiên tiến, giữ nguyên 100% định dạng gốc.

## 🎯 Tính Năng Chính

### ✨ Dịch Văn Bản

- Dịch tức thời với 100+ ngôn ngữ
- Tự động phát hiện ngôn ngữ nguồn
- Chọn 1 API dịch chung trong Cài đặt: Google Translate / DeepL / Gemini 2.5 Flash
- Đếm ký tự (giới hạn 5000)
- Hoán đổi ngôn ngữ nhanh
- Sao chép/tải xuống kết quả

### 📄 Dịch Tài Liệu - Giữ Định Dạng

- Hỗ trợ: PDF, Word, Excel, PowerPoint, TXT
- Kéo thả file hoặc chọn file
- Giữ nguyên 100% định dạng gốc
- Upload nhiều file cùng lúc
- Giới hạn 50MB/file

### 📊 Lịch Sử Dịch Thuật

- Lưu tất cả bản dịch
- Xem lại bản dịch cũ
- Quản lý và xóa lịch sử
- Hiển thị thời gian thực

### 🖼️ Dịch Ảnh (OCR)

- Upload hoặc dán ảnh (Ctrl+V) để OCR lấy chữ
- Dịch kết quả OCR như văn bản bình thường
- Khuyến nghị cấu hình `OCR_LANGS_DEFAULT=eng+vie` cho ảnh tiếng Việt

### 🔐 Bảo Mật & Xác Thực

- Đăng nhập Google OAuth
- JWT Authentication
- Mã hóa dữ liệu
- Bảo mật tuyệt đối

## 🛠️ Công Nghệ Sử Dụng

- **Backend**: Python 3.10, Flask, SQLAlchemy
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Database**: MySQL
- **Authentication**: JWT, Google OAuth 2.0
- **AI Services**: Google Translate, DeepL API, Gemini 2.5 Flash
- **Container**: Docker & Docker Compose
- **Payment**: SePay.vn integration

### PDF Pipeline (bắt buộc để giữ layout)

1. PDF Analyzer

- kiểm tra PDF có text hay scan
- kiểm tra có bảng không
- kiểm tra có nhiều cột không
- kiểm tra có ảnh không

2. Scan OCR (nếu là scan)

- OCR trước để tạo searchable PDF

3. PDF Cleaner

- xoay trang đúng chiều (autorotate)
- tăng chất lượng ảnh (enhance)
- deskew nếu bị nghiêng
- làm sạch layer lỗi bằng bản raster khi cần

4. PDF -> DOCX Converter

- ưu tiên `pdf2docx`

5. DOCX Translation

- giữ paragraph
- giữ run/style
- giữ bảng
- giữ heading

6. DOCX Layout Recovery

- tự co font trong bảng khi cần
- tự xuống dòng theo layout
- sửa tràn bảng (relax row height)
- sửa ảnh lệch (giới hạn theo khổ trang)

7. DOCX -> PDF

- export qua Word (docx2pdf) hoặc LibreOffice

8. Quality Checker

- kiểm tra mất chữ/bảng/reference

PDF đã dịch.

Biến môi trường liên quan:

```env
# PDF -> DOCX converter: pdf2docx | word | adobe
PDF_DOCX_CONVERTER=pdf2docx
PDF2DOCX_DELETE_HYPHEN=0

# DOCX -> PDF engine: auto | docx2pdf | libreoffice
PDF_DOCX_EXPORT_ENGINE=auto

# Keep intermediate DOCX files for debugging
PDF_DOCX_KEEP_INTERMEDIATE=0

# Layout/format recovery
PDF_DOCX_LAYOUT_SYNC=1
PDF_DOCX_PDF_FORMAT_SYNC=0
PDF_DOCX_TABLE_SYNC=1
PDF_DOCX_HEADER_FOOTER_SYNC=1
PDF_DOCX_SANITIZE_MERGE_FRAGMENTS=0
PDF_DOCX_FORCE_BODY_JUSTIFY=0
PDF_DOCX_REGIONAL_MODE=auto
# force: always mirror source layout | auto: mirror normal docs, allow academic regional logic | off: legacy normalize
PDF_DOCX_PRESERVE_LAYOUT_MODE=force
PDF_DOCX_SANITIZE_REPLACE_NBSP=1
PDF_DOCX_SANITIZE_REPLACE_TABS=0
PDF_DOCX_SANITIZE_STRIP_SOFT_HYPHEN=0
PDF_DOCX_NORMALIZE_SUBSET_FONTS=1
PDF_DOCX_FIX_SYMBOL_FONT_RUNS=1
PDF_DOCX_TEXT_FONT_FALLBACK=Times New Roman

# Strict mode: fail if scan OCR cannot create searchable PDF
PDF_SCAN_OCR_STRICT=0

# PDF cleanup controls
PDF_CLEAN_NORMALIZE_ROTATION=1
PDF_CLEAN_AUTOROTATE=1
PDF_CLEAN_DESKEW=1
PDF_CLEAN_ENHANCE=1
PDF_CLEAN_RENDER_DPI=250

# Translation guard for DOCX (skip URL/DOI/reference/formula/code)
DOCX_TRANSLATION_GUARD=1

# Optional post-fixes (off by default for generic PDF fidelity)
DOCX_TARGETED_FIXES=0
DOCX_DOMAIN_FIXUPS=0

# Layout recovery for table cells
DOCX_TABLE_SHRINK=0
DOCX_TABLE_SHRINK_LEN=140
DOCX_TABLE_SHRINK_MIN_PT=8

# Ưu tiên OpenAI API cho dịch
AI_PROVIDER=openai

# Engine xuất DOCX -> PDF: auto | docx2pdf | libreoffice
PDF_DOCX_EXPORT_ENGINE=auto
```

## 📚 Documentation / Tài liệu

| Document | Web | Markdown |
|----------|-----|----------|
| Installation / Cài đặt | [/installation](http://127.0.0.1:5055/installation) | [docs/INSTALLATION_GUIDE.md](docs/INSTALLATION_GUIDE.md) |
| System architecture / Kiến trúc | — | [docs/KIEN_TRUC_HE_THONG.md](docs/KIEN_TRUC_HE_THONG.md) |
| User guide / Sử dụng Web | [/user-guide](http://127.0.0.1:5055/user-guide) | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| SePay integration | — | [docs/SEPAY_INTEGRATION.md](docs/SEPAY_INTEGRATION.md) |
| Database setup | — | [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md) |
| Document translation flow | — | [docs/DOCUMENT_TRANSLATION_FLOW.md](docs/DOCUMENT_TRANSLATION_FLOW.md) |

Full index: [docs/README.md](docs/README.md)

## 🚀 Cài Đặt & Chạy

### Yêu cầu hệ thống

- Python 3.10+
- Node.js (cho development)
- Docker & Docker Compose
- MySQL

### 1. Clone repository

```bash
git clone https://github.com/duyvo26/ai-translation-system.git
cd ai-translation-system
```

### 2. Cấu hình môi trường

```bash
# Backend
cd api_base
cp .env.example .env
# Chỉnh sửa .env với API keys của bạn

# Frontend
cd ../frontend
cp .env.example .env
```

### 3. Chạy với Docker (Khuyến nghị)

```bash
docker-compose up --build
```

### 4. Hoặc chạy local

```bash
# Backend
cd api_base
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python run_api.py

# Frontend (mở terminal mới)
cd frontend
python -m http.server 8000  # Hoặc dùng Live Server extension
```

### 5. Truy cập

- Frontend: http://localhost:80 hoặc http://localhost:8000
- Backend API: http://localhost:5000
- Database: localhost:3306

## 🧩 Cấu hình OCR (Tesseract)

OCR dùng `pytesseract` nhưng máy bạn cần cài thêm **Tesseract OCR** (binary) thì mới chạy được.

### Windows

- Cài Tesseract OCR
- Sau khi cài, làm 1 trong 2 cách:
  - Thêm Tesseract vào `PATH` (mở terminal mới sau khi thêm PATH)
  - Hoặc set biến trong `api_base/.env`:

```env
# Ví dụ Windows
TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
OCR_LANGS_DEFAULT=eng+vie
```

Nếu OCR báo thiếu ngôn ngữ `vie`, hãy đảm bảo language data tiếng Việt được cài kèm trong Tesseract.

## 📄 Cấu hình PDF (giữ định dạng)

PDF rất khó “giữ nguyên định dạng gốc” tuyệt đối khi dịch (đặc biệt với bảng/form). Hệ thống dùng luồng DOCX (Analyzer → PDF → DOCX → dịch → khôi phục layout/định dạng → DOCX → PDF) để giảm lỗi chồng chữ và lệch bố cục.

Chỉnh trong `api_base/.env`:

```env
# (Chi ap dung cho pipeline IR)
# Mặc định: dịch cả bảng (ưu tiên "dịch toàn bộ") và cố gắng fit text trong đúng ô
# Values: skip | safe | force
# - force: dịch nhiều nhất (có thể chữ nhỏ hơn trong ô hẹp)
# - safe : chỉ thay thế khi fit tốt (giữ layout tối đa, nhưng có thể bỏ qua vài ô)
# - skip : không dịch các ô bảng/form (giữ layout tuyệt đối)
PDF_TABLE_MODE=force

# Chặn chế độ bilingual "newline" cho PDF để tránh chồng chữ (mặc định backend tự chặn)
PDF_ALLOW_NEWLINE_MODE=0

# Strict mode: ưu tiên giữ layout, có thể bỏ qua nhiều dòng khó thay thế
PDF_STRICT_PRESERVE=0

# (Quan trọng) Font Unicode cho PDF overlay.
# Một số môi trường (Docker/Linux) không có font hệ thống phù hợp, PyMuPDF có thể báo lỗi
# kiểu "need font file or buffer" hoặc chữ tiếng Việt bị lỗi.
# Hãy trỏ tới một file .ttf có hỗ trợ Unicode (ví dụ DejaVuSans.ttf, NotoSans-Regular.ttf).
PDF_FONT_FILE=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf

# (Giống bản gốc nhất) Full-page overlay cho PDF (áp dụng cho pipeline v2).
# - 1: rasterize mỗi trang + OCR bbox + vẽ chữ dịch lên ảnh + chèn ảnh phủ lên trang
# - 0: dùng redact/overlay theo bbox (text selectable hơn nhưng khó giống 100%)
PDF_FULL_PAGE_OVERLAY_FORCE=1

# Có xoá (che) chữ gốc dưới nền khi vẽ chữ dịch lên ảnh hay không.
# - 1: che bằng màu nền ước lượng (thường dễ đọc hơn, giống "thay chữ")
# - 0: chỉ vẽ đè (có thể thấy chữ gốc lẫn chữ dịch)
PDF_FULL_PAGE_OVERLAY_ERASE_BEHIND=1
```

## 🔧 Cấu Hình API Keys

Chỉnh sửa file `api_base/.env`:

```env
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
DATABASE_URL=mysql://translator:translator123@localhost/translation_db
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
OPENAI_API_KEY=your-openai-api-key
DEEPL_API_KEY=your-deepl-api-key
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
TRANSLATION_PROVIDER_DEFAULT=google
SEPAY_API_KEY=your-sepay-api-key
# Optional: key used to verify SePay webhooks (defaults to SEPAY_API_KEY)
SEPAY_WEBHOOK_API_KEY=your-sepay-webhook-api-key
# Kept for backward-compatibility with older setups (not used by current code)
SEPAY_SECRET=your-sepay-secret
```

## 📱 Giao Diện

### 🎨 Thiết Kế

- **Gradient Background**: Màu sắc bắt mắt với gradient động
- **Glassmorphism**: Hiệu ứng kính mờ hiện đại
- **Responsive**: Hoàn hảo trên mọi thiết bị
- **Animations**: Hiệu ứng mượt mà, tương tác
- **Font Awesome**: Icons đẹp và chuyên nghiệp

### 📱 Responsive Design

- Mobile-first approach
- Tablet và desktop optimization
- Touch-friendly interactions

## 🔒 Bảo Mật

- JWT tokens cho API authentication
- Google OAuth 2.0 cho user login
- Password hashing (nếu cần)
- CORS protection
- Input validation
- SQL injection prevention

## 💰 Tích Hợp Thanh Toán

- **SePay.vn**: Cổng thanh toán Việt Nam
- Hỗ trợ QR code payment
- Webhook notifications (endpoint: `POST /api/payment/sepay/webhook`)
- Transaction logging

Webhook auth (SePay cấu hình kiểu "API Key"):

- Header: `Authorization: Apikey <SEPAY_WEBHOOK_API_KEY>`

Lưu ý về QR:

- Hệ thống hiện tạo QR chuyển khoản chuẩn VietQR (chuyển khoản ngân hàng là giao dịch thật).
- SePay đóng vai trò **tự động xác nhận** giao dịch (poll User API hoặc nhận webhooks).

Tài liệu kỹ thuật (polling/sync, không cần webhook):

- Xem [docs/SEPAY_INTEGRATION.md](docs/SEPAY_INTEGRATION.md) (EN + VI)
- Xem [PAYMENT_POLLING_SYNC.md](PAYMENT_POLLING_SYNC.md) (chi tiết polling)
- Nếu muốn QR hiển thị theo style SePay như trang `qr.sepay.vn`, cấu hình `SEPAY_QR_TEMPLATE_URL`:
  - Ví dụ: `SEPAY_QR_TEMPLATE_URL=https://qr.sepay.vn/img?acc={account_number}&bank={bank_code}&amount={amount}&des={content}&template=compact`

## 🚀 Triển Khai Production

### Với AAPanel

1. Upload code lên server
2. Cấu hình domain
3. Setup SSL certificate
4. Configure reverse proxy
5. Setup MySQL database
6. Run Docker containers

### Environment Variables Production

```env
FLASK_ENV=production
DATABASE_URL=mysql://user:password@host:port/db
FRONTEND_URL=https://yourdomain.com
```

## 📊 API Documentation

### Authentication

```
POST /api/auth/google
POST /api/auth/profile
```

### Translation

```
POST /api/translation/text
POST /api/translation/document
GET  /api/translation/history
```

### Payment

```
POST /api/payment/create
GET  /api/payment/status/{id}
```

### History

```
GET  /api/history
DEL  /api/history/{id}
```

## 🤝 Đóng Góp

1. Fork project
2. Tạo feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Tạo Pull Request

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📞 Liên Hệ

**Duy Vo** - duyvo26@github.com

Project Link: [https://github.com/duyvo26/ai-translation-system](https://github.com/duyvo26/ai-translation-system)

---

⭐ **Nếu project này hữu ích, hãy cho chúng tôi một ngôi sao!**
