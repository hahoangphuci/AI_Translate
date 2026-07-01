# Installation Guide / Hướng dẫn cài đặt

---

## Tiếng Việt

### 1. Yêu cầu hệ thống

| Thành phần | Phiên bản gợi ý |
|------------|-----------------|
| Python | 3.10+ |
| MySQL | 8.x hoặc MariaDB (XAMPP) |
| Tesseract OCR | Bắt buộc nếu dùng dịch ảnh / PDF scan |
| Microsoft Word hoặc LibreOffice | Tùy chọn — xuất PDF từ DOCX |
| Git | Để clone repository |
| Docker & Docker Compose | Tùy chọn — triển khai đa container |

**Hệ điều hành:** Windows 10/11, Linux, macOS.

### 2. Clone repository

```bash
git clone https://github.com/duyvo26/ai-translation-system.git
cd ai-translation-system
```

### 3. Cài đặt Python dependencies

```bash
cd api_base
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường

Tạo file `.env` từ mẫu:

```bash
cd api_base

# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Chỉnh các mục quan trọng trong `api_base/.env`:

```env
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
DATABASE_URL=mysql+pymysql://root:@localhost:3306/ai_translation
FRONTEND_URL=http://127.0.0.1:5055

# Google OAuth (đăng nhập)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:5055/api/auth/google/callback

# AI translation (chọn ít nhất một)
OPENAI_API_KEY=
DEEPL_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
AI_PROVIDER=openrouter
TRANSLATION_PROVIDER_DEFAULT=gemini

# OCR (Windows)
TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
OCR_LANGS_DEFAULT=eng+vie

# Thanh toán SePay — xem SEPAY_INTEGRATION.md
SEPAY_API_KEY=
PAYMENT_BANK_CODE=MB
PAYMENT_BANK_ACCOUNT=
PAYMENT_BANK_ACCOUNT_NAME=
```

**Lưu ý Google OAuth:** Thêm các URI sau vào Google Cloud Console → **Authorized redirect URIs**:

- `http://127.0.0.1:5055/api/auth/google/callback`
- `http://localhost:5055/api/auth/google/callback`

### 5. Cấu hình database

1. Cài và khởi động MySQL (XAMPP hoặc standalone).
2. Tạo database `ai_translation` (charset `utf8mb4_unicode_ci`).
3. Chi tiết: [DATABASE_SETUP.md](./DATABASE_SETUP.md).

Kiểm tra kết nối và tạo bảng:

```bash
cd api_base
python app/models/base_db.py --check   # chỉ kiểm tra kết nối
python app/models/base_db.py           # tạo DB + bảng (nếu chưa có)
```

**Hoặc** import SQL trực tiếp:

```bash
mysql -u root ai_translation < init_db.sql
```

> **Ghi chú:** Khi chạy `python run_api.py`, ứng dụng cũng tự gọi `db.create_all()` và migration schema. Bước trên hữu ích khi muốn tạo database MySQL trước hoặc kiểm tra kết nối độc lập.

Nếu MySQL/XAMPP không chạy, app **tự chuyển sang SQLite** tại `api_base/instance/translation.db`.

### 6. Tesseract OCR (Windows)

1. Tải Tesseract: https://github.com/UB-Mannheim/tesseract/wiki  
2. Cài gói ngôn ngữ **English** và **Vietnamese**.  
3. Repo đã có `api_base/tessdata/vie.traineddata` — có thể copy vào thư mục tessdata của Tesseract nếu thiếu.

### 7. Khởi động server (local — khuyến nghị)

```bash
cd api_base
python run_api.py
```

Mặc định: **http://127.0.0.1:5055** — Flask phục vụ **frontend + API cùng một port** (không cần chạy Nginx riêng khi dev local).

Biến tùy chọn:

```env
BACKEND_PORT=5055
BACKEND_AUTO_OPEN_BROWSER=1
```

Lần chạy đầu, server tự tạo tài khoản admin mặc định (nếu chưa có):

```env
ADMIN_ACCOUNT_EMAIL=admin@gmail.com
ADMIN_ACCOUNT_PASSWORD=admin123
```

### 8. Chạy bằng Docker (tùy chọn)

```bash
# Tạo api_base/.env trước (bước 4)
docker-compose up --build
```

| Thành phần | URL |
|------------|-----|
| Frontend (Nginx) | http://localhost |
| Backend API trực tiếp | http://localhost:5000 |
| MySQL | localhost:3306 |

Docker Compose tự cấu hình `DATABASE_URL` trỏ tới container `db` và mount `init_db.sql`. Nginx proxy `/api/` → backend.

Khi dùng Docker, cấu hình OAuth:

```env
FRONTEND_URL=http://localhost
GOOGLE_REDIRECT_URI=http://localhost/api/auth/google/callback
```

### 9. Kiểm tra cài đặt

| Kiểm tra | URL / lệnh |
|----------|------------|
| Trang chủ | http://127.0.0.1:5055/ |
| API stats | http://127.0.0.1:5055/api/public/stats |
| AI config | http://127.0.0.1:5055/api/ai/status |
| Database | `python app/models/base_db.py --check` |
| Đăng nhập | http://127.0.0.1:5055/auth (Google OAuth) |

### 10. Xử lý sự cố thường gặp

| Lỗi | Cách xử lý |
|-----|------------|
| Port 5055 đã dùng | Dừng process cũ hoặc đổi `BACKEND_PORT` |
| MySQL connection failed | Bật MySQL trong XAMPP, kiểm tra `DATABASE_URL`. Nếu XAMPP lỗi: app **tự chuyển SQLite** (`api_base/instance/translation.db`) |
| OCR không chạy | Kiểm tra `TESSERACT_CMD` và ngôn ngữ `vie` |
| Google login lỗi | Khớp `GOOGLE_REDIRECT_URI` với Google Cloud Console; thêm cả `localhost` và `127.0.0.1` |
| PDF không xuất được | Cài Microsoft Word (`docx2pdf`) hoặc LibreOffice; xem `PDF_DOCX_EXPORT_ENGINE` |

---

## English

### 1. System requirements

| Component | Suggested version |
|-----------|-------------------|
| Python | 3.10+ |
| MySQL | 8.x or MariaDB (XAMPP) |
| Tesseract OCR | Required for image / scanned PDF translation |
| Microsoft Word or LibreOffice | Optional — DOCX to PDF export |
| Git | To clone the repository |
| Docker & Docker Compose | Optional — multi-container deployment |

**OS:** Windows 10/11, Linux, macOS.

### 2. Clone the repository

```bash
git clone https://github.com/duyvo26/ai-translation-system.git
cd ai-translation-system
```

### 3. Install Python dependencies

```bash
cd api_base
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Environment variables

```bash
cd api_base

# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit key values in `api_base/.env`:

```env
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
DATABASE_URL=mysql+pymysql://root:@localhost:3306/ai_translation
FRONTEND_URL=http://127.0.0.1:5055

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:5055/api/auth/google/callback

OPENAI_API_KEY=
DEEPL_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
AI_PROVIDER=openrouter
TRANSLATION_PROVIDER_DEFAULT=gemini

TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
OCR_LANGS_DEFAULT=eng+vie

SEPAY_API_KEY=
PAYMENT_BANK_CODE=MB
PAYMENT_BANK_ACCOUNT=
PAYMENT_BANK_ACCOUNT_NAME=
```

**Google OAuth:** Add these to Google Cloud Console → **Authorized redirect URIs**:

- `http://127.0.0.1:5055/api/auth/google/callback`
- `http://localhost:5055/api/auth/google/callback`

### 5. Configure the database

1. Install and start MySQL (XAMPP or standalone).
2. Create database `ai_translation` (`utf8mb4_unicode_ci`).
3. See [DATABASE_SETUP.md](./DATABASE_SETUP.md).

```bash
cd api_base
python app/models/base_db.py --check   # connection check only
python app/models/base_db.py           # create DB + tables
```

Or import SQL:

```bash
mysql -u root ai_translation < init_db.sql
```

> **Note:** `python run_api.py` also runs `db.create_all()` on startup. The script above is useful for pre-creating the MySQL database or verifying connectivity.

If MySQL is unavailable, the app **auto-falls back to SQLite** at `api_base/instance/translation.db`.

### 6. Tesseract OCR (Windows)

1. Download Tesseract: https://github.com/UB-Mannheim/tesseract/wiki  
2. Install **English** and **Vietnamese** language packs.  
3. The repo includes `api_base/tessdata/vie.traineddata` if needed.

### 7. Start the server (local — recommended)

```bash
cd api_base
python run_api.py
```

Default URL: **http://127.0.0.1:5055** — Flask serves **frontend and API on the same port** (no separate Nginx needed for local dev).

Optional:

```env
BACKEND_PORT=5055
BACKEND_AUTO_OPEN_BROWSER=1
```

Default admin account on first run (if not exists):

```env
ADMIN_ACCOUNT_EMAIL=admin@gmail.com
ADMIN_ACCOUNT_PASSWORD=admin123
```

### 8. Docker (optional)

```bash
# Create api_base/.env first (step 4)
docker-compose up --build
```

| Component | URL |
|-----------|-----|
| Frontend (Nginx) | http://localhost |
| Backend API (direct) | http://localhost:5000 |
| MySQL | localhost:3306 |

For Docker OAuth:

```env
FRONTEND_URL=http://localhost
GOOGLE_REDIRECT_URI=http://localhost/api/auth/google/callback
```

### 9. Verify installation

| Check | URL / command |
|-------|---------------|
| Home page | http://127.0.0.1:5055/ |
| API stats | http://127.0.0.1:5055/api/public/stats |
| AI status | http://127.0.0.1:5055/api/ai/status |
| Database | `python app/models/base_db.py --check` |
| Auth | Sign in with Google at `/auth` |

### 10. Troubleshooting

| Issue | Fix |
|-------|-----|
| Port 5055 in use | Stop old process or change `BACKEND_PORT` |
| MySQL connection failed | Start MySQL, verify `DATABASE_URL`. If XAMPP is broken: app **auto-falls back to SQLite** (`api_base/instance/translation.db`) |
| OCR errors | Check `TESSERACT_CMD` and `vie` language data |
| Google login fails | Match `GOOGLE_REDIRECT_URI` in Google Cloud Console; add both `localhost` and `127.0.0.1` |
| PDF export fails | Install Microsoft Word (`docx2pdf`) or LibreOffice; see `PDF_DOCX_EXPORT_ENGINE` |

---

**See also:** [USER_GUIDE.md](./USER_GUIDE.md) · [SEPAY_INTEGRATION.md](./SEPAY_INTEGRATION.md) · Web: `/installation`
