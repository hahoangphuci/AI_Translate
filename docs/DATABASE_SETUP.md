# Database Setup / Cài đặt Database

MySQL setup for AI Translation System (XAMPP or standalone).

---

## Tiếng Việt

### 1. Cài XAMPP (Windows)

1. Tải XAMPP: https://www.apachefriends.org  
2. Cài đặt, chọn **MySQL**  
3. Mở **XAMPP Control Panel** → **Start** MySQL (port **3306**)  
4. Mặc định: user `root`, password **trống**

### 2. Tạo database

**Cách 1 — phpMyAdmin**

1. Mở http://localhost/phpmyadmin  
2. Tab **Databases** → tên: `ai_translation`  
3. Collation: `utf8mb4_unicode_ci` → **Create**

**Cách 2 — MySQL CLI**

```sql
CREATE DATABASE ai_translation
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

### 3. Cấu hình ứng dụng

File `api_base/.env`:

```env
DATABASE_URL=mysql+pymysql://root:@localhost:3306/ai_translation
```

Format: `mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE`  
Không mật khẩu: `root:@localhost` (dấu `:` sau user, password trống).

### 4. Cài driver Python

```bash
cd api_base
pip install -r requirements.txt
pip install PyMySQL
```

### 5. Tạo bảng tự động

```bash
cd api_base
python app/models/base_db.py --check   # kiểm tra kết nối
python app/models/base_db.py           # tạo DB + bảng
```

Script tạo các bảng: `user`, `translation`, `payment`, …

Hoặc import SQL:

```bash
mysql -u root ai_translation < init_db.sql
```

### 6. Xác nhận

**phpMyAdmin:** database `ai_translation` có các bảng.

**CLI:**

```sql
USE ai_translation;
SHOW TABLES;
DESCRIBE user;
```

### 7. Xử lý sự cố

| Lỗi | Giải pháp |
|-----|-----------|
| Can't connect to MySQL | Start MySQL trong XAMPP |
| Access denied | Kiểm tra user/password trong `DATABASE_URL` |
| Unknown database | Chạy `python app/models/base_db.py` |
| Port conflict | Đổi port MySQL hoặc cập nhật URL |
| `proxies_priv` corrupt (XAMPP) | Xem [SETUP_MYSQL.md](../SETUP_MYSQL.md) mục Troubleshooting |
| MySQL lỗi / không chạy được | **Tự động chuyển SQLite** khi chạy `python run_api.py` (file `api_base/instance/translation.db`) |

**SQLite fallback (mặc định bật):** Nếu XAMPP MySQL không kết nối được, backend tự chuyển sang SQLite — không cần sửa `.env`. Muốn tắt: `DB_DISABLE_SQLITE_FALLBACK=1`. Muốn luôn dùng SQLite: `DB_FORCE_SQLITE=1`.

### 8. Production

- Tạo user MySQL riêng (không dùng `root`)
- Giới hạn quyền chỉ database `ai_translation`
- Backup định kỳ

```sql
CREATE USER 'translator'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON ai_translation.* TO 'translator'@'localhost';
FLUSH PRIVILEGES;
```

```env
DATABASE_URL=mysql+pymysql://translator:strong_password@localhost:3306/ai_translation
```

---

## English

### 1. Install XAMPP (Windows)

1. Download XAMPP: https://www.apachefriends.org  
2. Install with **MySQL** selected  
3. **XAMPP Control Panel** → **Start** MySQL (port **3306**)  
4. Default: user `root`, **empty** password

### 2. Create database

**Option 1 — phpMyAdmin**

1. Open http://localhost/phpmyadmin  
2. **Databases** tab → name: `ai_translation`  
3. Collation: `utf8mb4_unicode_ci` → **Create**

**Option 2 — MySQL CLI**

```sql
CREATE DATABASE ai_translation
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

### 3. Application config

File `api_base/.env`:

```env
DATABASE_URL=mysql+pymysql://root:@localhost:3306/ai_translation
```

Format: `mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE`

### 4. Python driver

```bash
cd api_base
pip install -r requirements.txt
pip install PyMySQL
```

### 5. Auto-create tables

```bash
cd api_base
python app/models/base_db.py --check
python app/models/base_db.py
```

Or import:

```bash
mysql -u root ai_translation < init_db.sql
```

### 6. Verify

**phpMyAdmin:** tables exist under `ai_translation`.

**CLI:**

```sql
USE ai_translation;
SHOW TABLES;
```

### 7. Troubleshooting

| Error | Fix |
|-------|-----|
| Can't connect | Start MySQL service |
| Access denied | Fix credentials in `DATABASE_URL` |
| Unknown database | Run `python app/models/base_db.py` |
| Port conflict | Change MySQL port in URL |
| XAMPP `proxies_priv` | See [SETUP_MYSQL.md](../SETUP_MYSQL.md) |
| MySQL down / broken | **Auto SQLite fallback** when running `python run_api.py` (`api_base/instance/translation.db`) |

**SQLite fallback (enabled by default):** If XAMPP MySQL is unreachable, the backend switches to SQLite automatically. Disable with `DB_DISABLE_SQLITE_FALLBACK=1`. Force SQLite only: `DB_FORCE_SQLITE=1`.

### 8. Production

- Dedicated MySQL user (not `root`)
- Restrict privileges to `ai_translation` only
- Regular backups

```sql
CREATE USER 'translator'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON ai_translation.* TO 'translator'@'localhost';
FLUSH PRIVILEGES;
```

---

**See also:** [INSTALLATION_GUIDE.md](./INSTALLATION_GUIDE.md)
