// auth.js - Authentication page JavaScript
document.addEventListener("DOMContentLoaded", function () {
  // Check for Google OAuth callback
  checkGoogleOAuthResponse();

  initializeAuthPage();
});

function initializeAuthPage() {
  try {
    setupAuthTabs();
    setupPasswordToggles();
    setupPasswordStrength();
    setupFormValidation();
    checkUrlParameters();

    // Initialize Google Sign-In with new library
    setTimeout(initializeGoogleSignIn, 500);
  } catch (e) {
    console.error("Auth initialization error:", e);
  }
}

function checkUrlParameters() {
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get("tab");

    if (tab === "register") {
      setTimeout(() => {
        showAuthTab("register");
      }, 100);
      return;
    }

    // Fallback: support hash like #register
    if (
      window.location.hash &&
      window.location.hash.toLowerCase().includes("register")
    ) {
      setTimeout(() => showAuthTab("register"), 100);
    }

    // Listen for hash changes too
    window.addEventListener("hashchange", () => {
      if (
        window.location.hash &&
        window.location.hash.toLowerCase().includes("register")
      ) {
        showAuthTab("register");
      } else if (
        window.location.hash &&
        window.location.hash.toLowerCase().includes("login")
      ) {
        showAuthTab("login");
      }
    });
  } catch (e) {
    console.error("checkUrlParameters error:", e);
  }
}

function setupAuthTabs() {
  const loginTab = document.getElementById("login-tab");
  const registerTab = document.getElementById("register-tab");

  document.querySelectorAll(".auth-tab").forEach((tab) => {
    tab.addEventListener("click", function () {
      // Remove active class from all tabs and forms
      document
        .querySelectorAll(".auth-tab")
        .forEach((t) => t.classList.remove("active"));
      document
        .querySelectorAll(".auth-form")
        .forEach((f) => f.classList.remove("active"));

      // Add active class to clicked tab
      this.classList.add("active");

      // Use data-target attribute to find the target form (more robust)
      const target = this.dataset.target;
      const targetForm = target
        ? document.getElementById(target + "-tab")
        : null;
      if (targetForm) {
        targetForm.classList.add("active");
        // Scroll form into view for better UX
        setTimeout(() => {
          targetForm.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 50);
      }
    });
  });
}

function showAuthTab(tabName) {
  try {
    const loginTab = document.getElementById("login-tab");
    const registerTab = document.getElementById("register-tab");
    const loginTabBtn = document.querySelector(
      '.auth-tab[data-target="login"]',
    );
    const registerTabBtn = document.querySelector(
      '.auth-tab[data-target="register"]',
    );

    // Remove active from all
    document
      .querySelectorAll(".auth-tab")
      .forEach((t) => t.classList.remove("active"));
    document
      .querySelectorAll(".auth-form")
      .forEach((f) => f.classList.remove("active"));

    if (tabName === "login") {
      loginTab.classList.add("active");
      if (loginTabBtn) loginTabBtn.classList.add("active");
      if (registerTabBtn) registerTabBtn.classList.remove("active");
      // Scroll into view
      setTimeout(
        () => loginTab.scrollIntoView({ behavior: "smooth", block: "center" }),
        50,
      );
    } else if (tabName === "register") {
      registerTab.classList.add("active");
      if (registerTabBtn) registerTabBtn.classList.add("active");
      if (loginTabBtn) loginTabBtn.classList.remove("active");
      setTimeout(
        () =>
          registerTab.scrollIntoView({ behavior: "smooth", block: "center" }),
        50,
      );
    }
  } catch (e) {
    console.error("showAuthTab error:", e);
  }
}

function setupPasswordToggles() {
  const buttons = document.querySelectorAll(".toggle-password");
  if (!buttons || buttons.length === 0) return;

  buttons.forEach((button) => {
    button.addEventListener("click", function () {
      const input = this.previousElementSibling;
      const icon = this.querySelector("i");

      if (!input) return;

      if (input.type === "password") {
        input.type = "text";
        if (icon) {
          icon.classList.remove("fa-eye");
          icon.classList.add("fa-eye-slash");
        }
      } else {
        input.type = "password";
        if (icon) {
          icon.classList.remove("fa-eye-slash");
          icon.classList.add("fa-eye");
        }
      }
    });
  });
}

function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  const button = input.nextElementSibling;
  const icon = button.querySelector("i");

  if (input.type === "password") {
    input.type = "text";
    icon.classList.remove("fa-eye");
    icon.classList.add("fa-eye-slash");
  } else {
    input.type = "password";
    icon.classList.remove("fa-eye-slash");
    icon.classList.add("fa-eye");
  }
}

function setupPasswordStrength() {
  const passwordInput = document.getElementById("register-password");
  const strengthMeter = document.getElementById("password-strength");
  const strengthText = document.getElementById("strength-text");

  if (!passwordInput || !strengthMeter || !strengthText) return;

  passwordInput.addEventListener("input", function () {
    const password = this.value;
    const strength = calculatePasswordStrength(password);

    // Update strength meter
    strengthMeter.style.width = strength.percentage + "%";

    // Update strength text and color
    strengthText.textContent = strength.text;
    strengthMeter.style.backgroundColor = strength.color;

    // Update text color
    strengthText.style.color = strength.color;
  });
}

function calculatePasswordStrength(password) {
  let score = 0;

  // Length check
  if (password.length >= 8) score += 25;
  if (password.length >= 12) score += 25;

  // Character variety checks
  if (/[a-z]/.test(password)) score += 10; // lowercase
  if (/[A-Z]/.test(password)) score += 10; // uppercase
  if (/[0-9]/.test(password)) score += 10; // numbers
  if (/[^A-Za-z0-9]/.test(password)) score += 10; // special characters

  // Determine strength level
  let strength = {
    percentage: Math.min(score, 100),
    text: "",
    color: "",
  };

  if (score < 30) {
    strength.text = "Mật khẩu yếu";
    strength.color = "#ff4444";
  } else if (score < 60) {
    strength.text = "Mật khẩu trung bình";
    strength.color = "#ffaa00";
  } else if (score < 80) {
    strength.text = "Mật khẩu khá mạnh";
    strength.color = "#00aa44";
  } else {
    strength.text = "Mật khẩu mạnh";
    strength.color = "#00aa44";
  }

  return strength;
}

function setupFormValidation() {
  try {
    const confirmPassword = document.getElementById(
      "register-confirm-password",
    );
    const password = document.getElementById("register-password");
    if (!confirmPassword || !password) return;

    confirmPassword.addEventListener("input", function () {
      if (this.value !== password.value) {
        this.setCustomValidity("Mật khẩu xác nhận không khớp");
      } else {
        this.setCustomValidity("");
      }
    });

    password.addEventListener("input", function () {
      if (confirmPassword.value && this.value !== confirmPassword.value) {
        confirmPassword.setCustomValidity("Mật khẩu xác nhận không khớp");
      } else {
        confirmPassword.setCustomValidity("");
      }
    });
  } catch (e) {
    console.error("setupFormValidation error:", e);
  }
}

async function handleLogin(event) {
  event.preventDefault();

  const emailEl = document.getElementById("login-email");
  const passwordEl = document.getElementById("login-password");
  if (!emailEl || !passwordEl) {
    showAuthMessage("Form đăng nhập chưa sẵn sàng", "error");
    return;
  }
  const email = emailEl.value;
  const password = passwordEl.value;

  // Basic validation
  if (!email || !password) {
    showAuthMessage("Vui lòng nhập đầy đủ thông tin", "error");
    return;
  }

  // Show loading
  const submitBtn = event.target.querySelector(".auth-submit");
  if (!submitBtn) return;
  const originalText = submitBtn.innerHTML;
  submitBtn.innerHTML =
    '<i class="fas fa-spinner fa-spin"></i> Đang đăng nhập...';
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      if (data.error === "email_not_verified") {
        showAuthMessage(
          data.message || "Tài khoản chưa xác thực Gmail.",
          "error",
        );
      } else if (data.error === "account_deleted") {
        showAuthMessage(
          data.message || "Tài khoản đã bị xóa hoặc vô hiệu hóa.",
          "error",
        );
      } else {
        showAuthMessage(
          data.error || data.message || "Đăng nhập thất bại. Vui lòng thử lại.",
          "error",
        );
      }
      return;
    }

    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user", JSON.stringify(data.user));

    showAuthMessage("Đăng nhập thành công!", "success");

    setTimeout(() => {
      finishLoginRedirect(data);
    }, 1000);
  } catch (error) {
    console.error("Login error:", error);
    showAuthMessage("Có lỗi xảy ra. Vui lòng thử lại sau.", "error");
  } finally {
    submitBtn.innerHTML = originalText;
    submitBtn.disabled = false;
  }
}

let pendingRegisterEmail = "";
let pendingForgotIdentifier = "";
let pendingResetToken = "";

function finishLoginRedirect(data) {
  if (
    data &&
    (data.account_pending_delete ||
      (data.user && data.user.account_status === "pending_delete"))
  ) {
    window.location.href = "/account-pending-delete";
    return;
  }
  const params = new URLSearchParams(window.location.search);
  const returnUrl = params.get("returnUrl");
  window.location.href =
    returnUrl && returnUrl.startsWith("/") ? returnUrl : "/dashboard";
}

function ensureRegisterOtpUi() {
  let step = document.getElementById("register-otp-step");
  if (step) return step;

  const tab = document.getElementById("register-tab");
  if (!tab) return null;

  step = document.createElement("div");
  step.id = "register-otp-step";
  step.className = "otp-step";
  step.innerHTML = `
    <div class="auth-header">
      <h2>Xác thực Gmail</h2>
      <p>Mã OTP 6 số đã gửi tới <strong id="register-otp-email"></strong> (hiệu lực 5 phút)</p>
    </div>
    <div class="form-group">
      <label for="register-otp">Mã OTP</label>
      <input type="text" id="register-otp" maxlength="6" inputmode="numeric" placeholder="000000" />
    </div>
    <button type="button" class="btn-primary auth-submit" onclick="verifyRegisterOtp()">
      <i class="fas fa-check"></i> Xác nhận đăng ký
    </button>
    <button type="button" class="btn-secondary otp-resend-btn" onclick="resendRegisterOtp()">
      Gửi lại mã OTP
    </button>
    <button type="button" class="btn-link" onclick="cancelRegisterOtp()">← Quay lại form đăng ký</button>
  `;
  const footer = tab.querySelector(".auth-footer");
  if (footer) tab.insertBefore(step, footer);
  else tab.appendChild(step);
  return step;
}

function showRegisterOtpStep(email) {
  ensureRegisterOtpUi();
  const emailEl = document.getElementById("register-otp-email");
  if (emailEl) emailEl.textContent = email;
  document.querySelector(".register-form")?.classList.add("hidden");
  document.getElementById("register-otp-step")?.classList.remove("hidden");
  const otpInput = document.getElementById("register-otp");
  if (otpInput) otpInput.value = "";
}

function isGmailAddress(email) {
  return /^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?@gmail\.com$/i.test(
    (email || "").trim().toLowerCase(),
  );
}

async function handleRegister(event) {
  event.preventDefault();

  const firstName = document.getElementById("register-firstname")?.value.trim();
  const lastName = document.getElementById("register-lastname")?.value.trim();
  const username = document.getElementById("register-username")?.value.trim();
  const email = document.getElementById("register-email")?.value.trim().toLowerCase();
  const password = document.getElementById("register-password")?.value || "";
  const confirmPassword =
    document.getElementById("register-confirm-password")?.value || "";
  const agreeTerms = document.getElementById("agree-terms")?.checked;

  if (!firstName || !lastName || !username || !email || !password) {
    showAuthMessage("Vui lòng nhập đầy đủ thông tin", "error");
    return;
  }
  if (!/^[A-Za-z0-9_]{3,30}$/.test(username)) {
    showAuthMessage("Username 3–30 ký tự, chỉ chữ, số và _", "error");
    return;
  }
  if (!isGmailAddress(email)) {
    showAuthMessage("Chỉ chấp nhận email Gmail (@gmail.com)", "error");
    return;
  }
  if (password.length < 8) {
    showAuthMessage("Mật khẩu phải có ít nhất 8 ký tự", "error");
    return;
  }
  if (password !== confirmPassword) {
    showAuthMessage("Mật khẩu xác nhận không khớp", "error");
    return;
  }
  if (!agreeTerms) {
    showAuthMessage("Vui lòng đồng ý với điều khoản sử dụng", "error");
    return;
  }

  const submitBtn = event.target.querySelector(".auth-submit");
  const originalText = submitBtn.innerHTML;
  submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang gửi OTP...';
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/auth/register/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        username,
        email,
        password,
        confirm_password: confirmPassword,
        agree_terms: agreeTerms,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      showAuthMessage(data.message || data.error || "Gửi OTP thất bại", "error");
      return;
    }

    pendingRegisterEmail = email;
    showRegisterOtpStep(email);
    showAuthMessage(data.message || "Mã OTP đã được gửi.", "success");
  } catch (error) {
    console.error("Register error:", error);
    showAuthMessage("Có lỗi xảy ra. Vui lòng thử lại sau.", "error");
  } finally {
    submitBtn.innerHTML = originalText;
    submitBtn.disabled = false;
  }
}

async function verifyRegisterOtp() {
  const otp = document.getElementById("register-otp")?.value.trim();
  if (!pendingRegisterEmail || !otp) {
    showAuthMessage("Vui lòng nhập mã OTP", "error");
    return;
  }
  try {
    const res = await fetch("/api/auth/register/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: pendingRegisterEmail, otp }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAuthMessage(data.message || data.error || "OTP không hợp lệ", "error");
      return;
    }
    localStorage.setItem("token", data.access_token);
    if (data.user) localStorage.setItem("user", JSON.stringify(data.user));
    showAuthMessage("Đăng ký thành công!", "success");
    setTimeout(() => {
      window.location.href = "/dashboard";
    }, 800);
  } catch (e) {
    showAuthMessage("Lỗi kết nối: " + e.message, "error");
  }
}

async function resendRegisterOtp() {
  if (!pendingRegisterEmail) return;
  try {
    const res = await fetch("/api/auth/register/resend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: pendingRegisterEmail }),
    });
    const data = await res.json();
    showAuthMessage(
      res.ok ? data.message || "Đã gửi lại OTP" : data.message || data.error,
      res.ok ? "success" : "error",
    );
  } catch (e) {
    showAuthMessage("Lỗi kết nối: " + e.message, "error");
  }
}

function cancelRegisterOtp() {
  pendingRegisterEmail = "";
  document.getElementById("register-otp-step")?.classList.add("hidden");
  document.querySelector(".register-form")?.classList.remove("hidden");
}

function openForgotPassword(event) {
  event.preventDefault();
  pendingForgotIdentifier = "";
  pendingResetToken = "";
  document.getElementById("forgot-identifier").value = "";
  document.getElementById("forgot-otp").value = "";
  document.getElementById("forgot-new-password").value = "";
  document.getElementById("forgot-confirm-password").value = "";
  showForgotStep("request");
  document.getElementById("forgot-modal")?.classList.remove("hidden");
}

function closeForgotPassword() {
  document.getElementById("forgot-modal")?.classList.add("hidden");
}

function showForgotStep(step) {
  ["request", "otp", "reset"].forEach((s) => {
    document.getElementById(`forgot-step-${s}`)?.classList.toggle("hidden", s !== step);
  });
}

async function requestForgotPassword() {
  const identifier = document.getElementById("forgot-identifier")?.value.trim();
  if (!identifier) {
    showAuthMessage("Vui lòng nhập email hoặc username", "error");
    return;
  }
  pendingForgotIdentifier = identifier;
  try {
    const res = await fetch("/api/auth/forgot-password/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier }),
    });
    const data = await res.json();
    if (!res.ok && data.error === "email_send_failed") {
      showAuthMessage(data.message || "Không gửi được email OTP", "error");
      return;
    }
    showForgotStep("otp");
    showAuthMessage(
      data.message ||
        "Nếu thông tin hợp lệ, hệ thống đã gửi hướng dẫn khôi phục đến Gmail đã đăng ký.",
      "info",
    );
  } catch (e) {
    showAuthMessage("Lỗi kết nối: " + e.message, "error");
  }
}

async function resendForgotOtp() {
  if (!pendingForgotIdentifier) return;
  try {
    const res = await fetch("/api/auth/forgot-password/resend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier: pendingForgotIdentifier }),
    });
    const data = await res.json();
    showAuthMessage(
      res.ok ? data.message || "Đã gửi lại OTP" : data.message || data.error,
      res.ok ? "success" : "error",
    );
  } catch (e) {
    showAuthMessage("Lỗi kết nối: " + e.message, "error");
  }
}

async function verifyForgotOtp() {
  const otp = document.getElementById("forgot-otp")?.value.trim();
  if (!pendingForgotIdentifier || !otp) {
    showAuthMessage("Vui lòng nhập mã OTP", "error");
    return;
  }
  try {
    const res = await fetch("/api/auth/forgot-password/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier: pendingForgotIdentifier, otp }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAuthMessage(data.message || data.error || "OTP không hợp lệ", "error");
      return;
    }
    pendingResetToken = data.reset_token;
    showForgotStep("reset");
    showAuthMessage("Xác thực OTP thành công. Hãy đặt mật khẩu mới.", "success");
  } catch (e) {
    showAuthMessage("Lỗi kết nối: " + e.message, "error");
  }
}

async function submitForgotReset() {
  const password = document.getElementById("forgot-new-password")?.value || "";
  const confirm = document.getElementById("forgot-confirm-password")?.value || "";
  if (!pendingResetToken) {
    showAuthMessage("Phiên đặt lại mật khẩu không hợp lệ", "error");
    return;
  }
  if (password.length < 8) {
    showAuthMessage("Mật khẩu phải có ít nhất 8 ký tự", "error");
    return;
  }
  if (password !== confirm) {
    showAuthMessage("Mật khẩu xác nhận không khớp", "error");
    return;
  }
  try {
    const res = await fetch("/api/auth/forgot-password/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reset_token: pendingResetToken,
        password,
        confirm_password: confirm,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      showAuthMessage(data.message || data.error || "Đặt lại mật khẩu thất bại", "error");
      return;
    }
    closeForgotPassword();
    showAuthTab("login");
    showAuthMessage(data.message || "Đặt lại mật khẩu thành công", "success");
  } catch (e) {
    showAuthMessage("Lỗi kết nối: " + e.message, "error");
  }
}

function loadGoogleAuth() {
  // DEPRECATED - using new Google Sign-In library instead
  console.log("loadGoogleAuth() deprecated - use initializeGoogleSignIn()");
}

function initializeGoogleSignIn() {
  // Initialize Google Sign-In with new library (google.accounts.id)
  if (typeof google === "undefined" || !google.accounts) {
    console.warn("Google Sign-In library not ready, retrying...");
    setTimeout(initializeGoogleSignIn, 500);
    return;
  }

  try {
    const clientId = window.GOOGLE_CLIENT_ID;

    if (!clientId) {
      console.error("GOOGLE_CLIENT_ID not configured");
      showAuthMessage("Google Client ID chưa được cấu hình", "error");
      return;
    }

    console.log(
      "Initializing Google Sign-In with clientId:",
      clientId.substring(0, 20) + "...",
    );

    google.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogleSignInCallback,
    });

    console.log("Google Sign-In initialized successfully");
  } catch (e) {
    console.error("Error initializing Google Sign-In:", e);
    showAuthMessage("Lỗi khởi tạo Google Sign-In: " + e.message, "error");
  }
}

function handleGoogleSignInCallback(response) {
  console.log("Google Sign-In response received");

  if (!response.credential) {
    console.error("No credential in response");
    showAuthMessage("Không nhận được token từ Google", "error");
    return;
  }

  const id_token = response.credential;

  // Send token to backend
  sendGoogleTokenToBackend(id_token);
}

/**
 * Detect if the current browser is an in-app WebView (Facebook, Instagram, Zalo, etc.)
 * Google blocks OAuth in these embedded browsers with 403 disallowed_useragent.
 */
function isInAppBrowser() {
  var ua = navigator.userAgent || navigator.vendor || "";
  // Common in-app browser signatures
  return /FBAN|FBAV|Instagram|Zalo|Line\/|Twitter|Snapchat|Pinterest|MicroMessenger|WeChat|Musical_ly|BytedApp|ByteLocale|TikTok|OKApp|GSA\/|CriOS.*wv|; wv\)/i.test(
    ua,
  );
}

function signInWithGoogle() {
  console.log("signInWithGoogle called - GSI popup flow");

  // Detect in-app browsers that Google blocks
  if (isInAppBrowser()) {
    var currentUrl = window.location.href;
    showAuthMessage(
      "Trình duyệt trong ứng dụng không hỗ trợ đăng nhập Google. " +
        'Hãy mở bằng Chrome/Safari: nhấn "⋮" hoặc "..." → "Mở trong trình duyệt".',
      "error",
    );
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(currentUrl);
      }
    } catch (e) {
      /* ignore */
    }
    try {
      window.open(currentUrl, "_system");
    } catch (e) {
      /* ignore */
    }
    return;
  }

  const clientId = window.GOOGLE_CLIENT_ID;
  if (!clientId) {
    showAuthMessage(
      "Google Client ID chưa được cấu hình. Restart backend và tải lại trang.",
      "error",
    );
    return;
  }

  waitForGoogleOAuth2(6000)
    .then(() => {
      const client = google.accounts.oauth2.initCodeClient({
        client_id: clientId,
        scope: "openid email profile",
        ux_mode: "popup",
        callback: (response) => {
          if (response.error) {
            showAuthMessage("Google: " + response.error, "error");
            return;
          }
          if (response.code) {
            exchangeGoogleCode(response.code);
          }
        },
      });
      client.requestCode();
    })
    .catch((e) => {
      console.warn("GSI popup unavailable, fallback redirect:", e);
      startGoogleOAuthRedirect();
    });
}

function waitForGoogleOAuth2(timeoutMs) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    (function tick() {
      if (
        typeof google !== "undefined" &&
        google.accounts &&
        google.accounts.oauth2
      ) {
        resolve();
        return;
      }
      if (Date.now() - start > timeoutMs) {
        reject(new Error("Google Sign-In chưa tải xong"));
        return;
      }
      setTimeout(tick, 200);
    })();
  });
}

async function exchangeGoogleCode(code) {
  showAuthMessage("Đang xác thực...", "info");
  try {
    const res = await fetch("/api/auth/google/code", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    if (res.status === 404) {
      showAuthMessage(
        "Backend chưa cập nhật. Trong terminal: Ctrl+C rồi chạy lại python api_base/run_api.py",
        "error",
      );
      return;
    }
    if (res.ok && data.access_token) {
      localStorage.setItem("token", data.access_token);
      if (data.user) {
        localStorage.setItem("user", JSON.stringify(data.user));
      } else {
        const profileRes = await fetch("/api/auth/profile", {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (profileRes.ok) {
          localStorage.setItem("user", JSON.stringify(await profileRes.json()));
        }
      }
      showAuthMessage("Đăng nhập Google thành công!", "success");
      setTimeout(() => finishLoginRedirect(data), 800);
    } else if (data.error === "account_deleted") {
      showAuthMessage(
        data.message || "Tài khoản đã bị xóa hoặc vô hiệu hóa.",
        "error",
      );
    } else {
      showAuthMessage(
        data.message || data.error || "Đăng nhập Google thất bại",
        "error",
      );
    }
  } catch (e) {
    showAuthMessage("Lỗi kết nối backend: " + e.message, "error");
  }
}

function startGoogleOAuthRedirect() {
  fetch("/api/auth/google/authorize", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin: window.location.origin }),
  })
    .then((r) =>
      r.json().then((data) => ({ ok: r.ok, status: r.status, data })),
    )
    .then(({ ok, status, data }) => {
      if (!ok) {
        showAuthMessage(
          data.message ||
            data.error ||
            `Không lấy được URL đăng nhập Google (HTTP ${status})`,
          "error",
        );
        return;
      }
      if (data.auth_url) {
        if (data.redirect_uri) {
          console.log("OAuth redirect_uri:", data.redirect_uri);
        }
        console.log(
          "Redirecting to Google OAuth:",
          data.auth_url.substring(0, 100) + "...",
        );
        window.location.href = data.auth_url;
      } else {
        showAuthMessage(
          "Không thể lấy URL xác thực từ Google: " + (data.error || "unknown"),
          "error",
        );
      }
    })
    .catch((e) => {
      console.error("Error getting auth URL:", e);
      showAuthMessage("Lỗi kết nối backend: " + e.message, "error");
    });
}

function generateNonce() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode.apply(null, array));
}

function handleGooglePopupMessage(event) {
  if (event.origin !== window.location.origin) return;

  if (event.data && event.data.type === "google-signin") {
    sendGoogleTokenToBackend(event.data.idToken);
    window.removeEventListener("message", handleGooglePopupMessage);
  }
}

// Check for Google OAuth response in URL (token in query params)
function checkGoogleOAuthResponse() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");

  if (token) {
    console.log("Found token in URL from OAuth callback");
    localStorage.setItem("token", token);

    // Fetch user profile
    fetch("/api/auth/profile", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((profile) => {
        localStorage.setItem("user", JSON.stringify(profile));
        console.log("User profile loaded:", profile.email);

        // Clean URL and stay on dashboard
        window.history.replaceState(
          {},
          document.title,
          window.location.pathname,
        );
      })
      .catch((e) => {
        console.warn("Could not fetch profile:", e);
        // Even if profile fetch fails, token is saved
        window.history.replaceState(
          {},
          document.title,
          window.location.pathname,
        );
      });
  }

  // Check for OAuth errors
  const error = params.get("error");
  if (error) {
    console.error("OAuth error:", error);
    if (error === "account_deleted") {
      showAuthMessage(
        "Tài khoản đã bị xóa hoặc vô hiệu hóa. Không thể đăng nhập.",
        "error",
      );
    } else if (error === "disallowed_useragent") {
      showAuthMessage(
        "Trình duyệt hiện tại không được Google cho phép đăng nhập. " +
          'Vui lòng mở trang này bằng Chrome hoặc Safari (nhấn "⋮" → "Mở trong trình duyệt").',
        "error",
      );
    } else if (error === "redirect_uri_mismatch") {
      fetch("/api/auth/config")
        .then((r) => r.json())
        .then((cfg) => {
          const hints = (cfg.google_redirect_uri_hints || []).join("\n• ");
          showAuthMessage(
            "Redirect URI chưa khớp Google Cloud Console. " +
              "Mở http://127.0.0.1:5055/auth và thử lại. " +
              "Thêm các URI sau vào OAuth Client 1086485437554-... → Authorized redirect URIs:\n• " +
              hints,
            "error",
          );
        })
        .catch(() => {
          showAuthMessage(
            "Redirect URI chưa khớp Google Cloud Console. " +
              "Mở http://127.0.0.1:5055/auth (không dùng IP LAN). " +
              "Thêm http://127.0.0.1:5055/api/auth/google/callback vào Authorized redirect URIs.",
            "error",
          );
        });
    } else {
      showAuthMessage("Lỗi đăng nhập Google: " + error, "error");
    }
  }
}

async function sendGoogleTokenToBackend(id_token) {
  showAuthMessage("Đang xác thực...", "info");

  try {
    console.log(
      "Sending token to /api/auth/google:",
      id_token.substring(0, 50) + "...",
    );

    const res = await fetch("/api/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: id_token }),
    });

    console.log("Response status:", res.status);
    const responseText = await res.text();
    console.log("Response text:", responseText);

    let data;
    try {
      data = JSON.parse(responseText);
    } catch (e) {
      console.error("Failed to parse response as JSON:", e);
      showAuthMessage(
        "Lỗi phản hồi từ backend (không phải JSON): " +
          responseText.substring(0, 100),
        "error",
      );
      return;
    }

    if (res.ok && data.access_token) {
      localStorage.setItem("token", data.access_token);
      if (data.user) {
        localStorage.setItem("user", JSON.stringify(data.user));
      } else {
        const profileRes = await fetch("/api/auth/profile", {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (profileRes.ok) {
          localStorage.setItem("user", JSON.stringify(await profileRes.json()));
        }
      }

      showAuthMessage("Đăng nhập Google thành công!", "success");
      setTimeout(() => finishLoginRedirect(data), 800);
    } else if (data.error === "account_deleted") {
      showAuthMessage(
        data.message || "Tài khoản đã bị xóa hoặc vô hiệu hóa.",
        "error",
      );
    } else {
      showAuthMessage(
        data.error || "Đăng nhập thất bại: " + res.status,
        "error",
      );
    }
  } catch (error) {
    console.error("Backend auth error:", error);
    showAuthMessage("Lỗi kết nối backend: " + error.message, "error");
  }
}

function showAuthMessage(message, type = "info") {
  // Remove existing messages
  const existingMessages = document.querySelectorAll(".auth-message");
  existingMessages.forEach((msg) => msg.remove());

  // Create new message
  const messageDiv = document.createElement("div");
  messageDiv.className = `auth-message ${type}`;
  messageDiv.innerHTML = `
        <i class="fas ${type === "success" ? "fa-check-circle" : type === "error" ? "fa-exclamation-circle" : "fa-info-circle"}"></i>
        ${message}
    `;

  // Add to auth container
  const authContainer = document.querySelector(".auth-container");
  authContainer.insertBefore(messageDiv, authContainer.firstChild);

  // Auto remove after 5 seconds
  setTimeout(() => {
    if (messageDiv.parentNode) {
      messageDiv.remove();
    }
  }, 5000);
}

// Add auth message styles
const authStyle = document.createElement("style");
authStyle.textContent = `
    .auth-message {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 500;
        animation: slideDown 0.3s ease;
    }

    .auth-message.success {
        background: rgba(76, 175, 80, 0.1);
        border: 1px solid #4CAF50;
        color: #4CAF50;
    }

    .auth-message.error {
        background: rgba(244, 67, 54, 0.1);
        border: 1px solid #f44336;
        color: #f44336;
    }

    .auth-message.info {
        background: rgba(33, 150, 243, 0.1);
        border: 1px solid #2196F3;
        color: #2196F3;
    }

    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .password-input {
        position: relative;
    }

    .toggle-password {
        position: absolute;
        right: 10px;
        top: 50%;
        transform: translateY(-50%);
        background: none;
        border: none;
        color: rgba(255, 255, 255, 0.6);
        cursor: pointer;
        padding: 5px;
    }

    .password-strength {
        margin-top: 8px;
    }

    .strength-meter {
        height: 4px;
        background: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
        overflow: hidden;
        margin-bottom: 4px;
    }

    .strength-fill {
        height: 100%;
        border-radius: 2px;
        transition: width 0.3s ease, background-color 0.3s ease;
    }
`;
document.head.appendChild(authStyle);
