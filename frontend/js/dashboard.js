// auth.js - Authentication module

/**
 * Download helper — hoạt động trên cả desktop browser và Flutter WebView (Android).
 * Trong WebView, blob URL không download được → gọi Flutter JS channel để mở Chrome ngoài.
 */
async function triggerDownload(downloadUrl, filename) {
  // Đảm bảo URL tuyệt đối
  const absUrl = downloadUrl.startsWith("http")
    ? downloadUrl
    : window.location.origin +
      (downloadUrl.startsWith("/") ? "" : "/") +
      downloadUrl;

  // Flutter WebView: dùng JS channel để mở Chrome ngoài (hỗ trợ download thật sự)
  if (window.flutter_inappwebview) {
    try {
      await window.flutter_inappwebview.callHandler(
        "flutterDownload",
        absUrl,
        filename || "",
      );
      return;
    } catch (e) {
      console.warn("Flutter download handler failed, fallback:", e);
    }
  }

  // Desktop browser: fetch → blob → <a download> click
  try {
    const resp = await fetch(downloadUrl);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "translated_file";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (e) {
    console.error("Download failed:", e);
    window.open(downloadUrl, "_blank");
  }
}

const PLAN_TOKEN_CAPS = { free: 5000, pro: 120000, promax: 300000 };

function getPlanTokenCap(plan) {
  const caps = window.SITE_PLAN_CAPS || PLAN_TOKEN_CAPS;
  const key = String(plan || "free").toLowerCase();
  return caps[key] || PLAN_TOKEN_CAPS[key] || 5000;
}

/** balance = token còn lại; usedPct = % đã dùng trong hạn mức gói */
function calcTokenUsage(balance, cap) {
  const bal = Math.max(0, parseInt(balance, 10) || 0);
  const planCap = Math.max(1, parseInt(cap, 10) || 5000);
  const used = Math.max(0, planCap - Math.min(bal, planCap));
  const usedPct = Math.min(100, Math.round((used / planCap) * 100));
  const remainingPct = Math.min(
    100,
    Math.round((Math.min(bal, planCap) / planCap) * 100),
  );
  return { balance: bal, cap: planCap, used, usedPct, remainingPct };
}

function updateTokenUsageUI(plan, tokenBalance) {
  const cap = getPlanTokenCap(plan);
  const usage = calcTokenUsage(tokenBalance, cap);

  const usedEl = document.getElementById("usedToday");
  const quotaEl = document.getElementById("dailyQuota");
  const fillEl = document.getElementById("usageFill");
  const usageEl = document.getElementById("usagePercent");

  if (usedEl) {
    usedEl.textContent = usage.balance.toLocaleString("vi-VN");
    usedEl.dataset.balance = String(usage.balance);
  }
  if (quotaEl) {
    quotaEl.textContent = usage.cap.toLocaleString("vi-VN") + " token";
    quotaEl.dataset.cap = String(usage.cap);
  }
  if (fillEl) fillEl.style.width = usage.remainingPct + "%";
  if (usageEl) usageEl.textContent = usage.usedPct + "%";
}

function applyTokenBalanceFromResponse(data, authManager) {
  if (!data || data.token_balance == null || !authManager) return;
  const plan = authManager.profile?.plan || "free";
  updateTokenUsageUI(plan, data.token_balance);
  if (authManager.profile) {
    authManager.profile.token_balance = data.token_balance;
  }
}

class AuthManager {
  constructor() {
    this.token = localStorage.getItem("token");
    this.profile = null;
  }

  isAuthenticated() {
    // Re-check localStorage in case token changes between page loads
    this.token = localStorage.getItem("token");
    return !!this.token;
  }

  redirectToLogin() {
    window.location.href = "/auth";
  }

  logout() {
    localStorage.removeItem("token");
    this.updateAuthUI();
    // Redirect to auth page after logout
    setTimeout(() => {
      window.location.href = "/auth";
    }, 500);
  }

  getAuthHeaders() {
    // Return authorization header if token is present and is a real JWT (not fake dev token)
    this.token = localStorage.getItem("token");
    if (this.token && !String(this.token).startsWith("fake")) {
      return { Authorization: `Bearer ${this.token}` };
    }
    return {};
  }

  async loadUserInfo() {
    // If no token, skip
    this.token = localStorage.getItem("token");
    if (!this.token) return null;

    // Development helper: if token starts with 'fake', load profile from localStorage to avoid hitting backend JWT checks
    if (this.token.startsWith && this.token.startsWith("fake")) {
      try {
        const cached = localStorage.getItem("user");
        const parsed = cached ? JSON.parse(cached) : null;
        const nameEl = document.getElementById("userName");
        if (nameEl) nameEl.textContent = (parsed && parsed.name) || "User";
        return parsed || { name: "User" };
      } catch (e) {
        console.warn("Failed to parse cached user", e);
        return { name: "User" };
      }
    }

    try {
      const response = await fetch("/api/auth/profile", {
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });

      if (!response.ok) {
        console.warn("Profile fetch failed with status", response.status);
        // If token invalid or unprocessable, force logout and return null
        if ([401, 422].includes(response.status)) {
          this.logout();
          return null;
        }
        return null;
      }

      const data = await response.json();
      this.profile = data;
      const nameEl = document.getElementById("userName");
      if (nameEl) nameEl.textContent = data.name || "User";

      // Update plan UI if present
      try {
        if (data.plan_name) {
          const planNameEl = document.getElementById("planName");
          const planSub = document.getElementById("planSubtitle");
          if (planNameEl) planNameEl.textContent = data.plan_name;
          if (planSub)
            planSub.textContent =
              data.plan === "free"
                ? "Gói miễn phí"
                : data.plan === "pro"
                  ? "Gói Pro"
                  : data.plan === "promax"
                    ? "Gói ProMax"
                    : data.plan;

          // Update plan card icon style
          const iconWrap = document.getElementById("planIconWrap");
          if (iconWrap) {
            iconWrap.className = "plan-pill-icon";
            if (data.plan === "pro") {
              iconWrap.className += " icon-pro";
              iconWrap.innerHTML = '<i class="fas fa-bolt"></i>';
            } else if (data.plan === "promax") {
              iconWrap.className += " icon-promax";
              iconWrap.innerHTML = '<i class="fas fa-crown"></i>';
            } else {
              iconWrap.innerHTML = '<i class="fas fa-leaf"></i>';
            }
          }

          updateTokenUsageUI(data.plan, data.token_balance);
          syncTranslationProvidersForPlan(data.plan);
        }
      } catch (e) {
        console.warn("Failed to update plan UI", e);
      }

      return data;
    } catch (error) {
      console.error("Error loading user info:", error);
      const nameEl = document.getElementById("userName");
      if (nameEl) nameEl.textContent = "User";
      return null;
    }
  }

  updateAuthUI() {
    const loginBtn = document.getElementById("loginBtn");
    const logoutBtn = document.getElementById("logoutBtn");
    const userInfo = document.querySelector(".user-info");

    if (this.isAuthenticated()) {
      // User is logged in
      if (loginBtn) loginBtn.style.display = "none";
      if (logoutBtn) logoutBtn.style.display = "inline-block";
      if (userInfo) userInfo.style.display = "flex";
    } else {
      // User is not logged in
      if (loginBtn) loginBtn.style.display = "inline-block";
      if (logoutBtn) logoutBtn.style.display = "none";
      if (userInfo) userInfo.style.display = "none";
    }
  }
}

// UI Manager
class UIManager {
  static uiT(key, fallback) {
    if (window.SiteI18n && typeof window.SiteI18n.t === "function") {
      const value = window.SiteI18n.t(key);
      if (value && value !== key) return value;
    }
    return fallback != null ? fallback : key;
  }
  static showTab(tabName) {
    try {
      console.debug("[UI] showTab called for", tabName);
      const normalizedTab = tabName || "translate";
      try {
        sessionStorage.setItem("dashboard_active_tab", normalizedTab);
      } catch {
        /* ignore */
      }
      document.documentElement.removeAttribute("data-dashboard-tab");
      // Hide all tabs
      document.querySelectorAll(".tab-content").forEach((tab) => {
        tab.classList.remove("active");
      });

      // Remove active class from all buttons
      document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.classList.remove("active");
      });

      // Show selected tab (guard if missing)
      const tabEl = document.getElementById(tabName + "-tab");
      if (tabEl) {
        tabEl.classList.add("active");
      } else {
        console.warn("[UI] Tab element not found:", tabName + "-tab");
      }

      // Add active class to the corresponding button (do not rely on global event)
      let button =
        document.querySelector(`.tab-btn[onclick="showTab('${tabName}')"]`) ||
        document.querySelector(`.tab-btn[onclick='showTab("${tabName}")']`);
      // Fallback: match by normalized text
      if (!button) {
        const normalized = (tabName || "").toLowerCase().replace(/\s+/g, "");
        button = Array.from(document.querySelectorAll(".tab-btn")).find((b) => {
          const text = (b.textContent || "").toLowerCase().replace(/\s+/g, "");
          return text === normalized;
        });
      }
      if (button) button.classList.add("active");
      else console.warn("[UI] Tab button not found for", tabName);
    } catch (err) {
      console.error("[UI] showTab error:", err);
    }
  }

  static showLoading(button, text) {
    if (text == null) text = UIManager.uiT("msg.processing", "Processing...");
    const originalText = button.innerHTML;
    button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
    button.disabled = true;
    return originalText;
  }

  static hideLoading(button, originalText) {
    button.innerHTML = originalText;
    button.disabled = false;
  }

  static showAlert(message, type = "error") {
    if (typeof showToast === "function") {
      showToast(message, type === "success" ? "success" : "error");
      return;
    }
    UIManager.showNotification(
      message,
      type === "success" ? "success" : "error",
    );
  }

  static showNotification(message, type = "info") {
    const notificationArea = document.getElementById("notificationArea");
    const notificationText = document.getElementById("notificationText");

    if (notificationArea && notificationText) {
      // Update notification content
      notificationText.textContent = message;

      // Update icon based on type
      const iconElement = notificationArea.querySelector("i");
      switch (type) {
        case "success":
          iconElement.className = "fas fa-check-circle";
          notificationArea.style.borderColor = "rgba(40, 167, 69, 0.3)";
          notificationArea.style.background = "rgba(40, 167, 69, 0.1)";
          break;
        case "error":
          iconElement.className = "fas fa-exclamation-triangle";
          notificationArea.style.borderColor = "rgba(220, 53, 69, 0.3)";
          notificationArea.style.background = "rgba(220, 53, 69, 0.1)";
          break;
        default:
          iconElement.className = "fas fa-info-circle";
          notificationArea.style.borderColor = "rgba(255, 215, 0, 0.3)";
          notificationArea.style.background = "rgba(255, 215, 0, 0.1)";
      }

      // Show notification
      notificationArea.style.display = "block";

      // Auto hide after 5 seconds
      setTimeout(() => {
        UIManager.hideNotification();
      }, 5000);
    } else {
      // Fallback to old notification system
      this.showToastNotification(message, type);
    }
  }

  static hideNotification() {
    const notificationArea = document.getElementById("notificationArea");
    if (notificationArea) {
      notificationArea.style.display = "none";
    }
  }

  static showToastNotification(message, type = "info") {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;
    notification.innerHTML = `
            <i class="fas ${type === "success" ? "fa-check-circle" : type === "error" ? "fa-exclamation-circle" : "fa-info-circle"}"></i>
            ${message}
        `;

    // Add to page
    document.body.appendChild(notification);

    // Show animation
    setTimeout(() => notification.classList.add("show"), 100);

    // Remove after 3 seconds
    setTimeout(() => {
      notification.classList.remove("show");
      setTimeout(() => document.body.removeChild(notification), 300);
    }, 3000);
  }

  static showError(message) {
    const errorDiv = document.getElementById("translationError");
    const errorText = document.getElementById("errorText");

    if (errorDiv && errorText) {
      errorText.textContent = message;
      errorDiv.style.display = "flex";
    } else {
      this.showNotification(message, "error");
    }
  }

  static hideError() {
    const errorDiv = document.getElementById("translationError");
    if (errorDiv) {
      errorDiv.style.display = "none";
    }
  }

  static showSuccess(message) {
    const successDiv = document.getElementById("uploadSuccess");
    const successText = document.getElementById("successText");

    if (successDiv && successText) {
      successText.textContent = message;
      successDiv.style.display = "flex";
    } else {
      this.showNotification(message, "success");
    }
  }

  static hideSuccess() {
    const successDiv = document.getElementById("uploadSuccess");
    if (successDiv) {
      successDiv.style.display = "none";
    }
  }
}

// Translation Manager
class TranslationManager {
  constructor(authManager) {
    this.auth = authManager;
    this.setupEventListeners();
  }

  setupEventListeners() {
    const inputText = document.getElementById("inputText");
    const richInput = document.getElementById("richInput");
    const charCount = document.getElementById("charCount");
    const richToggle = document.getElementById("richToggle");
    const preserveCheck = document.getElementById("preserveFormatting");
    const toolbar = document.getElementById("editorToolbar");

    const updateCharCount = () => {
      let text = "";
      if (richToggle && richToggle.checked && richInput)
        text = richInput.innerText || "";
      else if (inputText) text = inputText.value || "";
      const count = text.length;
      charCount.textContent = count;
      charCount.style.color =
        count > 5000 ? "#00A8FF" : "rgba(255,255,255,0.7)";
    };

    if (inputText) inputText.addEventListener("input", updateCharCount);
    if (richInput) {
      richInput.addEventListener("input", (e) => {
        updateCharCount();
        try {
          richInput.dataset._isPristine = "false";
        } catch (er) {}
      });
    }

    // Small helpers: escape plaintext for HTML and convert HTML back to plain text (preserve newlines)
    const escapeForHTML = (s) =>
      String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");

    const htmlToPlainText = (html) => {
      const tmp = document.createElement("div");
      // Convert <br> to newlines first so they are preserved
      tmp.innerHTML = (html || "").replace(/<br\s*\/?>(\s*)/gi, "<br />");
      // Then read textContent to get proper unescaped text with newlines
      // Replace <br> tags with newline characters
      const withLineBreaks = String(tmp.innerHTML).replace(
        /<br\s*\/?>/gi,
        "\n",
      );
      tmp.innerHTML = withLineBreaks;
      return tmp.textContent || tmp.innerText || "";
    };

    // Helper to copy plain -> rich, preserving any previous saved HTML and keeping original plaintext intact
    const loadPlainToRich = () => {
      // If we have stored HTML (user previously edited and saved), reuse it
      const storedHtml = richInput.dataset._lastHtml;
      if (storedHtml) {
        richInput.innerHTML = storedHtml;
        // Mark as not pristine because stored HTML implies user edited it before
        richInput.dataset._isPristine = "false";
        return;
      }

      // Otherwise insert the plaintext inside a wrapper that preserves whitespace exactly
      const plain = inputText.value || "";
      // Save original plain for exact restoration if user doesn't edit the rich contents
      richInput.dataset._plainOriginal = plain;
      richInput.dataset._isPristine = "true";
      // Use escaped content inside a pre-wrap container so it appears visually identical
      richInput.innerHTML = `<div class="plain-preserve" style="white-space: pre-wrap;">${escapeForHTML(plain)}</div>`;
    };

    // Helper to save rich HTML for later restoration
    const saveRichHtml = () => {
      try {
        richInput.dataset._lastHtml = richInput.innerHTML || "";
      } catch (e) {
        // ignore
      }
    };

    if (richToggle) {
      richToggle.addEventListener("change", (e) => {
        const checked = e.target.checked;
        if (checked) {
          // Enable toolbar and rich input
          richInput.style.display = "block";
          inputText.style.display = "none";
          toolbar && (toolbar.style.display = "flex");
          // Load content to rich editor
          loadPlainToRich();
          richInput.focus();
          // Preserve checkbox makes sense only when rich editor is active
          if (preserveCheck) preserveCheck.disabled = false;
        } else {
          // When turning off rich editor: save HTML if user wanted to preserve it
          if (preserveCheck && preserveCheck.checked) {
            saveRichHtml();
          } else {
            // clear stored html to avoid unexpected restores
            if (richInput.dataset._lastHtml) delete richInput.dataset._lastHtml;
          }

          richInput.style.display = "none";
          inputText.style.display = "block";
          toolbar && (toolbar.style.display = "none");
          // If the rich content is still pristine (user didn't edit it), restore original plaintext exactly
          if (
            richInput &&
            richInput.dataset &&
            richInput.dataset._isPristine === "true" &&
            richInput.dataset._plainOriginal !== undefined
          ) {
            inputText.value = richInput.dataset._plainOriginal;
          } else {
            // Otherwise convert edited HTML to plain text reliably
            inputText.value = richInput
              ? htmlToPlainText(richInput.innerHTML)
              : inputText.value;
          }
          // Disable preserve formatting when rich editor is off
          if (preserveCheck) {
            preserveCheck.checked = false;
            preserveCheck.disabled = true;
          }
        }
        updateCharCount();
      });

      // Initialize state: if preserve is checked, ensure rich editor is on
      if (preserveCheck && preserveCheck.checked && !richToggle.checked) {
        richToggle.checked = true;
        richToggle.dispatchEvent(new Event("change"));
      }
    }

    // If user checks 'preserve formatting' while rich is off, auto-enable rich editor
    if (preserveCheck) {
      preserveCheck.addEventListener("change", (e) => {
        if (e.target.checked && richToggle && !richToggle.checked) {
          richToggle.checked = true;
          richToggle.dispatchEvent(new Event("change"));
          UIManager.showNotification(
            "Bật Rich editor để giữ định dạng",
            "info",
          );
        }
        // if user unchecks preserve while rich on, clear stored html
        if (!e.target.checked && richInput && richInput.dataset._lastHtml) {
          delete richInput.dataset._lastHtml;
        }
      });
    }

    // Toolbar buttons
    document.querySelectorAll(".toolbar-btn").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        const cmd = btn.dataset.cmd;
        if (!cmd) return;
        if (cmd === "createLink") {
          const url = await showPrompt({
            title: "Thêm liên kết",
            message: "Nhập URL (ví dụ: https://example.com)",
            placeholder: "https://example.com",
          });
          if (url) document.execCommand(cmd, false, url);
        } else {
          document.execCommand(cmd, false, null);
        }
        richInput && richInput.focus();
      });
    });

    // Keyboard shortcuts for rich editor
    if (richInput) {
      richInput.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
          const key = e.key.toLowerCase();
          if (key === "b") {
            e.preventDefault();
            document.execCommand("bold");
          }
          if (key === "i") {
            e.preventDefault();
            document.execCommand("italic");
          }
          if (key === "u") {
            e.preventDefault();
            document.execCommand("underline");
          }
        }
      });
    }

    // hide toolbar initially if not active
    if (toolbar && (!richToggle || !richToggle.checked))
      toolbar.style.display = "none";
  }

  async translateText() {
    const richOn = document.getElementById("richToggle")?.checked;
    let text = "";
    const preserve = document.getElementById("preserveFormatting")?.checked;
    if (richOn) {
      const richEl = document.getElementById("richInput");
      if (preserve && richEl) {
        // Send raw HTML when user wants to preserve formatting
        text = richEl ? richEl.innerHTML || "" : "";
      } else {
        text = richEl ? richEl.innerText || "" : "";
      }
    } else {
      text = document.getElementById("inputText").value.trim();
    }
    const sourceLang =
      (document.getElementById("sourceLang") &&
        document.getElementById("sourceLang").value) ||
      "auto";
    const targetLang = document.getElementById("targetLang").value;
    const translationProvider = getSelectedTranslationProvider();

    // Ensure user is authenticated
    if (!this.auth.isAuthenticated()) {
      UIManager.showError(
        UIManager.uiT("msg.loginRequired", "Please sign in."),
      );
      // Optionally redirect to login after short delay
      setTimeout(() => this.auth.redirectToLogin(), 800);
      return;
    }

    if (!text) {
      UIManager.showError(UIManager.uiT("msg.enterText", "Please enter text."));
      return;
    }

    // Hide previous error
    UIManager.hideError();

    const translateBtn = document.getElementById("translateBtn");
    const translateBtnText = document.getElementById("translateBtnText");
    const translateLoading = document.getElementById("translateLoading");

    // Show loading state
    translateBtnText.textContent = UIManager.uiT(
      "msg.translating",
      "Translating...",
    );
    translateLoading.style.display = "inline-block";
    translateBtn.disabled = true;
    // Accessibility: set ARIA busy and live status
    try {
      translateBtn.setAttribute("aria-busy", "true");
      const translateStatusEl = document.getElementById("translateStatus");
      if (translateStatusEl)
        translateStatusEl.textContent = UIManager.uiT(
          "msg.translating",
          "Translating...",
        );
    } catch (e) {
      // ignore
    }

    // Show faux progress
    const textProgress = document.getElementById("textProgress");
    const textProgressFill = document.getElementById("textProgressFill");
    let progressInterval;
    if (textProgress) {
      textProgress.style.display = "block";
      textProgressFill.style.width = "0%";
      let p = 0;
      progressInterval = setInterval(() => {
        p = Math.min(95, p + Math.random() * 8);
        textProgressFill.style.width = `${p}%`;
      }, 250);
    }

    try {
      let response = await fetch("/api/translation/text", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...this.auth.getAuthHeaders(),
        },
        body: JSON.stringify({
          text: text,
          source_lang: sourceLang,
          target_lang: targetLang,
          translation_provider: translationProvider,
          is_html: richOn && preserve ? true : false,
        }),
      });

      // Token hết hạn / không hợp lệ — bắt đăng nhập lại (không dịch ẩn danh)
      if (response.status === 401 || response.status === 422) {
        UIManager.showError("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");
        setTimeout(() => this.auth.redirectToLogin(), 800);
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.error ||
            errorData.message ||
            errorData.msg ||
            "Dịch thất bại. Kiểm tra API key (OPENAI/OPENROUTER) trong .env.",
        );
      }

      const data = await response.json();
      this.showTranslationResult(data.translated_text, data.is_html);
      applyTokenBalanceFromResponse(data, this.auth);

      // Show a small success toast
      UIManager.showNotification("Dịch hoàn tất", "success");

      // Reload stats and history
      dashboard.auth.loadUserInfo();
      dashboard.stats.loadStats();
      dashboard.history.loadHistory();
    } catch (error) {
      console.error("Translation error:", error);
      UIManager.showError(
        error.message || "Có lỗi xảy ra khi dịch. Vui lòng thử lại.",
      );
      // Also show toast
      UIManager.showNotification(error.message || "Lỗi khi dịch.", "error");
    } finally {
      // Hide loading state & finish progress
      translateBtnText.textContent = UIManager.uiT(
        "msg.translate",
        "Translate",
      );
      translateLoading.style.display = "none";
      translateBtn.disabled = false;
      // Clear ARIA busy
      try {
        translateBtn.removeAttribute("aria-busy");
        const translateStatusEl = document.getElementById("translateStatus");
        if (translateStatusEl) translateStatusEl.textContent = "";
      } catch (e) {
        // ignore
      }

      if (progressInterval) clearInterval(progressInterval);
      if (textProgress) {
        const textProgressFill = document.getElementById("textProgressFill");
        textProgressFill.style.width = "100%";
        setTimeout(() => {
          textProgress.style.display = "none";
          textProgressFill.style.width = "0%";
        }, 600);
      }
    }
  }

  sanitizeHTML(s) {
    if (!s) return "";
    // Very small sanitizer: remove <script> blocks and on* attributes to avoid inline JS
    try {
      let out = String(s);
      // Remove script tags
      out = out.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "");
      // Remove on* attributes (onclick, onerror, etc.)
      out = out.replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, "");
      return out;
    } catch (e) {
      return String(s);
    }
  }

  // Decode HTML entities like &lt; &gt; &amp; into their character equivalents
  decodeHTMLEntities(s) {
    if (!s) return "";
    try {
      const txt = document.createElement("textarea");
      txt.innerHTML = s;
      return txt.value;
    } catch (e) {
      return String(s);
    }
  }

  showTranslationResult(translatedText, isHtml) {
    const resultDiv = document.getElementById("translationResult");
    const outputDiv = document.getElementById("outputText");
    const previewPane = document.getElementById("previewPane");
    const preserve = document.getElementById("preserveFormatting")?.checked;

    // If result is HTML or user requested preserve, render as HTML in preview (try decode entities then sanitize)
    if (isHtml || preserve) {
      let html = String(translatedText || "");
      // Only decode entities if the whole result looks like escaped HTML (e.g. &lt;p&gt;...)
      // Decoding unconditionally can break content like "5 &lt; 10" by turning it into a broken tag.
      const hasRealTags = /<\s*[a-zA-Z][^>]*>/.test(html);
      const looksLikeEscapedHtml =
        /&lt;\s*[a-zA-Z][^&]*&gt;/.test(html) && !hasRealTags;
      if (looksLikeEscapedHtml) {
        html = this.decodeHTMLEntities(html);
      }

      const sanitized = this.sanitizeHTML(html);
      if (previewPane)
        previewPane.innerHTML = sanitized || "<em>Không có kết quả</em>";

      // For plain text output area, derive text via DOM parsing (avoid regex stripping that can drop characters)
      if (outputDiv) {
        const tmp = document.createElement("div");
        tmp.innerHTML = sanitized;
        outputDiv.textContent = tmp.textContent || tmp.innerText || "";
      }
    } else {
      outputDiv.textContent = translatedText;
      if (previewPane) {
        // Convert plain text into paragraphs: split on double-newlines, collapse inner whitespace
        previewPane.innerHTML = this.plainTextToHTML(translatedText || "");
      }
    }

    resultDiv.style.display = "block";
  }

  // Utility: escape text for <pre>

  escapedForPre(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Convert plain text to HTML paragraphs, collapsing stray newlines inside paragraphs
  plainTextToHTML(s) {
    if (!s) return "<em>Không có kết quả</em>";
    // Normalize CRLF
    s = s.replace(/\r\n?/g, "\n");
    // Split into paragraphs on 2+ newlines
    const parts = s.split(/\n{2,}/g);
    const escaped = parts
      .map((p) => {
        const collapsed = p.replace(/\s+/g, " ").trim();
        return `<p>${this.escapedForPre(collapsed)}</p>`;
      })
      .join("");
    return escaped;
  }

  copyResult() {
    const outputText = document.getElementById("outputText").textContent;
    navigator.clipboard.writeText(outputText).then(() => {
      UIManager.showNotification("Đã sao chép vào clipboard!", "success");
    });
  }

  async saveTranslation() {
    const richOn = document.getElementById("richToggle")?.checked;
    const preserve = document.getElementById("preserveFormatting")?.checked;
    let originalText = document.getElementById("inputText").value;
    if (richOn && preserve) {
      const rich = document.getElementById("richInput");
      originalText = rich ? rich.innerHTML : originalText;
    } else if (richOn) {
      const rich = document.getElementById("richInput");
      originalText = rich ? rich.innerText : originalText;
    }

    const translatedText =
      document.getElementById("outputText").textContent ||
      document.getElementById("previewPane").innerHTML;

    try {
      const response = await fetch("/api/translation/save", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...this.auth.getAuthHeaders(),
        },
        body: JSON.stringify({
          original_text: originalText,
          translated_text: translatedText,
          source_lang: document.getElementById("sourceLang").value,
          target_lang: document.getElementById("targetLang").value,
        }),
      });

      if (response.ok) {
        UIManager.showNotification("Đã lưu bản dịch!", "success");
      } else {
        throw new Error("Save failed");
      }
    } catch (error) {
      console.error("Save error:", error);
      UIManager.showAlert("Có lỗi khi lưu bản dịch.");
    }
  }
}

// History Manager
class HistoryManager {
  constructor(authManager) {
    this.auth = authManager;
    this.currentPage = 1;
    this.currentFilter = "all";
    this.currentDate = "";
  }

  async loadHistory(page = 1, filter = "all", date = "") {
    // History tab might be removed from the UI; don't error if elements are missing.
    if (!document.getElementById("historyList")) return;
    this.currentPage = page;
    this.currentFilter = filter;
    this.currentDate = date || "";

    try {
      // Dev: if token is fake, use local mock history
      const token = localStorage.getItem("token");
      if (token && token.startsWith && token.startsWith("fake")) {
        const mock = [
          {
            id: 1,
            original_text: "Hello",
            translated_text: "[DEV] Xin chào",
            source_lang: "en",
            target_lang: "vi",
            created_at: new Date().toISOString(),
            has_file: false,
          },
        ];
        this.renderHistory(mock);
        this.updatePagination(1, 1);
        return;
      }

      const params = new URLSearchParams({
        page: page,
        per_page: 10,
        type: filter,
      });

      if (date) {
        params.set("date", date);
      }

      const response = await fetch(`/api/translation/history?${params}`, {
        headers: this.auth.getAuthHeaders(),
      });

      if (!response.ok) throw new Error("Failed to load history");

      const data = await response.json();
      this.renderHistory(data.translations);
      this.updatePagination(data.pages, page);
    } catch (error) {
      console.error("Error loading history:", error);
    }
  }

  renderHistory(translations) {
    const historyList = document.getElementById("historyList");
    if (!historyList) return;

    if (translations.length === 0) {
      historyList.innerHTML =
        '<p class="no-history">Chưa có lịch sử dịch thuật.</p>';
      return;
    }

    historyList.innerHTML = translations
      .map(
        (item) => `
            <div class="history-item glassmorphism">
                <div class="history-header">
                    <span class="history-date">${new Date(item.created_at).toLocaleString("vi-VN")}</span>
                    <span class="history-lang">${item.source_lang} → ${item.target_lang}</span>
                </div>
                <div class="history-content">
                    <div class="original-text">
                        <strong>Nguyên bản:</strong> ${item.original_text.length > 100 ? item.original_text.substring(0, 100) + "..." : item.original_text}
                    </div>
                    <div class="translated-text">
                        <strong>Dịch:</strong> ${item.translated_text.length > 100 ? item.translated_text.substring(0, 100) + "..." : item.translated_text}
                    </div>
                </div>
                <div class="history-actions">
                    <button onclick="copyHistoryItem('${item.translated_text.replace(/'/g, "\\'")}')" class="btn-small">
                        <i class="fas fa-copy"></i> Sao chép
                    </button>
                    <button onclick="deleteHistoryItem(${item.id})" class="btn-small delete">
                        <i class="fas fa-trash"></i> Xóa
                    </button>
                </div>
            </div>
        `,
      )
      .join("");
  }

  updatePagination(totalPages, currentPage) {
    const pageInfo = document.getElementById("pageInfo");
    const prevBtn = document.getElementById("prevPage");
    const nextBtn = document.getElementById("nextPage");

    if (!pageInfo || !prevBtn || !nextBtn) return;

    pageInfo.textContent = `Trang ${currentPage} / ${totalPages}`;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
  }

  changePage(direction) {
    const newPage = this.currentPage + direction;
    if (newPage > 0) {
      this.loadHistory(newPage, this.currentFilter, this.currentDate);
    }
  }

  filterHistory() {
    const historyFilter = document.getElementById("historyFilter");
    if (!historyFilter) return;
    const filter = historyFilter.value;
    const date = (document.getElementById("dateFilter") || {}).value || "";
    this.loadHistory(1, filter, date);
  }
}

// File Upload Manager
class FileUploadManager {
  constructor(authManager) {
    this.auth = authManager;
    this.selectedFile = null;
    this.pollInterval = null;
    this.setupFileUpload();
  }

  clearPollInterval() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  setupFileUpload() {
    const fileInput = document.getElementById("fileInput");
    // There are multiple ".upload-area" elements (OCR image + document upload).
    // Scope to the document upload tab to avoid binding handlers to the wrong area.
    const uploadArea = document.querySelector("#upload-tab .upload-area");

    if (!fileInput || !uploadArea) return;

    // Click to select file
    uploadArea.addEventListener("click", (e) => {
      // Open picker for most clicks inside upload area.
      // Reset input value first so selecting the same file still triggers change.
      const t = e.target;
      if (t && t.id === "fileInput") return;
      fileInput.value = "";
      fileInput.click();
    });

    // Drag and drop (optional enhancement)
    uploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadArea.classList.add("drag-over");
    });

    uploadArea.addEventListener("dragleave", () => {
      uploadArea.classList.remove("drag-over");
    });

    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.classList.remove("drag-over");
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        this.handleFileSelect(files[0]);
      }
    });

    // File input change
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        this.handleFileSelect(e.target.files[0]);
      }
    });
  }

  handleFileSelect(file) {
    const allowedTypes = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ];
    const allowedExts = [".pdf", ".docx"];
    const maxSize = 50 * 1024 * 1024; // 50MB

    const fileName = String((file && file.name) || "").toLowerCase();
    const extOk = allowedExts.some((ext) => fileName.endsWith(ext));
    const typeOk = allowedTypes.includes(String(file.type || "").toLowerCase());

    if (!typeOk && !extOk) {
      UIManager.showAlert(
        "Định dạng file không được hỗ trợ. Chỉ chấp nhận PDF và Word (.docx).",
      );
      return;
    }

    if (file.size > maxSize) {
      UIManager.showAlert(
        UIManager.uiT("msg.fileTooLarge", "File too large. Limit is 50MB."),
      );
      return;
    }

    this.showFileInfo(file);
  }

  showFileInfo(file) {
    const fileInfo = document.getElementById("fileInfo");
    const fileName = document.getElementById("fileName");
    const fileSize = document.getElementById("fileSize");

    fileName.textContent = file.name;
    fileSize.textContent = `(${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    fileInfo.style.display = "block";
    this.selectedFile = file;

    // Keep OCR toggle as user-selected; do not auto-toggle when selecting a file.
  }

  async uploadDocument() {
    if (!this.selectedFile) {
      UIManager.showError(
        UIManager.uiT("msg.selectFile", "Please select a file first."),
      );
      return;
    }

    this.clearPollInterval();
    UIManager.hideSuccess();

    const targetLang = document.getElementById("uploadTargetLang").value;
    const uploadBtn = document.getElementById("uploadBtn");
    const uploadBtnText = document.getElementById("uploadBtnText");
    const uploadBtnLoading = document.getElementById("uploadBtnLoading");

    // Hide previous messages
    UIManager.hideError();

    // Show loading state
    uploadBtnText.textContent = "Đang upload...";
    uploadBtnLoading.style.display = "inline-block";
    uploadBtn.disabled = true;

    const formData = new FormData();
    formData.append("file", this.selectedFile);
    formData.append("target_lang", targetLang);
    const translationProvider = getSelectedTranslationProvider();
    if (translationProvider) {
      formData.append("translation_provider", translationProvider);
    }

    // Optional: OCR images embedded in Word (.docx) or PDF
    try {
      const ocrToggle = document.getElementById("uploadDocxOcrImages");
      const isDocx =
        (this.selectedFile &&
          (this.selectedFile.type ===
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
            String(this.selectedFile.name || "")
              .toLowerCase()
              .endsWith(".docx"))) ||
        false;
      const isPdf =
        (this.selectedFile &&
          (this.selectedFile.type === "application/pdf" ||
            String(this.selectedFile.name || "")
              .toLowerCase()
              .endsWith(".pdf"))) ||
        false;
      if (ocrToggle && ocrToggle.checked && (isDocx || isPdf)) {
        formData.append("ocr_images", "1");
        formData.append("ocr_mode", "image");
      }
    } catch (e) {
      // ignore
    }

    // Bilingual mode
    try {
      const bilingualSel = document.getElementById("uploadBilingualMode");
      if (bilingualSel && bilingualSel.value && bilingualSel.value !== "none") {
        formData.append("bilingual_mode", bilingualSel.value);

        // Inline bilingual: Original <delimiter> Translated (delimiter from uploadBilingualDelimiter)
        if (bilingualSel.value === "preserve_layout") {
          const delimSel = document.getElementById("uploadBilingualDelimiter");
          let delimiter = (delimSel && delimSel.value) || "|";
          delimiter = String(delimiter).trim();
          if (!delimiter) delimiter = "|";
          if (delimiter.length > 10) delimiter = delimiter.slice(0, 10);
          formData.append("bilingual_delimiter", delimiter);
        }
      }
    } catch (e) {
      // ignore
    }

    try {
      let response = await fetch("/api/translation/document", {
        method: "POST",
        headers: this.auth.getAuthHeaders(),
        body: formData,
      });

      if (response.status === 401 || response.status === 422) {
        UIManager.showError("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");
        setTimeout(() => this.auth.redirectToLogin(), 800);
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.error ||
            errorData.message ||
            errorData.msg ||
            "Upload thất bại. Kiểm tra API key (OPENAI/OPENROUTER) trong .env.",
        );
      }

      const data = await response.json();
      applyTokenBalanceFromResponse(data, this.auth);

      // If job-based, start polling status
      if (data.job_id) {
        UIManager.showNotification(
          "Tệp đã được chấp nhận, bắt đầu xử lý. Bắt đầu theo dõi tiến trình...",
          "info",
        );
        document.getElementById("uploadProgress").style.display = "block";
        const progressFill = document.getElementById("progressFill");
        const progressText = document.getElementById("progressText");
        const progressPercent = document.getElementById("progressPercent");

        // Reset from previous run so progress does not appear stuck at 100%.
        progressFill.style.width = "0%";
        progressPercent.textContent = "0%";
        progressText.textContent = "Đang bắt đầu xử lý...";

        const pollUrl = data.status_url;
        let notFoundCount = 0;
        let fetchErrorCount = 0;
        const MAX_FETCH_ERRORS = 15;
        this.pollInterval = setInterval(async () => {
          try {
            let activePollUrl = pollUrl;
            let statusResp = await fetch(activePollUrl, {
              headers: this.auth.getAuthHeaders(),
            });

            // If JWT is stale/invalid, retry without auth because status endpoint is optional-auth.
            if (statusResp.status === 401 || statusResp.status === 422) {
              statusResp = await fetch(activePollUrl);
            }

            // Some deployments may expose an older status route.
            if (
              statusResp.status === 404 &&
              typeof activePollUrl === "string" &&
              activePollUrl.includes("/api/translation/document/status/")
            ) {
              const legacyPollUrl = activePollUrl.replace(
                "/api/translation/document/status/",
                "/api/translation/status/",
              );
              let legacyResp = await fetch(legacyPollUrl, {
                headers: this.auth.getAuthHeaders(),
              });
              if (legacyResp.status === 401 || legacyResp.status === 422) {
                legacyResp = await fetch(legacyPollUrl);
              }
              if (legacyResp.ok) {
                statusResp = legacyResp;
                activePollUrl = legacyPollUrl;
              }
            }

            if (!statusResp.ok) {
              if (statusResp.status === 404) {
                notFoundCount += 1;
                if (notFoundCount >= 3) {
                  this.clearPollInterval();
                  UIManager.showError(
                    "Không tìm thấy tiến trình xử lý (404). Server có thể đã khởi động lại, vui lòng upload lại file.",
                  );
                  document.getElementById("uploadProgress").style.display =
                    "none";
                  return;
                }
              }
              throw new Error(`Failed to get status (${statusResp.status})`);
            }
            notFoundCount = 0;
            fetchErrorCount = 0;
            const statusData = await statusResp.json();
            const rawP = Number(statusData.progress);
            let p = Number.isFinite(rawP)
              ? Math.max(0, Math.min(100, Math.round(rawP)))
              : 0;

            const msg = String(statusData.message || "");
            const pageMatch = msg.match(/PDF:\s*page\s*(\d+)\s*\/\s*(\d+)/i);
            if (pageMatch) {
              const cur = Math.max(1, Number(pageMatch[1]) || 1);
              const total = Math.max(1, Number(pageMatch[2]) || 1);
              if (cur < total && p >= 100) {
                p = Math.min(99, 5 + Math.round(((cur - 1) / total) * 85));
              }
            }

            progressFill.style.width = `${p}%`;
            progressPercent.textContent = `${p}%`;
            progressText.textContent = statusData.message || "Đang xử lý...";

            if (statusData.status === "completed") {
              this.clearPollInterval();

              // If fallback occurred, inform user
              if (statusData.fallback) {
                UIManager.showError(
                  `File was returned as a fallback (${statusData.fallback_reason}). The file may be plain text.`,
                );
              }

              // Auto download
              if (statusData.download_url) {
                setTimeout(() => {
                  triggerDownload(
                    statusData.download_url,
                    `translated_${this.selectedFile.name}`,
                  );
                }, 500);
              }

              // OCR text is now inserted directly into the DOCX — no separate sidecar file.

              // Surface DOCX OCR image processing summary (if enabled on backend)
              try {
                if (statusData.ocr_summary) {
                  UIManager.showNotification(
                    String(statusData.ocr_summary),
                    "info",
                  );
                }
                if (statusData.ocr_skipped) {
                  // Example: missing Tesseract; show as error-style notification
                  UIManager.showNotification(
                    String(statusData.ocr_skipped),
                    "error",
                  );
                }
              } catch (e) {
                // ignore
              }

              // Success message (include OCR summary if present so it's visible even if notification hides)
              const suffix = statusData.ocr_summary
                ? ` (${String(statusData.ocr_summary)})`
                : statusData.ocr_skipped
                  ? ` (${String(statusData.ocr_skipped)})`
                  : "";
              UIManager.showSuccess(`Tệp đã được dịch xong!${suffix}`);
              document.getElementById("uploadProgress").style.display = "none";

              // Reload stats and history
              dashboard.auth.loadUserInfo();
              dashboard.stats.loadStats();
              dashboard.history.loadHistory();
            }

            if (statusData.status === "failed") {
              this.clearPollInterval();
              const errMsg = statusData.error || "Đã có lỗi khi xử lý file";
              UIManager.showError(errMsg);
              // Show error in progress bar area instead of hiding it
              progressFill.style.width = "100%";
              progressFill.style.backgroundColor = "#e74c3c";
              progressText.textContent = `Lỗi: ${errMsg}`;
              progressPercent.textContent = "❌";
              // Auto-hide after 8 seconds
              setTimeout(() => {
                document.getElementById("uploadProgress").style.display =
                  "none";
                progressFill.style.backgroundColor = "";
              }, 8000);
            }
          } catch (err) {
            fetchErrorCount++;
            console.error(
              `Status polling error (${fetchErrorCount}/${MAX_FETCH_ERRORS})`,
              err,
            );
            if (fetchErrorCount >= MAX_FETCH_ERRORS) {
              this.clearPollInterval();
              UIManager.showError(
                "Mất kết nối đến server. Vui lòng kiểm tra server và thử lại.",
              );
              document.getElementById("uploadProgress").style.display = "none";
            }
          }
        }, 1000);
      } else if (data.download_url) {
        // Fallback for immediate synchronous response
        if (data.fallback) {
          UIManager.showError(
            `File was returned as a fallback (${data.fallback_reason}). The file may be plain text.`,
          );
        }
        UIManager.showSuccess("File đã được dịch thành công!");

        // Auto download after a short delay
        setTimeout(() => {
          triggerDownload(
            data.download_url,
            `translated_${this.selectedFile.name}`,
          );
        }, 1000);

        // Reload stats and history
        dashboard.auth.loadUserInfo();
        dashboard.stats.loadStats();
        dashboard.history.loadHistory();
      }
    } catch (error) {
      console.error("Upload error:", error);
      const rawMessage = String(error?.message || "");
      if (
        /failed to fetch|networkerror|err_connection_refused/i.test(
          rawMessage.toLowerCase(),
        )
      ) {
        UIManager.showError(
          "Không kết nối được backend API. Hãy chạy backend tại http://127.0.0.1:5055 (python api_base/run_api.py) và đảm bảo không trùng cổng.",
        );
      } else {
        UIManager.showError(error.message || "Có lỗi khi upload file.");
      }
    } finally {
      // Hide loading state
      uploadBtnText.textContent = "Upload & Dịch";
      uploadBtnLoading.style.display = "none";
      uploadBtn.disabled = false;
    }
  }

  resetUpload() {
    this.clearPollInterval();
    document.getElementById("uploadProgress").style.display = "none";
    document.getElementById("fileInput").value = "";
    document.getElementById("fileInfo").style.display = "none";
    this.selectedFile = null;
  }
}

// Image OCR Upload Manager
class ImageOcrManager {
  constructor(authManager) {
    this.auth = authManager;
    this.selectedImage = null;
    this.objectUrl = null;
    this.setupImageUpload();
  }

  setupImageUpload() {
    const imageInput = document.getElementById("imageInput");
    const imageArea = document.getElementById("imageUploadArea");
    if (!imageInput || !imageArea) return;

    const modeSel = document.getElementById("imageOutputMode");
    const modeLabel = document.getElementById("imageModeLabel");
    const updateModeLabel = () => {
      if (!modeSel || !modeLabel) return;
      const v = String(modeSel.value || "auto").toLowerCase();
      if (v === "text") modeLabel.textContent = "Chế độ: Văn bản";
      else if (v === "image") modeLabel.textContent = "Chế độ: Ảnh";
      else if (v === "both") modeLabel.textContent = "Chế độ: Ảnh + Văn bản";
      else modeLabel.textContent = "Chế độ: Tự động";
    };
    updateModeLabel();
    if (modeSel) modeSel.addEventListener("change", updateModeLabel);

    const isOcrTabActive = () => {
      const imageTab = document.getElementById("image-tab");
      return !!(imageTab && imageTab.classList.contains("active"));
    };

    const tryGetImageFileFromClipboard = (clipboardData) => {
      const items = clipboardData && clipboardData.items;
      if (!items) return null;
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (!it) continue;

        // Typical case: clipboard exposes the pasted bitmap as image/*
        if (it.type && it.type.startsWith("image/")) {
          const f = it.getAsFile && it.getAsFile();
          if (f) return f;
        }

        // Some environments expose a file-kind item with missing/empty type
        if (it.kind === "file") {
          const f = it.getAsFile && it.getAsFile();
          if (f && f.type && f.type.startsWith("image/")) return f;
        }
      }
      return null;
    };

    // Paste image from clipboard (Ctrl+V) when OCR tab is active
    const onPaste = async (e) => {
      try {
        // Only handle image paste when the OCR tab is active.
        // This avoids breaking normal paste behavior in text inputs on other tabs.
        if (!isOcrTabActive()) return;

        let file = tryGetImageFileFromClipboard(e.clipboardData);

        // Fallback: some environments don't populate clipboardData.items for images.
        // Try the async Clipboard API if available.
        if (!file && navigator.clipboard && navigator.clipboard.read) {
          try {
            const items = await navigator.clipboard.read();
            for (const item of items) {
              for (const type of item.types || []) {
                if (type && type.startsWith("image/")) {
                  const blob = await item.getType(type);
                  file = new File(
                    [blob],
                    `pasted-image.${type.split("/")[1] || "png"}`,
                    { type },
                  );
                  break;
                }
              }
              if (file) break;
            }
          } catch (clipErr) {
            // Ignore permission errors and fall back to default paste
          }
        }

        if (!file) return;
        e.preventDefault();
        this.handleImageSelect(file);
        UIManager.showNotification("Đã dán ảnh từ clipboard", "success");
      } catch (err) {
        // ignore
      }
    };

    // Listen globally so paste works even if the area isn't focused
    document.addEventListener("paste", onPaste);

    // Click to select
    imageArea.addEventListener("click", (e) => {
      if (
        e.target === imageArea ||
        e.target.closest(".upload-icon") ||
        e.target.tagName === "H3" ||
        e.target.tagName === "P"
      ) {
        imageInput.click();
      }
    });

    // Also allow pasting while the OCR area is focused
    imageArea.addEventListener("paste", onPaste);

    // Drag & drop
    imageArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      imageArea.classList.add("drag-over");
    });
    imageArea.addEventListener("dragleave", () => {
      imageArea.classList.remove("drag-over");
    });
    imageArea.addEventListener("drop", (e) => {
      e.preventDefault();
      imageArea.classList.remove("drag-over");
      const files = e.dataTransfer.files;
      if (files && files.length > 0) this.handleImageSelect(files[0]);
    });

    imageInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.handleImageSelect(e.target.files[0]);
      }
    });
  }

  handleImageSelect(file) {
    const maxSize = 15 * 1024 * 1024; // 15MB
    if (!file || !file.type || !file.type.startsWith("image/")) {
      UIManager.showNotification("File không phải hình ảnh.", "error");
      return;
    }
    if (file.size > maxSize) {
      UIManager.showNotification("Ảnh quá lớn. Giới hạn 15MB.", "error");
      return;
    }

    this.selectedImage = file;
    this.showImageInfo(file);
  }

  showImageInfo(file) {
    const info = document.getElementById("imageInfo");
    const nameEl = document.getElementById("imageName");
    const sizeEl = document.getElementById("imageSize");
    const preview = document.getElementById("imagePreview");
    const err = document.getElementById("imageError");
    if (err) err.style.display = "none";

    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl)
      sizeEl.textContent = `(${(file.size / 1024 / 1024).toFixed(2)} MB)`;
    if (info) info.style.display = "block";

    try {
      if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = URL.createObjectURL(file);
      if (preview) {
        preview.src = this.objectUrl;
        preview.style.display = "block";
      }
    } catch (e) {
      // ignore preview errors
    }
  }

  showImageError(message) {
    const err = document.getElementById("imageError");
    const txt = document.getElementById("imageErrorText");
    if (txt) txt.textContent = message;
    if (err) err.style.display = "block";
  }

  clearImage() {
    const imageInput = document.getElementById("imageInput");
    const info = document.getElementById("imageInfo");
    const preview = document.getElementById("imagePreview");
    const result = document.getElementById("imageResult");
    const ocrText = document.getElementById("imageOcrText");
    const translatedText = document.getElementById("imageTranslatedText");
    const translatedPreview = document.getElementById("imageTranslatedPreview");
    const textResultWrap = document.getElementById("imageTextResult");
    const modeSel = document.getElementById("imageOutputMode");
    const downloadBtn = document.getElementById("imageDownloadBtn");
    const err = document.getElementById("imageError");
    if (err) err.style.display = "none";
    if (info) info.style.display = "none";
    if (imageInput) imageInput.value = "";
    if (preview) {
      preview.src = "";
      preview.style.display = "none";
    }
    if (translatedPreview) {
      translatedPreview.src = "";
      translatedPreview.style.display = "none";
    }
    if (ocrText) ocrText.value = "";
    if (translatedText) translatedText.value = "";
    if (textResultWrap) textResultWrap.style.display = "grid";
    if (modeSel) {
      modeSel.value = "auto";
      modeSel.dispatchEvent(new Event("change"));
    }
    if (downloadBtn) downloadBtn.style.display = "none";
    if (result) result.style.display = "none";
    if (this.objectUrl) {
      try {
        URL.revokeObjectURL(this.objectUrl);
      } catch (e) {}
      this.objectUrl = null;
    }
    this.renderedImageDataUrl = null;
    this.selectedImage = null;
  }

  async uploadImageForTranslation() {
    if (!this.selectedImage) {
      this.showImageError("Vui lòng chọn ảnh trước!");
      return;
    }

    // Ensure user is authenticated
    if (!this.auth.isAuthenticated()) {
      this.showImageError("Vui lòng đăng nhập để sử dụng OCR & dịch!");
      setTimeout(() => this.auth.redirectToLogin(), 800);
      return;
    }

    const sourceLang =
      (document.getElementById("imageSourceLang") || {}).value || "auto";
    const targetLang =
      (document.getElementById("imageTargetLang") || {}).value || "";
    if (!targetLang) {
      this.showImageError(
        UIManager.uiT(
          "msg.selectTargetLang",
          "Please select a target language.",
        ),
      );
      return;
    }

    const btn = document.getElementById("imageTranslateBtn");
    const btnText = document.getElementById("imageTranslateBtnText");
    const btnLoading = document.getElementById("imageTranslateBtnLoading");

    if (btnText) btnText.textContent = "Đang OCR...";
    if (btnLoading) btnLoading.style.display = "inline-block";
    if (btn) btn.disabled = true;

    const formData = new FormData();
    formData.append("file", this.selectedImage);
    formData.append("source_lang", sourceLang);
    formData.append("target_lang", targetLang);
    const translationProvider = getSelectedTranslationProvider();
    if (translationProvider) {
      formData.append("translation_provider", translationProvider);
    }
    const modeSel = document.getElementById("imageOutputMode");
    const mode = String((modeSel && modeSel.value) || "auto").toLowerCase();
    formData.append("mode", mode);

    try {
      let resp = await fetch("/api/translation/image", {
        method: "POST",
        headers: this.auth.getAuthHeaders(),
        body: formData,
      });

      if (resp.status === 401 || resp.status === 422) {
        UIManager.showError("Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.");
        setTimeout(() => this.auth.redirectToLogin(), 800);
        return;
      }

      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(
          data.error || data.message || data.msg || "OCR & dịch thất bại.",
        );
      }

      // Show results inside the OCR tab (do NOT switch tabs and do NOT overwrite text-translation input)
      const result = document.getElementById("imageResult");
      const ocrText = document.getElementById("imageOcrText");
      const translatedText = document.getElementById("imageTranslatedText");
      const translatedPreview = document.getElementById(
        "imageTranslatedPreview",
      );
      const downloadBtn = document.getElementById("imageDownloadBtn");

      if (ocrText) ocrText.value = data.ocr_text || "";
      if (translatedText) translatedText.value = data.translated_text || "";

      const textResultWrap = document.getElementById("imageTextResult");
      const selectedMode = String(data.mode || mode || "auto").toLowerCase();
      const showText = selectedMode !== "image";
      if (textResultWrap)
        textResultWrap.style.display = showText ? "grid" : "none";

      this.renderedImageDataUrl = data.rendered_image || null;
      if (translatedPreview) {
        if (this.renderedImageDataUrl) {
          translatedPreview.src = this.renderedImageDataUrl;
          translatedPreview.style.display = "block";
        } else {
          translatedPreview.src = "";
          translatedPreview.style.display = "none";
        }
      }
      if (downloadBtn) {
        downloadBtn.style.display = this.renderedImageDataUrl
          ? "inline-block"
          : "none";
      }
      if (result) result.style.display = "block";

      UIManager.showNotification(
        this.renderedImageDataUrl
          ? "Đã dịch ảnh (đã thay chữ)"
          : "OCR & dịch hoàn tất",
        "success",
      );
      applyTokenBalanceFromResponse(data, this.auth);

      // Reload stats and history
      dashboard.auth.loadUserInfo();
      dashboard.stats.loadStats();
      dashboard.history.loadHistory();
    } catch (e) {
      console.error("Image OCR error", e);
      this.showImageError(e.message || "Có lỗi khi OCR ảnh.");
    } finally {
      if (btnText) btnText.textContent = "OCR & Dịch";
      if (btnLoading) btnLoading.style.display = "none";
      if (btn) btn.disabled = false;
    }
  }
}

function downloadTranslatedImage() {
  try {
    if (!dashboard || !dashboard.ocr || !dashboard.ocr.renderedImageDataUrl) {
      UIManager.showNotification("Chưa có ảnh đã dịch để tải.", "error");
      return;
    }
    const a = document.createElement("a");
    a.href = dashboard.ocr.renderedImageDataUrl;
    a.download = "translated_image.png";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (e) {
    UIManager.showNotification("Không tải được ảnh.", "error");
  }
}

// Dashboard Stats Manager
class DashboardStatsManager {
  constructor(authManager) {
    this.auth = authManager;
  }

  async loadStats() {
    try {
      // Dev: if token is fake, create mock stats
      const token = localStorage.getItem("token");
      if (token && token.startsWith && token.startsWith("fake")) {
        this.updateStats([
          { created_at: new Date().toISOString(), has_file: false },
        ]);
        return;
      }

      const response = await fetch(
        "/api/translation/history?page=1&per_page=100",
        {
          headers: this.auth.getAuthHeaders(),
        },
      );

      if (!response.ok) throw new Error("Failed to load stats");

      const data = await response.json();
      this.updateStats(data.translations);
    } catch (error) {
      console.error("Error loading stats:", error);
    }
  }

  updateStats(translations) {
    const today = new Date().toDateString();

    let todayCount = 0;
    let documentCount = 0;

    translations.forEach((item) => {
      const itemDate = new Date(item.created_at).toDateString();
      if (itemDate === today) {
        todayCount++;
      }
      if (item.has_file) {
        documentCount++;
      }
    });

    document.getElementById("translationCount").textContent = todayCount;
    document.getElementById("documentCount").textContent = documentCount;
  }
}

// Main Dashboard Controller
class DashboardController {
  constructor() {
    this.auth = new AuthManager();
    this.ui = UIManager;
    this.translation = new TranslationManager(this.auth);
    this.history = new HistoryManager(this.auth);
    this.upload = new FileUploadManager(this.auth);
    this.ocr = new ImageOcrManager(this.auth);
    this.stats = new DashboardStatsManager(this.auth);
    this.paymentPollTimer = null;
    this.paymentCountdownTimer = null;
    this.activePaymentHexId = null;
    this.activePaymentPackageId = null;
    this.paymentExpireAtMs = null;

    this.init();
  }

  init() {
    // Extract token from URL query parameter (from OAuth callback)
    const params = new URLSearchParams(window.location.search);
    const tokenFromUrl = params.get("token");
    if (tokenFromUrl) {
      localStorage.setItem("token", tokenFromUrl);
      // Remove token from URL to clean it up
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Check authentication first
    if (!this.auth.isAuthenticated()) {
      // Hide the entire dashboard and show login prompt
      this.showLoginRequired();
      return;
    }

    this.setupEventListeners();
    this.loadInitialData();
  }

  showLoginRequired() {
    // Redirect thẳng sang trang đăng nhập, giữ returnUrl để quay lại sau khi login
    window.location.replace(
      "/auth?returnUrl=" +
        encodeURIComponent(window.location.pathname + window.location.search),
    );
  }

  setupEventListeners() {
    try {
      // Logout
      const logoutBtn = document.getElementById("logoutBtn");
      if (logoutBtn) {
        logoutBtn.addEventListener("click", () => this.auth.logout());
      }

      // Login button (in case user gets logged out)
      const loginBtn = document.getElementById("loginBtn");
      if (loginBtn) {
        loginBtn.addEventListener("click", () => {
          window.location.href = "/auth";
        });
      }

      // User menu
      const userMenuBtn = document.querySelector(".user-menu-btn");
      if (userMenuBtn) {
        userMenuBtn.addEventListener("click", () => this.toggleUserMenu());
      }

      // Close user menu when clicking outside
      document.addEventListener("click", (e) => {
        const userMenu = document.getElementById("userMenu");
        const userMenuBtn = document.querySelector(".user-menu-btn");
        if (
          userMenu &&
          userMenuBtn &&
          !userMenuBtn.contains(e.target) &&
          !userMenu.contains(e.target)
        ) {
          userMenu.classList.remove("show");
        }
      });

      // Tab switching
      const tabButtons = document.querySelectorAll(".tab-btn");
      if (tabButtons && tabButtons.length) {
        tabButtons.forEach((btn) => {
          btn.addEventListener("click", (e) => {
            e.preventDefault();
            // Try to read an explicit target from onclick attribute or data-target
            let onclickAttr = btn.getAttribute("onclick");
            let match =
              onclickAttr && onclickAttr.match(/showTab\(['"]([^'"\)]+)['"]\)/);
            let tabName = match
              ? match[1]
              : btn.dataset.target || btn.getAttribute("data-target");
            if (!tabName && btn.textContent)
              tabName = btn.textContent.toLowerCase().replace(/\s+/g, "");
            this.ui.showTab(tabName);
          });
        });
      }

      // History filter
      const historyFilter = document.getElementById("historyFilter");
      if (historyFilter) {
        historyFilter.addEventListener("change", () =>
          this.history.filterHistory(),
        );
      }

      const dateFilter = document.getElementById("dateFilter");
      if (dateFilter) {
        dateFilter.addEventListener("change", () =>
          this.history.filterHistory(),
        );
      }

      // Settings link navigates to /profile page

      // Close notification
      const notificationClose = document.querySelector(".notification-close");
      if (notificationClose) {
        notificationClose.addEventListener("click", () =>
          UIManager.hideNotification(),
        );
      }

      // Clear file button
      const clearFileBtn = document.querySelector(
        ".upload-controls .btn-secondary",
      );
      if (clearFileBtn) {
        clearFileBtn.addEventListener("click", () => this.upload.resetUpload());
      }

      // Delimiter only for adjacent bilingual (preserve_layout → backend inline)
      const uploadBilingualModeSel = document.getElementById(
        "uploadBilingualMode",
      );
      const uploadDelimiterWrap = document.querySelector(
        ".upload-controls--document .upload-bilingual-delimiter",
      );
      const syncUploadDelimiter = () => {
        if (!uploadDelimiterWrap) return;
        const showDelim =
          uploadBilingualModeSel &&
          uploadBilingualModeSel.value === "preserve_layout";
        uploadDelimiterWrap.classList.toggle("is-visible", Boolean(showDelim));
        uploadDelimiterWrap.setAttribute(
          "aria-hidden",
          showDelim ? "false" : "true",
        );
      };
      if (uploadBilingualModeSel) {
        uploadBilingualModeSel.addEventListener("change", syncUploadDelimiter);
      }
      syncUploadDelimiter();

      const copyTransferBtn = document.getElementById("copyTransferBtn");
      if (copyTransferBtn) {
        copyTransferBtn.addEventListener("click", () =>
          this.copyTransferContent(),
        );
      }

      const checkPaymentNowBtn = document.getElementById("checkPaymentNowBtn");
      if (checkPaymentNowBtn) {
        checkPaymentNowBtn.addEventListener("click", () =>
          this.checkPaymentNow(),
        );
      }

      const recreateInvoiceBtn = document.getElementById("recreateInvoiceBtn");
      if (recreateInvoiceBtn) {
        recreateInvoiceBtn.addEventListener("click", () =>
          this.recreateInvoice(),
        );
      }
    } catch (err) {
      console.error("setupEventListeners error:", err);
    }
  }

  toggleUserMenu() {
    const userMenu = document.getElementById("userMenu");
    if (userMenu) {
      userMenu.classList.toggle("show");
    }
  }

  // Upgrade modal handlers
  async openUpgradeModal() {
    const m = document.getElementById("upgradeModal");
    if (m) m.style.display = "block";
    const planView = document.getElementById("planSelectionView");
    const paymentBox = document.getElementById("paymentBox");
    const successBox = document.getElementById("paymentSuccessBox");
    const statusEl = document.getElementById("paymentStatusText");
    const countdownEl = document.getElementById("paymentCountdown");
    if (planView) planView.style.display = "block";
    if (paymentBox) paymentBox.style.display = "none";
    if (successBox) successBox.style.display = "none";
    if (statusEl) statusEl.textContent = "";
    if (countdownEl) countdownEl.textContent = "--:--";
    // Show with current cached state first, then refresh
    this._updatePlanCardStates();
    await this.auth.loadUserInfo();
    this._updatePlanCardStates();
  }

  _canRepurchasePlan(plan) {
    const currentPlan = String(this.auth.profile?.plan || "free").toLowerCase();
    if (plan !== currentPlan || plan === "free") return false;
    const balance = parseInt(this.auth.profile?.token_balance, 10) || 0;
    const cap = getPlanTokenCap(plan);
    const threshold = Math.max(1, Math.floor(cap * 0.1));
    return balance <= threshold;
  }

  _updatePlanCardStates() {
    const currentPlan = String(this.auth.profile?.plan || "free").toLowerCase();
    const plans = ["free", "pro", "promax"];
    const labels = { free: "Free", pro: "Pro", promax: "ProMax" };
    const btnClasses = {
      free: "plan-btn-current",
      pro: "plan-btn-pro",
      promax: "plan-btn-promax",
    };
    const btnIcons = {
      free: "fa-check-circle",
      pro: "fa-bolt",
      promax: "fa-crown",
    };
    const btnTexts = {
      free: "Đang sử dụng",
      pro: "Nâng cấp Pro",
      promax: "Nâng cấp ProMax",
    };
    const repurchaseTexts = {
      pro: "Mua thêm Pro",
      promax: "Mua thêm ProMax",
    };
    const onclicks = {
      free: "closeUpgradeModal()",
      pro: "startUpgrade('pro')",
      promax: "startUpgrade('promax')",
    };

    plans.forEach((plan) => {
      const card = document.querySelector(`.upgrade-plan-card.${plan}-card`);
      if (!card) return;
      const btn = card.querySelector(".plan-btn");
      const badge = card.querySelector(".plan-badge");
      const isCurrent = plan === currentPlan;
      const canRepurchase = isCurrent && this._canRepurchasePlan(plan);

      // Update button
      if (btn) {
        if (canRepurchase) {
          btn.className = `plan-btn ${btnClasses[plan]}`;
          btn.setAttribute("onclick", onclicks[plan]);
          btn.disabled = false;
          btn.innerHTML = `<i class="fas fa-redo"></i> ${repurchaseTexts[plan] || `Mua thêm ${labels[plan]}`}`;
        } else {
          btn.className = `plan-btn ${isCurrent ? "plan-btn-current" : btnClasses[plan]}`;
          btn.setAttribute(
            "onclick",
            isCurrent ? "closeUpgradeModal()" : onclicks[plan],
          );
          btn.disabled = isCurrent;
          btn.innerHTML = isCurrent
            ? `<i class="fas fa-check-circle"></i> Đang sử dụng`
            : `<i class="fas ${btnIcons[plan]}"></i> ${btnTexts[plan]}`;
        }
      }

      // Update badge
      if (badge) {
        if (canRepurchase) {
          badge.className = "plan-badge popular-badge";
          badge.innerHTML = '<i class="fas fa-redo"></i> Mua thêm';
        } else if (isCurrent) {
          badge.className = "plan-badge";
          badge.textContent = "Hiện tại";
        } else if (plan === "pro") {
          badge.className = "plan-badge popular-badge";
          badge.innerHTML = '<i class="fas fa-star"></i> Phổ biến';
        } else if (plan === "promax") {
          badge.className = "plan-badge promax-badge";
          badge.innerHTML = '<i class="fas fa-crown"></i> Tốt nhất';
        } else {
          badge.className = "plan-badge";
          badge.textContent = "";
        }
      }
    });
  }

  closeUpgradeModal() {
    const m = document.getElementById("upgradeModal");
    if (m) m.style.display = "none";
    const successBox = document.getElementById("paymentSuccessBox");
    if (successBox) successBox.style.display = "none";
    this.stopPaymentPolling();
  }

  formatSeconds(totalSeconds) {
    const sec = Math.max(0, Number(totalSeconds || 0));
    const mm = Math.floor(sec / 60)
      .toString()
      .padStart(2, "0");
    const ss = Math.floor(sec % 60)
      .toString()
      .padStart(2, "0");
    return `${mm}:${ss}`;
  }

  formatVnd(value) {
    const amount = Number(value || 0);
    return `${amount.toLocaleString("vi-VN")} VNĐ`;
  }

  setPaymentStatusText(message, kind = "info") {
    const el = document.getElementById("paymentStatusText");
    if (!el) return;
    el.textContent = message;
    if (kind === "success") {
      el.style.color = "#22c55e";
      return;
    }
    if (kind === "error") {
      el.style.color = "#ef4444";
      return;
    }
    el.style.color = "#d1d5db";
  }

  renderPaymentInstructions(payload) {
    const planView = document.getElementById("planSelectionView");
    const paymentBox = document.getElementById("paymentBox");
    const packageText = document.getElementById("paymentPackageText");
    const amountText = document.getElementById("paymentAmountText");
    const transferText = document.getElementById("paymentTransferContent");
    const expireText = document.getElementById("paymentExpireText");
    const qrImage = document.getElementById("paymentQrImage");
    const bankCodeText = document.getElementById("paymentBankCode");
    const bankAccText = document.getElementById("paymentBankAccount");
    const bankNameText = document.getElementById("paymentBankAccountName");

    // Hide plan selection, show payment layout
    if (planView) planView.style.display = "none";
    if (paymentBox) paymentBox.style.display = "block";
    this.activePaymentHexId = payload.hex_id || null;
    this.activePaymentPackageId = payload.package_id || null;
    this.paymentExpireAtMs = payload.expires_at
      ? new Date(payload.expires_at).getTime()
      : null;

    if (packageText) {
      const tokenText = payload.token_amount
        ? ` · ${Number(payload.token_amount).toLocaleString("vi-VN")} token`
        : "";
      packageText.textContent = `Gói ${payload.package_name}${tokenText}`;
    }
    if (amountText) amountText.textContent = this.formatVnd(payload.amount_vnd);
    if (transferText) transferText.textContent = payload.transfer_content || "";
    if (expireText) {
      const expireAt = payload.expires_at
        ? new Date(payload.expires_at).toLocaleString("vi-VN")
        : "--";
      expireText.textContent = expireAt;
    }

    const bank = payload.bank || {};
    if (bankCodeText) bankCodeText.textContent = bank.code || "";
    if (bankAccText) bankAccText.textContent = bank.account_number || "";
    if (bankNameText) bankNameText.textContent = bank.account_name || "";

    if (qrImage) {
      const bankCode = bank.code || "";
      const accountNumber = bank.account_number || "";
      const amount = Number(payload.amount_vnd || 0);
      const transferContent = payload.transfer_content || "";

      let qrUrl = payload.qr_image_url || "";

      if (
        !qrUrl &&
        bankCode &&
        accountNumber &&
        amount > 0 &&
        transferContent
      ) {
        const params = new URLSearchParams({
          acc: String(accountNumber),
          bank: String(bankCode),
          amount: String(Math.round(amount)),
          des: String(transferContent),
          template: "compact",
        });
        qrUrl = `https://qr.sepay.vn/img?${params.toString()}`;
      }

      if (qrUrl) {
        qrImage.src = qrUrl;
        qrImage.style.display = "block";
      } else {
        qrImage.removeAttribute("src");
        qrImage.style.display = "none";

        if (!bankCode || !accountNumber) {
          this.setPaymentStatusText(
            "Chưa cấu hình tài khoản nhận tiền (PAYMENT_BANK_*) nên không thể tạo QR.",
            "error",
          );
        }
      }
    }

    this.startCountdown(payload.remaining_seconds);
  }

  startCountdown(initialSeconds) {
    const countdownEl = document.getElementById("paymentCountdown");
    if (!countdownEl) return;

    if (this.paymentCountdownTimer) {
      clearInterval(this.paymentCountdownTimer);
      this.paymentCountdownTimer = null;
    }

    const updateCountdown = () => {
      if (!this.paymentExpireAtMs) {
        countdownEl.textContent = "--:--";
        return;
      }

      const remaining = Math.max(
        0,
        Math.floor((this.paymentExpireAtMs - Date.now()) / 1000),
      );
      countdownEl.textContent = this.formatSeconds(remaining);
      if (remaining <= 0) {
        clearInterval(this.paymentCountdownTimer);
        this.paymentCountdownTimer = null;
      }
    };

    if (
      Number.isFinite(Number(initialSeconds)) &&
      Number(initialSeconds) >= 0 &&
      !this.paymentExpireAtMs
    ) {
      this.paymentExpireAtMs = Date.now() + Number(initialSeconds) * 1000;
    }

    updateCountdown();
    this.paymentCountdownTimer = setInterval(updateCountdown, 1000);
  }

  async loadCurrentPendingInvoice() {
    try {
      const response = await fetch("/api/payment/current", {
        method: "GET",
        headers: {
          ...this.auth.getAuthHeaders(),
        },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.has_pending || !payload.invoice) {
        return;
      }

      this.renderPaymentInstructions(payload.invoice);
      this.setPaymentStatusText(
        "Đã khôi phục hóa đơn đang chờ. Hệ thống sẽ tiếp tục kiểm tra tự động.",
      );
      this.startPaymentPolling(payload.invoice.hex_id);
    } catch (err) {
      console.warn("loadCurrentPendingInvoice failed", err);
    }
  }

  async reconcilePendingInvoiceSilently() {
    try {
      const response = await fetch("/api/payment/current", {
        method: "GET",
        headers: {
          ...this.auth.getAuthHeaders(),
        },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.has_pending || !payload.invoice) {
        return;
      }

      const previousPlan = String(this.auth.profile?.plan || "").toLowerCase();
      await this.pollPaymentStatus(payload.invoice.hex_id);

      const nextPlan = String(this.auth.profile?.plan || "").toLowerCase();
      if (nextPlan && previousPlan && nextPlan !== previousPlan) {
        UIManager.showNotification(
          "Đã đồng bộ thanh toán thành công và cập nhật gói của bạn.",
          "success",
        );
      }
    } catch (err) {
      console.warn("reconcilePendingInvoiceSilently failed", err);
    }
  }

  async copyTransferContent() {
    const transferText = document.getElementById("paymentTransferContent");
    const value = (transferText && transferText.textContent) || "";
    if (!value) {
      this.setPaymentStatusText(
        "Chưa có nội dung chuyển khoản để sao chép.",
        "error",
      );
      return;
    }

    try {
      await navigator.clipboard.writeText(value);
      UIManager.showNotification(
        "Đã sao chép nội dung chuyển khoản.",
        "success",
      );
    } catch (err) {
      this.setPaymentStatusText(
        "Không thể sao chép tự động, vui lòng copy thủ công.",
        "error",
      );
    }
  }

  checkPaymentNow() {
    if (!this.activePaymentHexId) {
      this.setPaymentStatusText("Chưa có hóa đơn để kiểm tra.", "error");
      return;
    }
    this.pollPaymentStatus(this.activePaymentHexId);
  }

  recreateInvoice() {
    if (!this.activePaymentPackageId) {
      this.setPaymentStatusText(
        "Không xác định được gói hiện tại để tạo lại hóa đơn.",
        "error",
      );
      return;
    }
    this.startUpgrade(this.activePaymentPackageId, { forceNew: true });
  }

  stopPaymentPolling() {
    if (this.paymentPollTimer) {
      clearInterval(this.paymentPollTimer);
      this.paymentPollTimer = null;
    }

    if (this.paymentCountdownTimer) {
      clearInterval(this.paymentCountdownTimer);
      this.paymentCountdownTimer = null;
    }

    this.activePaymentHexId = null;
    this.activePaymentPackageId = null;
    this.paymentExpireAtMs = null;
  }

  startPaymentPolling(hexId) {
    this.stopPaymentPolling();
    this.activePaymentHexId = hexId;
    this.paymentPollTimer = setInterval(() => {
      this.pollPaymentStatus(hexId);
    }, 8000);
    this.pollPaymentStatus(hexId);
  }

  async pollPaymentStatus(hexId) {
    if (!hexId) return;
    try {
      const response = await fetch(
        `/api/payment/status/${encodeURIComponent(hexId)}`,
        {
          method: "GET",
          headers: {
            ...this.auth.getAuthHeaders(),
          },
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          payload.error || "Không thể kiểm tra trạng thái thanh toán",
        );
      }

      if (payload.status === "completed") {
        await this._handlePaymentCompleted(payload);
        return;
      }

      if (payload.status === "failed") {
        this.setPaymentStatusText(
          "Hóa đơn đã hết hạn. Bạn có thể tạo lại thanh toán mới.",
          "error",
        );
        if (payload.remaining_seconds !== undefined) {
          this.startCountdown(payload.remaining_seconds);
        }
        return;
      }

      if (payload.expires_at) {
        this.paymentExpireAtMs = new Date(payload.expires_at).getTime();
      }
      if (payload.remaining_seconds !== undefined) {
        this.startCountdown(payload.remaining_seconds);
      }

      this.setPaymentStatusText(
        "Đang chờ giao dịch ngân hàng. Hệ thống tự kiểm tra mỗi 8 giây...",
      );
    } catch (err) {
      this.setPaymentStatusText(
        `Lỗi kiểm tra trạng thái: ${err.message || err}`,
        "error",
      );
    }
  }

  startUpgrade(plan, options = {}) {
    if (!this.auth.isAuthenticated()) {
      this.auth.redirectToLogin();
      return;
    }

    const currentPlan = String(this.auth.profile?.plan || "free").toLowerCase();
    if (
      plan === currentPlan &&
      plan !== "free" &&
      !this._canRepurchasePlan(plan)
    ) {
      UIManager.showNotification(
        "Bạn còn quá nhiều token. Chỉ có thể mua lại gói khi token còn lại ≤ 10% hạn mức.",
        "error",
      );
      return;
    }

    const forceNew = Boolean(options.forceNew);

    // Development mode: support fake tokens by updating cached user locally
    const token = localStorage.getItem("token") || "";
    if (String(token).startsWith("fake")) {
      try {
        const cached = localStorage.getItem("user");
        const parsed = cached ? JSON.parse(cached) : {};
        const planNameMap = { free: "Free", pro: "Pro", promax: "ProMax" };
        parsed.plan = plan;
        parsed.plan_name = planNameMap[plan] || plan;
        localStorage.setItem("user", JSON.stringify(parsed));
      } catch (e) {
        // ignore
      }
      UIManager.showNotification("Đã nâng cấp gói (Dev local).", "success");
      this.closeUpgradeModal();
      this.auth.loadUserInfo();
      return;
    }

    UIManager.showNotification("Đang tạo hóa đơn thanh toán...", "info");

    fetch("/api/payment/create", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...this.auth.getAuthHeaders(),
      },
      body: JSON.stringify({ package_id: plan, force_new: forceNew }),
    })
      .then(async (res) => {
        const payload = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(payload.error || "Không tạo được hóa đơn thanh toán");
        }
        return payload;
      })
      .then((payload) => {
        // If the created/reused invoice is already completed (edge case: webhook already processed it)
        if (payload.status === "completed") {
          this._handlePaymentCompleted(payload);
          return;
        }
        this.renderPaymentInstructions(payload);
        if (payload.is_reused) {
          this.setPaymentStatusText(
            "Đang sử dụng lại hóa đơn đang chờ thanh toán.",
          );
        } else {
          this.setPaymentStatusText(
            "Đã tạo hóa đơn mới. Vui lòng chuyển khoản đúng nội dung.",
          );
        }
        this.startPaymentPolling(payload.hex_id);
      })
      .catch((err) => {
        UIManager.showNotification(
          `Không thể tạo thanh toán: ${err.message || err}`,
          "error",
        );
      });
  }

  // Shared handler: called whenever a payment is confirmed completed
  async _handlePaymentCompleted(payload) {
    this.stopPaymentPolling();

    const planView = document.getElementById("planSelectionView");
    const paymentBox = document.getElementById("paymentBox");
    const successBox = document.getElementById("paymentSuccessBox");
    if (planView) planView.style.display = "none";
    if (paymentBox) paymentBox.style.display = "none";
    if (successBox) {
      const detailEl = document.getElementById("paymentSuccessDetail");
      if (detailEl) {
        const planLabel = payload.package_name || payload.package_id || "mới";
        const tokenAmt = Number(payload.token_amount || 0);
        const tokenStr =
          tokenAmt > 0 ? ` với ${tokenAmt.toLocaleString("vi-VN")} token` : "";
        detailEl.textContent = `Gói ${planLabel} đã được kích hoạt${tokenStr}. Cảm ơn bạn!`;
      }
      const cdEl = document.getElementById("paymentSuccessCountdown");
      if (cdEl) cdEl.textContent = "3";
      successBox.style.display = "block";

      let secs = 3;
      const cdTimer = setInterval(() => {
        secs--;
        if (cdEl) cdEl.textContent = String(secs);
        if (secs <= 0) clearInterval(cdTimer);
      }, 1000);
    }

    UIManager.showNotification(
      "Thanh toán thành công, đã nâng cấp gói.",
      "success",
    );
    await this.auth.loadUserInfo();
    this._updatePlanCardStates();
    setTimeout(() => this.closeUpgradeModal(), 3500);
  }

  async loadInitialData() {
    await fetchTranslationProviders();
    const profile = await this.auth.loadUserInfo();
    // If profile not available (invalid token or not logged in), show login prompt
    if (!profile) {
      this.showLoginRequired();
      return;
    }

    await this.stats.loadStats();
    await this.history.loadHistory();

    // Apply saved settings to UI
    try {
      const s = loadSettings();
      applySettingsToUI(s);
    } catch (e) {
      // ignore
    }

    // Update authentication UI
    this.auth.updateAuthUI();
    this._updatePlanCardStates();

    // If user transferred and reloaded page, silently reconcile latest pending invoice.
    this.reconcilePendingInvoiceSilently();
  }
}

// Global functions for HTML onclick handlers
function showTab(tabName) {
  UIManager.showTab(tabName);
}

function translateText() {
  if (
    typeof dashboard === "undefined" ||
    !dashboard ||
    !dashboard.translation
  ) {
    UIManager.showError(
      UIManager.uiT("msg.appNotReady", "App not ready. Please reload."),
    );
    return;
  }
  dashboard.translation.translateText();
}

function copyResult() {
  dashboard.translation.copyResult();
}

function saveTranslation() {
  dashboard.translation.saveTranslation();
}

function filterHistory() {
  dashboard.history.filterHistory();
}

function changePage(direction) {
  dashboard.history.changePage(direction);
}

function uploadDocument() {
  dashboard.upload.uploadDocument();
}

function closeNotification() {
  UIManager.hideNotification();
}

function clearFile() {
  dashboard.upload.resetUpload();
}

function uploadImageForTranslation() {
  dashboard.ocr.uploadImageForTranslation();
}

function clearImage() {
  dashboard.ocr.clearImage();
}

function downloadResult() {
  const outputText = document.getElementById("outputText").textContent;
  const blob = new Blob([outputText], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "translated_text.txt";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  UIManager.showNotification("Đã tải xuống file kết quả!", "success");
}

function downloadHTML() {
  const previewPane = document.getElementById("previewPane");
  let bodyContent = previewPane
    ? previewPane.innerHTML
    : document.getElementById("outputText").textContent;
  // If preview contains plain text wrapped in <pre>, extract text
  if (/<pre>/.test(bodyContent)) {
    bodyContent = document
      .getElementById("outputText")
      .textContent.replace(/\n/g, "<br>");
  }
  const full = `<!doctype html><html><head><meta charset="utf-8"><title>Translated</title><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="font-family: Inter, Arial, sans-serif; padding:20px; background:#fff; color:#111">${bodyContent}</body></html>`;
  const blob = new Blob([full], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "translated.html";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  UIManager.showNotification("Đã tải xuống HTML!", "success");
}

// Improve notification creator for toast display
UIManager.showToastNotification = function (message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `notification ${type}`;
  notification.innerHTML = `
            <i class="fas ${type === "success" ? "fa-check-circle" : type === "error" ? "fa-exclamation-circle" : "fa-info-circle"}"></i>
            ${message}
        `;
  document.body.appendChild(notification);
  setTimeout(() => notification.classList.add("show"), 50);
  setTimeout(() => {
    notification.classList.remove("show");
    setTimeout(() => document.body.removeChild(notification), 300);
  }, 3000);
};

function downloadTranslatedFile() {
  // This function is called from the success message
  // The actual download is handled in the uploadDocument method
}

function toggleUserMenu() {
  dashboard.toggleUserMenu();
}

function logout() {
  dashboard.auth.logout();
}

function openUpgradeModal() {
  dashboard.openUpgradeModal();
}
function closeUpgradeModal() {
  dashboard.closeUpgradeModal();
}
function startUpgrade(plan) {
  dashboard.startUpgrade(plan);
}

function openSettingsModal() {
  const m = document.getElementById("settingsModal");
  if (m) m.style.display = "block";

  // Populate form from profile + saved settings
  try {
    const profile = dashboard?.auth?.profile;
    const nameInput = document.getElementById("userFullName");
    const emailInput = document.getElementById("userEmail");
    if (profile) {
      if (nameInput) nameInput.value = profile.name || "";
      if (emailInput) emailInput.value = profile.email || "";
    }
    const s = loadSettings();
    applySettingsToUI(s);
  } catch (e) {
    // ignore
  }
}

function closeSettingsModal() {
  const m = document.getElementById("settingsModal");
  if (m) m.style.display = "none";
}

async function updateProfile() {
  const name = (document.getElementById("userFullName") || {}).value || "";
  if (!dashboard?.auth?.isAuthenticated()) {
    UIManager.showNotification("Vui lòng đăng nhập.", "error");
    return;
  }
  try {
    const resp = await fetch("/api/auth/profile", {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...dashboard.auth.getAuthHeaders(),
      },
      body: JSON.stringify({ name }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || "Update failed");
    }
    const data = await resp.json();
    // Refresh cached profile
    dashboard.auth.profile = { ...(dashboard.auth.profile || {}), ...data };
    UIManager.showNotification("Đã cập nhật thông tin!", "success");
    await dashboard.auth.loadUserInfo();
  } catch (e) {
    console.error("updateProfile error", e);
    UIManager.showNotification(e.message || "Có lỗi khi cập nhật.", "error");
  }
}

function loadSettings() {
  try {
    const raw = localStorage.getItem("dashboard_settings");
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveSettings() {
  const providerFromSettings = (
    document.getElementById("translationProvider") || {}
  ).value;
  const providerFromUpload = (
    document.getElementById("uploadTranslationProvider") || {}
  ).value;
  const s = {
    defaultTargetLang: (document.getElementById("defaultTargetLang") || {})
      .value,
    translationProvider: providerFromSettings || providerFromUpload || "google",
    autoSave: !!(document.getElementById("autoSave") || {}).checked,
    emailNotifications: !!(document.getElementById("emailNotifications") || {})
      .checked,
    translationComplete: !!(
      document.getElementById("translationComplete") || {}
    ).checked,
  };
  localStorage.setItem("dashboard_settings", JSON.stringify(s));
  applySettingsToUI(s);
  UIManager.showNotification("Đã lưu cài đặt!", "success");
}

function applySettingsToUI(s) {
  if (!s) return;
  const defaultTarget = document.getElementById("defaultTargetLang");
  if (defaultTarget && s.defaultTargetLang)
    defaultTarget.value = s.defaultTargetLang;

  const plan = String(dashboard?.auth?.profile?.plan || "free").toLowerCase();
  const providerSel = document.getElementById("translationProvider");
  const uploadProviderSel = document.getElementById(
    "uploadTranslationProvider",
  );
  const picked = pickProviderForPlan(plan, s.translationProvider || "google");
  if (providerSel) providerSel.value = picked;
  if (uploadProviderSel) uploadProviderSel.value = picked;

  const autoSave = document.getElementById("autoSave");
  if (autoSave && typeof s.autoSave === "boolean")
    autoSave.checked = s.autoSave;

  const emailNotifications = document.getElementById("emailNotifications");
  if (emailNotifications && typeof s.emailNotifications === "boolean")
    emailNotifications.checked = s.emailNotifications;

  const translationComplete = document.getElementById("translationComplete");
  if (translationComplete && typeof s.translationComplete === "boolean")
    translationComplete.checked = s.translationComplete;

  // Apply default target language to translate/upload selects when available
  if (s.defaultTargetLang) {
    const targetLang = document.getElementById("targetLang");
    if (targetLang) targetLang.value = s.defaultTargetLang;
    const uploadTargetLang = document.getElementById("uploadTargetLang");
    if (uploadTargetLang) uploadTargetLang.value = s.defaultTargetLang;
    const imageTargetLang = document.getElementById("imageTargetLang");
    if (imageTargetLang) imageTargetLang.value = s.defaultTargetLang;
  }
}

let _translationProvidersMeta = { models: [], default_by_plan: {} };

async function fetchTranslationProviders() {
  try {
    const res = await fetch("/api/public/translation-providers");
    if (!res.ok) return _translationProvidersMeta;
    const data = await res.json();
    _translationProvidersMeta = {
      models: Array.isArray(data.models) ? data.models : [],
      default_by_plan:
        data.default_by_plan && typeof data.default_by_plan === "object"
          ? data.default_by_plan
          : {},
    };
  } catch (e) {
    _translationProvidersMeta = {
      models: [
        {
          id: "google",
          label: "Google Translate",
          plans: ["free", "pro", "promax"],
        },
        { id: "deepl", label: "DeepL", plans: ["pro", "promax"] },
        {
          id: "gemini",
          label: "Gemini 2.5 Flash (OpenRouter)",
          plans: ["promax"],
        },
      ],
      default_by_plan: { free: "google", pro: "google", promax: "google" },
    };
  }
  return _translationProvidersMeta;
}

function getAllowedProvidersForPlan(plan) {
  const planNorm = String(plan || "free").trim().toLowerCase();
  return (_translationProvidersMeta.models || []).filter((m) =>
    (m.plans || []).map((x) => String(x).toLowerCase()).includes(planNorm),
  );
}

function getAllowedProviderIds(plan) {
  return getAllowedProvidersForPlan(plan).map((m) =>
    String(m.id || "").toLowerCase(),
  );
}

function pickProviderForPlan(plan, preferred) {
  const allowed = getAllowedProviderIds(plan);
  const pref = String(preferred || "")
    .trim()
    .toLowerCase();
  if (allowed.includes(pref)) return pref;
  const fallback = String(
    (_translationProvidersMeta.default_by_plan || {})[plan] || "",
  )
    .trim()
    .toLowerCase();
  if (allowed.includes(fallback)) return fallback;
  return allowed[0] || "google";
}

function syncTranslationProvidersForPlan(plan) {
  if (!_translationProvidersMeta.models?.length) {
    _translationProvidersMeta = {
      models: [
        {
          id: "google",
          label: "Google Translate",
          plans: ["free", "pro", "promax"],
        },
        { id: "deepl", label: "DeepL", plans: ["pro", "promax"] },
        {
          id: "gemini",
          label: "Gemini 2.5 Flash (OpenRouter)",
          plans: ["promax"],
        },
      ],
      default_by_plan: { free: "google", pro: "google", promax: "google" },
    };
  }
  const planNorm = String(plan || "free").trim().toLowerCase();
  const allowed = getAllowedProvidersForPlan(planNorm);
  if (!allowed.length) return;

  const s = loadSettings();
  const preferred = pickProviderForPlan(
    planNorm,
    s.translationProvider || "google",
  );

  ["translationProvider", "uploadTranslationProvider"].forEach((selId) => {
    const sel = document.getElementById(selId);
    if (!sel) return;
    sel.innerHTML = allowed
      .map(
        (m) =>
          `<option value="${String(m.id).replace(/"/g, "&quot;")}">${String(m.label || m.id).replace(/</g, "&lt;")}</option>`,
      )
      .join("");
    sel.value = pickProviderForPlan(planNorm, sel.value || preferred);
  });

  const next = pickProviderForPlan(planNorm, preferred);
  if (next !== s.translationProvider) {
    s.translationProvider = next;
    localStorage.setItem("dashboard_settings", JSON.stringify(s));
  }
}

function getSelectedTranslationProvider() {
  const plan = String(dashboard?.auth?.profile?.plan || "free").toLowerCase();
  const allowed = getAllowedProviderIds(plan);

  const uploadProviderSel = document.getElementById(
    "uploadTranslationProvider",
  );
  const fromUploadUI = String(
    (uploadProviderSel && uploadProviderSel.value) || "",
  )
    .trim()
    .toLowerCase();
  if (allowed.includes(fromUploadUI)) {
    return fromUploadUI;
  }

  const providerSel = document.getElementById("translationProvider");
  const fromUI = String((providerSel && providerSel.value) || "")
    .trim()
    .toLowerCase();
  if (allowed.includes(fromUI)) {
    return fromUI;
  }

  const s = loadSettings();
  return pickProviderForPlan(plan, s.translationProvider || "google");
}

function persistTranslationProvider(provider) {
  const plan = String(dashboard?.auth?.profile?.plan || "free").toLowerCase();
  const normalized = pickProviderForPlan(plan, provider);
  if (!getAllowedProviderIds(plan).includes(normalized)) {
    return;
  }

  const s = loadSettings();
  s.translationProvider = normalized;
  localStorage.setItem("dashboard_settings", JSON.stringify(s));
  applySettingsToUI(s);
}

async function deleteHistoryItem(id) {
  const ok = await showConfirm({
    title: "Xóa bản dịch",
    message: "Bạn có chắc muốn xóa bản dịch này?",
    confirmText: "Xóa",
    danger: true,
  });
  if (!ok) return;
  try {
    const response = await fetch(`/api/history/${id}`, {
      method: "DELETE",
      headers: dashboard.auth.getAuthHeaders(),
    });

    if (response.ok) {
      UIManager.showNotification("Đã xóa bản dịch!", "success");
      dashboard.history.loadHistory();
      dashboard.auth.loadUserInfo();
      dashboard.stats.loadStats();
    } else {
      throw new Error("Delete failed");
    }
  } catch (error) {
    console.error("Error deleting history item:", error);
    UIManager.showNotification("Có lỗi khi xóa bản dịch!", "error");
  }
}

// Initialize dashboard when DOM is loaded
let dashboard;
document.addEventListener("DOMContentLoaded", () => {
  dashboard = new DashboardController();

  // Keep translation provider synced between upload quick selector and settings modal.
  try {
    const uploadProviderSel = document.getElementById(
      "uploadTranslationProvider",
    );
    if (uploadProviderSel) {
      uploadProviderSel.addEventListener("change", (e) => {
        persistTranslationProvider((e.target || {}).value);
      });
    }

    const settingsProviderSel = document.getElementById("translationProvider");
    if (settingsProviderSel) {
      settingsProviderSel.addEventListener("change", (e) => {
        persistTranslationProvider((e.target || {}).value);
      });
    }
  } catch (e) {
    // ignore
  }

  // Deep-link from Home pricing buttons: /dashboard?upgrade_plan=pro
  try {
    const params = new URLSearchParams(window.location.search);
    const urlPlan = (params.get("upgrade_plan") || "").trim().toLowerCase();
    const storedPlan = (localStorage.getItem("pending_upgrade_plan") || "")
      .trim()
      .toLowerCase();

    const plan = urlPlan || storedPlan;
    const token = localStorage.getItem("token") || "";
    const shouldAutoCreate =
      params.get("autocreate") === "1" || params.get("autocreate") === "true";

    if (plan && token) {
      dashboard.openUpgradeModal();

      if (shouldAutoCreate || storedPlan) {
        // Small delay to ensure modal DOM is ready
        setTimeout(() => dashboard.startUpgrade(plan), 50);
      }
    }

    if (storedPlan) localStorage.removeItem("pending_upgrade_plan");
    if (urlPlan) {
      params.delete("upgrade_plan");
      params.delete("autocreate");
      const qs = params.toString();
      const newUrl =
        window.location.pathname +
        (qs ? `?${qs}` : "") +
        (window.location.hash || "");
      window.history.replaceState({}, document.title, newUrl);
    }
  } catch (e) {
    // ignore
  }
});

// Add notification styles dynamically
const style = document.createElement("style");
style.textContent = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 15px 20px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
    }

    .notification.show {
        transform: translateX(0);
    }

    .notification.success {
        border-color: #4CAF50;
    }

    .notification.error {
        border-color: rgba(139,0,0,0.35);
        background: linear-gradient(90deg, #0B0F1A, #6B0000);
        box-shadow: 0 8px 30px rgba(139,0,0,0.12);
    }

    .upload-area.drag-over {
        border-color: #ffd700;
        background: rgba(255, 215, 0, 0.1);
    }
`;
document.head.appendChild(style);
