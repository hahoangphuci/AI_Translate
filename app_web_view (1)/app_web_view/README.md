# AI Translator — Mobile App

Ứng dụng Flutter bọc web **AI Translation System** bằng WebView.

**Server hiện tại:** `https://legacy-unpaid-sternum.ngrok-free.dev`

## Tính năng

- Toàn bộ giao diện web (dịch văn bản, tài liệu, lịch sử, thanh toán…)
- Đăng nhập Google qua Chrome Custom Tab (tránh lỗi `disallowed_useragent`)
- Upload file tài liệu trong WebView
- Nút **Trang chủ** / **Tải lại** trên AppBar
- Nút Back Android quay lại trang trước
- Header `ngrok-skip-browser-warning` tự động

## Cấu trúc

```
lib/
  main.dart
  config/app_config.dart
  config/generated_base_url.dart
```

## Build APK

```powershell
# Cần JDK 17 (Java 25 gây lỗi Gradle)
$env:JAVA_HOME = "$env:LOCALAPPDATA\jdk-17"

cd "app_web_view (1)\app_web_view"
flutter pub get
flutter build apk --release --dart-define=BASE_URL=https://legacy-unpaid-sternum.ngrok-free.dev
```

Hoặc dùng script (đọc URL từ `ngrok-url.txt`):

```powershell
.\scripts\build-apk-ngrok.ps1
```

APK output:

```
app_web_view (1)/app_web_view/build/app/outputs/flutter-apk/app-release.apk
```

Link tải qua ngrok (khi backend đang chạy):

```
https://legacy-unpaid-sternum.ngrok-free.dev/downloads/AI_Translator_v1.0.0.apk
```

## Google OAuth cho app mobile

1. Google Cloud Console → OAuth 2.0 Client → **Authorized redirect URIs**:
   ```
   https://legacy-unpaid-sternum.ngrok-free.dev/api/auth/google/callback
   ```
2. Backend `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FRONTEND_URL=https://legacy-unpaid-sternum.ngrok-free.dev`
3. App dùng deep link scheme `aitranslator://oauth?token=...` (Custom Tab) — backend đã hỗ trợ `callback_scheme`.

## Lưu ý

- URL ngrok free đổi mỗi lần restart → cập nhật `lib/config/generated_base_url.dart`, Google redirect URI, build lại APK.
- Backend phải chạy (`python run_api.py`) trước khi mở app.
