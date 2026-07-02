// auth_state.js - manage auth state across pages
(function () {
  async function fetchProfileAndCache(token) {
    if (!token || String(token).startsWith("fake")) return null;
    try {
      const response = await fetch("/api/auth/profile", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return null;
      const profile = await response.json();
      if (profile && (profile.name || profile.email)) {
        // Merge with any existing local-only fields
        let existing = null;
        try {
          existing = JSON.parse(localStorage.getItem("user") || "null");
        } catch (e) {
          existing = null;
        }
        const merged = { ...(existing || {}), ...profile };
        localStorage.setItem("user", JSON.stringify(merged));
      }
      if (
        profile &&
        profile.account_status === "pending_delete" &&
        !window.location.pathname.includes("account-pending-delete") &&
        !window.location.pathname.includes("/auth")
      ) {
        window.location.href = "/account-pending-delete";
        return profile;
      }
      if (
        profile &&
        profile.account_status === "deleted" &&
        !window.location.pathname.includes("/auth")
      ) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        window.location.href = "/auth?error=account_deleted";
        return null;
      }
      return profile;
    } catch (e) {
      console.warn("Profile fetch failed", e);
      return null;
    }
  }

  async function consumeTokenFromUrlIfPresent() {
    try {
      const params = new URLSearchParams(window.location.search);
      const urlToken = params.get("token");
      if (!urlToken) return null;

      localStorage.setItem("token", urlToken);
      await fetchProfileAndCache(urlToken);

      // Clean URL (remove token but keep other params)
      params.delete("token");
      const qs = params.toString();
      const newUrl =
        window.location.pathname +
        (qs ? `?${qs}` : "") +
        (window.location.hash || "");
      window.history.replaceState({}, document.title, newUrl);
      return urlToken;
    } catch (e) {
      console.warn("Failed to consume token from URL", e);
      return null;
    }
  }

  function getUser() {
    try {
      const token = localStorage.getItem("token");
      const user = localStorage.getItem("user");
      return token ? (user ? JSON.parse(user) : { name: "User" }) : null;
    } catch (e) {
      console.error("getUser parse error", e);
      return null;
    }
  }

  function setLoggedInUI(user) {
    // Find nav container
    const navLinks = document.querySelector(".nav-links");
    if (!navLinks) return;

    // Avoid duplicate user menu if init runs more than once
    if (navLinks.querySelector(".nav-user")) return;

    // Remove existing login/register buttons
    navLinks
      .querySelectorAll(".btn-login, .btn-register")
      .forEach((el) => el.remove());

    // ── Notification Bell ──────────────────────────────────────────────────
    if (!navLinks.querySelector(".nav-bell")) {
      const bell = document.createElement("div");
      bell.className = "nav-bell";
      bell.innerHTML = `
        <button class="nav-bell-btn" title="Thông báo" tabindex="0" aria-label="Thông báo">
          <i class="fas fa-bell"></i>
          <span class="nav-bell-badge" style="display:none">0</span>
        </button>
        <div class="nav-bell-dropdown">
          <div class="nav-bell-header">
            <span>Thông báo</span>
            <button class="nav-bell-markall" title="Đánh dấu đã đọc tất cả">✓ Đọc tất cả</button>
          </div>
          <div class="nav-bell-list">
            <p class="nav-bell-empty"><i class="fas fa-inbox"></i><br>Không có thông báo</p>
          </div>
        </div>`;
      navLinks.insertBefore(bell, navLinks.firstChild);

      // Toggle dropdown
      const bellBtn = bell.querySelector(".nav-bell-btn");
      const dropdown = bell.querySelector(".nav-bell-dropdown");
      bellBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = dropdown.classList.toggle("open");
        if (isOpen) loadNotifications(bell);
      });
      document.addEventListener("click", (e) => {
        if (!bell.contains(e.target)) dropdown.classList.remove("open");
      });
      bell.querySelector(".nav-bell-markall").addEventListener("click", () => {
        const msgs = JSON.parse(localStorage.getItem("_notif_msgs") || "[]");
        const ids = msgs.filter((m) => m.admin_reply).map((m) => m.id);
        markNotifSeen(ids);
        bell.querySelector(".nav-bell-badge").style.display = "none";
        renderNotifList(bell, msgs, ids);
      });

      // Initial load (count badge)
      loadNotifications(bell);
    }

    // Create user menu with avatar and dropdown
    const userWrap = document.createElement("div");
    userWrap.className = "nav-user";
    const initials = (user.name || "U").trim()[0].toUpperCase();
    const secondary = user.email || "CodeQuest Member";
    const avatarUrl = user.avatarUrl || user.avatar_url;
    userWrap.innerHTML = `
      <div class="nav-user-button" tabindex="0">
        <div class="nav-user-avatar">
          ${avatarUrl ? `<img src="${escapeHtml(avatarUrl)}" alt="avatar" referrerpolicy="no-referrer" onerror="this.remove(); this.parentElement.textContent='${escapeHtml(initials)}';" />` : escapeHtml(initials)}
        </div>
        <div class="nav-user-info">
          <div class="nav-user-name">${escapeHtml(user.name || "User")}</div>
          <div class="nav-user-role">${escapeHtml(secondary)}</div>
        </div>
        <div class="nav-user-caret">▾</div>
      </div>
      <div class="nav-user-dropdown">
        <a href="/dashboard" class="nav-user-item">Dashboard</a>
        <a href="/profile" class="nav-user-item">Cài đặt tài khoản</a>
        ${user.role === "admin" ? '<a href="/admin" class="nav-user-item" style="color:#00ffd1"><i class="fas fa-shield-halved"></i> Quản trị</a>' : ""}
        <button id="nav-logout-btn" class="nav-user-item nav-user-logout">Đăng xuất</button>
      </div>
    `;

    navLinks.appendChild(userWrap);

    // Dropdown behavior
    const btn = userWrap.querySelector(".nav-user-button");
    const dropdown = userWrap.querySelector(".nav-user-dropdown");
    function closeDropdown() {
      dropdown.classList.remove("open");
    }
    function openDropdown() {
      dropdown.classList.add("open");
    }

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (dropdown.classList.contains("open")) closeDropdown();
      else openDropdown();
    });
    btn.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        btn.click();
      }
      if (e.key === "Escape") closeDropdown();
    });

    document.addEventListener("click", (e) => {
      if (!userWrap.contains(e.target)) closeDropdown();
    });

    const logoutBtn = document.getElementById("nav-logout-btn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        // reload to update UI
        window.location.reload();
      });
    }

    if (window.SiteI18n) {
      window.SiteI18n.injectLangSwitcher();
      window.SiteI18n.applySiteLanguage(window.SiteI18n.getLang());
    }
    window.dispatchEvent(new CustomEvent("authUiReady"));
  }

  function setLoggedOutUI() {
    const navLinks = document.querySelector(".nav-links");
    if (!navLinks) return;
    // Remove any existing user UI
    navLinks.querySelectorAll(".nav-user").forEach((el) => el.remove());

    // Hide/remove any static logout button if present (prevents showing only "Đăng xuất" when not logged in)
    const staticLogout = navLinks.querySelector("#logoutBtn");
    if (staticLogout) staticLogout.remove();

    // If no login button exists, add one
    if (!navLinks.querySelector(".btn-login")) {
      const loginBtn = document.createElement("button");
      loginBtn.className = "btn-login";
      loginBtn.textContent = window.SiteI18n
        ? window.SiteI18n.t("nav.login")
        : "Sign in";
      loginBtn.addEventListener(
        "click",
        () => (window.location.href = "/auth"),
      );
      navLinks.appendChild(loginBtn);
    }

    if (window.SiteI18n) {
      window.SiteI18n.injectLangSwitcher();
      window.SiteI18n.applySiteLanguage(window.SiteI18n.getLang());
    }
    window.dispatchEvent(new CustomEvent("authUiReady"));
  }

  // ── Notification helpers ───────────────────────────────────────────────────

  function getSeenIds() {
    try {
      return JSON.parse(localStorage.getItem("_notif_seen") || "[]");
    } catch {
      return [];
    }
  }

  function markNotifSeen(ids) {
    const seen = getSeenIds();
    const merged = Array.from(new Set([...seen, ...ids]));
    localStorage.setItem("_notif_seen", JSON.stringify(merged));
  }

  async function loadNotifications(bellEl) {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch("/api/contact/my-messages", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const d = await res.json();
      const msgs = (d.messages || []).filter((m) => m.admin_reply);
      localStorage.setItem("_notif_msgs", JSON.stringify(msgs));

      const seen = getSeenIds();
      const unread = msgs.filter((m) => !seen.includes(m.id));
      const badge = bellEl.querySelector(".nav-bell-badge");
      if (unread.length > 0) {
        badge.textContent = unread.length > 9 ? "9+" : unread.length;
        badge.style.display = "flex";
      } else {
        badge.style.display = "none";
      }
      renderNotifList(bellEl, msgs, seen);
    } catch (e) {
      /* silently ignore */
    }
  }

  function renderNotifList(bellEl, msgs, seen) {
    const listEl = bellEl.querySelector(".nav-bell-list");
    if (!msgs.length) {
      listEl.innerHTML = `<p class="nav-bell-empty"><i class="fas fa-inbox"></i><br>Không có thông báo</p>`;
      return;
    }
    const SUBJECT_MAP = {
      general: "Câu hỏi chung",
      technical: "Hỗ trợ kỹ thuật",
      billing: "Thanh toán",
      partnership: "Hợp tác",
      other: "Khác",
    };
    listEl.innerHTML = msgs
      .map((m) => {
        const isNew = !seen.includes(m.id);
        const subj = SUBJECT_MAP[m.subject] || m.subject;
        const dt = m.replied_at
          ? new Date(m.replied_at).toLocaleString("vi-VN", {
              dateStyle: "short",
              timeStyle: "short",
            })
          : "";
        return `
        <div class="nav-bell-item${isNew ? " unread" : ""}" data-id="${m.id}"
             onclick="(function(el){
               var body = el.querySelector('.nav-bell-item-body');
               body.style.display = body.style.display === 'none' ? 'block' : 'none';
               el.classList.remove('unread');
               var ids = [${m.id}];
               try{ var s=JSON.parse(localStorage.getItem('_notif_seen')||'[]');
                 localStorage.setItem('_notif_seen',JSON.stringify([...new Set([...s,...ids])])); }catch(e){}
             })(this)">
          <div class="nav-bell-item-top">
            <span class="nav-bell-item-title">
              ${isNew ? '<span class="nav-bell-dot"></span>' : ""}
              Phản hồi: ${escapeHtml(subj)}
            </span>
            <span class="nav-bell-item-time">${escapeHtml(dt)}</span>
          </div>
          <div class="nav-bell-item-body" style="display:none">
            <div class="nav-bell-item-orig">${escapeHtml(m.message.length > 80 ? m.message.slice(0, 80) + "…" : m.message)}</div>
            <div class="nav-bell-item-reply"><i class="fas fa-reply"></i> ${escapeHtml(m.admin_reply)}</div>
          </div>
        </div>`;
      })
      .join("");
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (m) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[m];
    });
  }

  async function init() {
    // 1) Support OAuth redirect that includes ?token=...
    await consumeTokenFromUrlIfPresent();

    // 2) If we have a token but missing user fields, fetch profile
    const token = localStorage.getItem("token");
    let user = getUser();
    if (token && (!user || (!user.email && !user.name))) {
      await fetchProfileAndCache(token);
      user = getUser();
    }

    if (user) setLoggedInUI(user);
    else setLoggedOutUI();

    // Also support immediate DOM changes on pages that have logout buttons already
    const pageLogout = document.getElementById("logoutBtn");
    if (pageLogout) {
      pageLogout.addEventListener("click", () => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        window.location.reload();
      });
    }
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      init();
      loadSiteConfigScript();
    });
  } else {
    init();
    loadSiteConfigScript();
  }

  function loadSiteConfigScript() {
    if (document.querySelector('script[src="/js/site_config.js"]')) return;
    const s = document.createElement("script");
    s.src = "/js/site_config.js";
    s.defer = true;
    document.body.appendChild(s);
  }
})();
