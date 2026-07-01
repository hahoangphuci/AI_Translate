# AI Translator — Mobile App

Ứng dụng mobile Flutter bọc frontend web **AI Translation System** bằng WebView, hỗ trợ đăng nhập Google qua Chrome Custom Tab / Safari View (tránh lỗi `disallowed_useragent` của Google trong WebView).

## Yêu cầu

- [Flutter SDK](https://docs.flutter.dev/get-started/install) 3.10+
- Backend + frontend đang chạy (Docker hoặc local)

```bash
# Từ thư mục gốc dự án
docker compose up -d
```

Frontend mặc định: `http://localhost` (port 80)

## Chạy app

```bash
cd app_web_view
flutter pub get
flutter run
```

### URL server tùy chỉnh

| Môi trường                   | BASE_URL mặc định                        |
| ---------------------------- | ---------------------------------------- |
| Android Emulator             | `http://10.0.2.2`                        |
| iOS Simulator                | `http://localhost`                       |
| Điện thoại thật (cùng Wi‑Fi) | IP máy tính, ví dụ `http://192.168.1.10` |

```bash
# Android emulator / thiết bị thật trỏ tới IP LAN
flutter run --dart-define=BASE_URL=http://192.168.1.10

# Production
flutter run --dart-define=BASE_URL=https://yourdomain.com
```

## Tính năng

- Nhúng toàn bộ giao diện web (dịch văn bản, tài liệu, lịch sử, thanh toán…)
- Đăng nhập Google qua trình duyệt hệ thống (Custom Tab)
- Nút **Tải lại** và **Trang chủ** trên AppBar
- Nút Back Android quay lại trang trước trong WebView
- Màn hình lỗi khi không kết nối được server

## Dùng ngrok (điện thoại thật + Google OAuth)

Xem hướng dẫn đầy đủ: [NGROK_SETUP.md](../NGROK_SETUP.md)

```powershell
# Terminal 1
cd api_base && python run_api.py

# Terminal 2 (sau khi thêm NGROK_AUTHTOKEN vào api_base/.env)
.\scripts\ngrok-start.ps1
.\scripts\build-apk-ngrok.ps1
```

## Cấu trúc mã nguồn

```
lib/
  main.dart                 # Entry point
  config/app_config.dart    # BASE_URL, OAuth callback
  screens/webview_screen.dart
  services/oauth_service.dart
  services/preferences_service.dart
```

## Lưu ý OAuth Google

1. `GOOGLE_REDIRECT_URI` trên backend phải trỏ tới callback server (ví dụ `http://localhost/api/auth/google/callback`).
2. Sau đăng nhập, backend redirect về `/dashboard?token=...` — app bắt URL này qua Custom Tab.
3. Trên thiết bị thật, dùng IP/domain công khai thay vì `localhost`.

## Icon app

Logo lấy từ `assets/logo.png`. Tạo lại icon launcher:

```bash
dart run flutter_launcher_icons
```
