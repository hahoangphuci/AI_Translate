// ============================================================
// ⚙️ FILE CẤU HÌNH FLUTTER APP
// ⚠️ Thêm file này vào .gitignore nếu chứa thông tin nhạy cảm
// ============================================================

class AppConfig {
  // ── BASE URLs ──────────────────────────────────────────────
  /// URL backend FastAPI (không có dấu / ở cuối)
  static const String apiBaseUrl = 'https://buddhichat.adhightech.com/api/v1';

  /// URL frontend web (không có dấu / ở cuối)
  static const String webBaseUrl = 'https://buddhichat.adhightech.com';

  // ── OAUTH DEEP LINK ────────────────────────────────────────
  /// Scheme cho Deep Link callback sau Google OAuth
  /// Phải khớp với android:scheme trong AndroidManifest.xml
  static const String callbackScheme = 'phatgiaochatbot';

  // ── APP INFO ───────────────────────────────────────────────
  static const String appName = 'Chatbot Phật Giáo';
  static const String appVersion = '1.0.0';

  // ── COMPUTED ───────────────────────────────────────────────
  /// URL endpoint đăng nhập Google dành cho Flutter
  static String get googleLoginFlutterUrl =>
      '$apiBaseUrl/auth/google/login/flutter?callback_scheme=$callbackScheme';
}
