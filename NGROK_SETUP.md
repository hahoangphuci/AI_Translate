# Hướng dẫn dùng ngrok cho App Mobile

Backend Flask (`run_api.py`) chạy port **5055** và phục vụ cả frontend + API. Ngrok expose port này ra internet (HTTPS) để điện thoại và Google OAuth truy cập được.

## Bước 1 — Lấy ngrok authtoken (miễn phí)

1. Đăng ký: https://dashboard.ngrok.com/signup  
2. Copy authtoken: https://dashboard.ngrok.com/get-started/your-authtoken  
3. Thêm vào `api_base/.env`:

```env
NGROK_AUTHTOKEN=your_token_here
```

## Bước 2 — Khởi động server + ngrok

**Terminal 1** — Backend:

```powershell
cd api_base
python run_api.py
```

**Terminal 2** — Ngrok (tự cập nhật `.env`):

```powershell
.\scripts\ngrok-start.ps1
```

Script sẽ in URL dạng `https://xxxx.ngrok-free.app` và lưu vào `ngrok-url.txt`.

## Bước 3 — Google OAuth

Vào [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials** → OAuth 2.0 Client → **Authorized redirect URIs**, thêm:

```
https://xxxx.ngrok-free.app/api/auth/google/callback
```

(thay `xxxx` bằng subdomain ngrok thực tế — script in ra khi chạy)

Sau đó **restart backend** (`python run_api.py`) để đọc `.env` mới.

## Bước 4 — Build APK trỏ ngrok

```powershell
.\scripts\build-apk-ngrok.ps1
```

APK output:

```
app_web_view/build/app/outputs/flutter-apk/app-release.apk
```

## Lưu ý

| Vấn đề | Giải pháp |
|--------|-----------|
| URL ngrok đổi mỗi lần restart (free) | Chạy lại `ngrok-start.ps1` + `build-apk-ngrok.ps1` + cập nhật Google redirect URI |
| Trang cảnh báo ngrok | App đã gửi header `ngrok-skip-browser-warning` tự động |
| Backend không kết nối | Đảm bảo `run_api.py` đang chạy trước khi mở app |
| Muốn URL cố định | Nâng cấp ngrok paid (reserved domain) |

## Test nhanh trên trình duyệt

Mở URL ngrok trên Chrome — nếu thấy trang chủ AI Translator là server đã OK.
