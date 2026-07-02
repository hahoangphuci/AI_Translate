/* Site UI language — default English, switch to Vietnamese on demand */
(function () {
  const STORAGE_KEY = "site_ui_lang";
  const DEFAULT_LANG = "en";

  const MESSAGES = window.I18N_MESSAGES || {
    en: {},
    vi: {},
  };

  const PAGE_BINDINGS = window.I18N_PAGE_BINDINGS || {};

  /** Nội dung article trên các trang này do Admin chỉnh trong HTML — không ghi đè bằng i18n tĩnh */
  const ADMIN_MANAGED_LEGAL_PATHS = new Set([
    "/privacy",
    "/terms",
    "/ai-terms",
    "/payment-policy",
    "/data-deletion",
    "/support",
  ]);

  const NAV_HREF_KEYS = {
    "/": "nav.home",
    "/#home": "nav.home",
    "#home": "nav.home",
    "/#features": "nav.features",
    "#features": "nav.features",
    "home.html#features": "nav.features",
    "/#pricing": "nav.pricing",
    "#pricing": "nav.pricing",
    "home.html#pricing": "nav.pricing",
    "/about": "nav.about",
    "about.html": "nav.about",
    "#about": "nav.about",
    "/contact": "nav.contact",
    "contact.html": "nav.contact",
    "#contact": "nav.contact",
    "/dashboard": "nav.dashboard",
    "/history": "nav.history",
    "/profile": "nav.settings",
    "/support": "nav.support",
    "/installation": "nav.installation",
    "/user-guide": "nav.userGuide",
    "#translate": "nav.translate",
    "/#translate": "nav.translate",
  };

  const FOOTER_HREF_KEYS = {
    "#features": "footer.features",
    "#pricing": "footer.pricing",
    "/#features": "footer.features",
    "/#pricing": "footer.pricing",
    "home.html#features": "footer.features",
    "home.html#pricing": "footer.pricing",
    "/about": "footer.about",
    "about.html": "footer.about",
    "/contact": "footer.contact",
    "contact.html": "footer.contact",
    "/installation": "footer.installGuide",
    "/user-guide": "footer.userGuide",
    "/support": "footer.faq",
    "/terms": "footer.terms",
    "/privacy": "footer.privacy",
    "/ai-terms": "footer.aiTerms",
    "/payment-policy": "footer.paymentPolicy",
    "/data-deletion": "footer.dataDeletion",
  };

  const LEGAL_NAV_HREF_KEYS = {
    "/privacy": "legal.nav.privacy",
    "/terms": "legal.nav.terms",
    "/ai-terms": "legal.nav.aiTerms",
    "/payment-policy": "legal.nav.paymentPolicy",
    "/data-deletion": "legal.nav.dataDeletion",
    "/support": "legal.nav.support",
  };

  const LEGAL_HERO_KEYS = {
    "/privacy": { title: "legal.privacyTitle", meta: "legal.privacyMeta" },
    "/terms": { title: "legal.termsTitle", meta: "legal.termsMeta" },
    "/ai-terms": { title: "legal.aiTermsTitle", meta: "legal.aiTermsMeta" },
    "/payment-policy": {
      title: "legal.paymentPolicyTitle",
      meta: "legal.paymentPolicyMeta",
    },
    "/data-deletion": {
      title: "legal.dataDeletionTitle",
      meta: "legal.dataDeletionMeta",
    },
    "/support": {
      title: "support.heroTitle",
      meta: "support.heroMeta",
      metaHtml: true,
    },
  };

  /** Trang chủ / liên hệ — nội dung chính do Admin chỉnh, EN lưu trong legal_pages_en.json */
  const ADMIN_MANAGED_FULL_PAGE_SLUGS = {
    "/": "home",
    "/home": "home",
    "/contact": "contact",
  };

  const legalArticleViCache = new Map();
  const fullPageViCache = new Map();
  let legalPagesEnCache = null;
  let legalPagesEnPromise = null;

  function isPageEditMode() {
    return (
      window.__CMS_EDIT_MODE === true ||
      new URLSearchParams(window.location.search).get("edit") === "1"
    );
  }

  function getManagedPageSlug(path) {
    const p = path || getPagePath();
    const fullSlug = getFullPageSlug(p);
    if (fullSlug) return fullSlug;
    if (ADMIN_MANAGED_LEGAL_PATHS.has(p)) return p.replace(/^\//, "");
    return "";
  }

  function fetchPublicPageContent(slug, lang) {
    const qs = new URLSearchParams({
      lang: lang === "vi" ? "vi" : "en",
      _: String(Date.now()),
    });
    return fetch(
      `/api/public/legal-content/${encodeURIComponent(slug)}?${qs.toString()}`,
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => (data && data.content ? String(data.content).trim() : ""))
      .catch(() => "");
  }

  function invalidateManagedContentCaches(path) {
    const p = path || getPagePath();
    legalArticleViCache.delete(p);
    fullPageViCache.delete(p);
  }

  function updateManagedContentCache(path, lang, html) {
    const p = path || getPagePath();
    const content = String(html || "").trim();
    if (!content) return;
    if (lang === "vi") {
      if (ADMIN_MANAGED_LEGAL_PATHS.has(p)) {
        legalArticleViCache.set(p, content);
      }
      if (ADMIN_MANAGED_FULL_PAGE_SLUGS[p]) {
        fullPageViCache.set(p, content);
      }
    }
  }

  function normalizeHref(href) {
    if (!href) return "";
    return String(href).trim();
  }

  function getPagePath() {
    const path = window.location.pathname.replace(/\/$/, "") || "/";
    return path;
  }

  function getLang() {
    try {
      const qp = new URLSearchParams(window.location.search).get("lang");
      if (qp === "vi" || qp === "en") return qp;
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "vi" || stored === "en") return stored;
    } catch (e) {
      /* ignore */
    }
    return DEFAULT_LANG;
  }

  function t(key, lang) {
    const l = lang || getLang();
    return (MESSAGES[l] && MESSAGES[l][key]) || MESSAGES.en[key] || key;
  }

  function setLang(lang) {
    const next = lang === "vi" ? "vi" : "en";
    try {
      localStorage.setItem(STORAGE_KEY, next);
      localStorage.setItem("docs_preferred_lang", next);
    } catch (e) {
      /* ignore */
    }
    applySiteLanguage(next);
    window.dispatchEvent(
      new CustomEvent("siteLanguageChanged", { detail: { lang: next } }),
    );
  }

  function applyText(el, value, binding) {
    if (binding && binding.attr) {
      el.setAttribute(binding.attr, value);
      return;
    }
    if (binding && binding.placeholder) {
      el.placeholder = value;
      return;
    }
    if (binding && binding.html) {
      el.innerHTML = value;
      return;
    }
    el.textContent = value;
  }

  function applyDataI18n(lang) {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      const text = t(key, lang);
      if (el.hasAttribute("data-i18n-html")) {
        el.innerHTML = text;
      } else if (
        el.tagName === "INPUT" ||
        el.tagName === "TEXTAREA" ||
        el.hasAttribute("data-i18n-placeholder")
      ) {
        el.placeholder = text;
      } else {
        el.textContent = text;
      }
    });
  }

  function getFullPageSlug(path) {
    return ADMIN_MANAGED_FULL_PAGE_SLUGS[path || getPagePath()] || "";
  }

  function cacheFullPageVi() {
    const path = getPagePath();
    const slug = getFullPageSlug(path);
    if (!slug || fullPageViCache.has(path)) return;
    const nav = document.querySelector("nav.navbar");
    const footer = document.querySelector("footer.footer");
    if (!nav || !footer) return;
    let html = "";
    let el = nav.nextElementSibling;
    while (el && el !== footer) {
      if (
        el.nodeType === Node.COMMENT_NODE &&
        String(el.textContent || "")
          .trim()
          .toLowerCase() === "page-main-start"
      ) {
        el = el.nextElementSibling;
        continue;
      }
      if (
        el.nodeType === Node.COMMENT_NODE &&
        String(el.textContent || "")
          .trim()
          .toLowerCase() === "page-main-end"
      ) {
        break;
      }
      if (el.nodeType === Node.ELEMENT_NODE) {
        html += el.outerHTML;
      }
      el = el.nextElementSibling;
    }
    if (html.trim()) fullPageViCache.set(path, html);
  }

  function stripCmsEditHtml(html) {
    if (!html) return html;
    return String(html)
      .replace(/\scontenteditable="(?:true|false)"/gi, "")
      .replace(/\sspellcheck="(?:true|false)"/gi, "")
      .replace(/\sclass="([^"]*)"/g, (_match, classNames) => {
        const cleaned = String(classNames || "")
          .split(/\s+/)
          .filter(
            (token) =>
              token && token !== "cms-editing" && token !== "cms-text-editable",
          )
          .join(" ");
        return cleaned ? ` class="${cleaned}"` : "";
      });
  }

  function replaceFullPageMain(html) {
    const nav = document.querySelector("nav.navbar");
    const footer = document.querySelector("footer.footer");
    if (!nav || !footer || !html) return;
    const cleaned = stripCmsEditHtml(html);
    const toRemove = [];
    let el = nav.nextElementSibling;
    while (el && el !== footer) {
      toRemove.push(el);
      el = el.nextElementSibling;
    }
    toRemove.forEach((node) => node.remove());
    const tpl = document.createElement("template");
    tpl.innerHTML = cleaned.trim();
    while (tpl.content.firstChild) {
      footer.parentNode.insertBefore(tpl.content.firstChild, footer);
    }
    if (typeof window.loadSiteConfigPublic === "function") {
      window.loadSiteConfigPublic();
    }
  }

  function applyFullPageLanguage(lang) {
    if (isPageEditMode()) return true;

    const path = getPagePath();
    const slug = getFullPageSlug(path);
    if (!slug) return false;

    const applyHtml = (html) => {
      if (!html) return false;
      replaceFullPageMain(html);
      if (lang === "vi") fullPageViCache.set(path, html);
      return true;
    };

    if (lang === "vi") {
      fetchPublicPageContent(slug, "vi").then((html) => {
        if (html) {
          applyHtml(html);
        } else if (fullPageViCache.has(path)) {
          replaceFullPageMain(fullPageViCache.get(path));
        }
      });
      return true;
    }

    const enPages = legalPagesEnCache || {};
    const customEn = String(enPages[slug] || "").trim();
    if (customEn) {
      replaceFullPageMain(customEn);
      return true;
    }

    fetchPublicPageContent(slug, "en").then((html) => {
      if (html) {
        replaceFullPageMain(html);
      } else {
        cacheFullPageVi();
        const viHtml = fullPageViCache.get(path);
        if (viHtml) {
          replaceFullPageMain(viHtml);
          applyPageBindings("en");
        }
      }
    });
    return true;
  }

  function cacheLegalArticleVi() {
    const path = getPagePath();
    if (!ADMIN_MANAGED_LEGAL_PATHS.has(path)) return;
    const article = document.querySelector("article.legal-content");
    if (!article || legalArticleViCache.has(path)) return;
    legalArticleViCache.set(path, article.innerHTML);
  }

  function hasArticleBindings(path) {
    const bindings = PAGE_BINDINGS[path];
    return (
      bindings &&
      bindings.some((b) => b.sel && b.sel.includes("article.legal-content"))
    );
  }

  function applyArticleBindingsOnly(lang, path, root) {
    const bindings = PAGE_BINDINGS[path];
    if (!bindings) return;
    const scope = root || document;
    bindings.forEach((binding) => {
      if (!binding || !binding.sel || !binding.key) return;
      if (!binding.sel.includes("article.legal-content")) return;
      scope.querySelectorAll(binding.sel).forEach((el) => {
        applyText(el, t(binding.key, lang), binding);
      });
    });
  }

  function previewLegalEnFromVi(slug, viHtml) {
    const normalized = String(slug || "").replace(/^\//, "");
    const path = `/${normalized}`;
    if (!hasArticleBindings(path) || !viHtml) return "";

    const wrap = document.createElement("div");
    wrap.setAttribute("aria-hidden", "true");
    wrap.style.cssText =
      "position:fixed;left:-10000px;top:0;width:1px;height:1px;overflow:hidden;visibility:hidden";
    wrap.innerHTML = `<article class="legal-content glassmorphism">${viHtml}</article>`;
    document.body.appendChild(wrap);
    applyArticleBindingsOnly("en", path, wrap);
    const html = wrap.querySelector("article.legal-content")?.innerHTML || "";
    wrap.remove();
    return html;
  }

  function invalidateLegalPagesEnCache() {
    legalPagesEnCache = null;
    legalPagesEnPromise = null;
  }

  function loadLegalPagesEn() {
    if (legalPagesEnCache) return Promise.resolve(legalPagesEnCache);
    if (legalPagesEnPromise) return legalPagesEnPromise;
    legalPagesEnPromise = fetch("/api/public/site-config/legal-pages-en")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && typeof data === "object") return data;
        return fetch("/config/legal_pages_en.json")
          .then((r) => (r.ok ? r.json() : {}))
          .catch(() => ({}));
      })
      .then((data) => {
        legalPagesEnCache = data && typeof data === "object" ? data : {};
        return legalPagesEnCache;
      })
      .catch(() => {
        legalPagesEnCache = {};
        return legalPagesEnCache;
      });
    return legalPagesEnPromise;
  }

  function applyLegalHero(lang) {
    const path = getPagePath();
    const keys = LEGAL_HERO_KEYS[path];
    if (!keys) return;
    const h1 = document.querySelector(".legal-hero h1");
    const meta = document.querySelector(".legal-meta");
    if (h1 && keys.title) h1.textContent = t(keys.title, lang);
    if (meta && keys.meta) {
      const value = t(keys.meta, lang);
      if (keys.metaHtml) meta.innerHTML = value;
      else meta.textContent = value;
    }
  }

  function applyLegalArticleLanguage(lang) {
    if (isPageEditMode()) return;

    const path = getPagePath();
    if (!ADMIN_MANAGED_LEGAL_PATHS.has(path)) return;

    const article = document.querySelector("article.legal-content");
    if (!article) return;

    const slug = path.replace(/^\//, "");

    const applyHtml = (html) => {
      if (!html) return;
      article.innerHTML = html;
      if (lang === "vi") legalArticleViCache.set(path, html);
    };

    if (lang === "vi") {
      fetchPublicPageContent(slug, "vi").then((html) => {
        if (html) {
          applyHtml(html);
        } else {
          cacheLegalArticleVi();
          const viHtml = legalArticleViCache.get(path);
          if (viHtml) article.innerHTML = viHtml;
        }
      });
      return;
    }

    const enPages = legalPagesEnCache || {};
    const customEn = String(enPages[slug] || enPages[path] || "").trim();
    if (customEn) {
      article.innerHTML = customEn;
      return;
    }

    fetchPublicPageContent(slug, "en").then((html) => {
      if (html) {
        applyHtml(html);
        return;
      }
      cacheLegalArticleVi();
      const viHtml = legalArticleViCache.get(path);
      if (!viHtml) return;
      if (hasArticleBindings(path)) {
        const enHtml = previewLegalEnFromVi(slug, viHtml);
        if (enHtml.trim()) {
          article.innerHTML = enHtml;
          return;
        }
      }
      article.innerHTML = viHtml;
    });
  }

  function applyPageBindings(lang) {
    if (isPageEditMode()) return;

    const path = getPagePath();
    const bindings = PAGE_BINDINGS[path];
    if (!bindings || !bindings.length) return;

    const skipArticleI18n = ADMIN_MANAGED_LEGAL_PATHS.has(path);

    bindings.forEach((binding) => {
      if (!binding || !binding.sel || !binding.key) return;
      if (skipArticleI18n && binding.sel.includes("article.legal-content"))
        return;
      if (skipArticleI18n && binding.sel.includes(".legal-hero h1")) return;
      if (skipArticleI18n && binding.sel.includes(".legal-meta")) return;
      document.querySelectorAll(binding.sel).forEach((el) => {
        if (el.closest("article.legal-content[data-i18n-skip]")) return;
        applyText(el, t(binding.key, lang), binding);
      });
    });
  }

  function applyNavLinks(lang) {
    document.querySelectorAll(".nav-link").forEach((link) => {
      const href = normalizeHref(link.getAttribute("href"));
      const key = NAV_HREF_KEYS[href];
      if (key) link.textContent = t(key, lang);
    });

    document.querySelectorAll(".btn-login").forEach((btn) => {
      if (btn.id === "logoutBtn") {
        btn.innerHTML = `<i class="fas fa-sign-out-alt"></i> ${t("userMenu.logout", lang)}`;
        return;
      }
      if (btn.querySelector("i")) {
        btn.innerHTML = `<i class="fas fa-sign-in-alt"></i> ${t("nav.login", lang)}`;
      } else {
        btn.textContent = t("nav.login", lang);
      }
    });

    document.querySelectorAll(".btn-register").forEach((btn) => {
      btn.textContent = t("nav.register", lang);
    });
  }

  function applyLegalNav(lang) {
    document.querySelectorAll(".legal-nav a[href]").forEach((link) => {
      const href = normalizeHref(link.getAttribute("href"));
      const key = LEGAL_NAV_HREF_KEYS[href];
      if (key) link.textContent = t(key, lang);
    });
  }

  function applyDocsNav(lang) {
    document.querySelectorAll(".docs-nav a[href]").forEach((link) => {
      const href = normalizeHref(link.getAttribute("href"));
      if (href === "/installation")
        link.textContent = t("docs.nav.install", lang);
      else if (href === "/user-guide")
        link.textContent = t("docs.nav.userGuide", lang);
      else if (href === "/support") link.textContent = t("docs.nav.faq", lang);
    });
  }

  function applyFooter(lang) {
    document.querySelectorAll(".footer-section h3").forEach((h3) => {
      const text = h3.textContent.trim();
      if (/Sản phẩm|Product/i.test(text))
        h3.textContent = t("footer.product", lang);
      else if (/Hỗ trợ|Support/i.test(text))
        h3.textContent = t("footer.support", lang);
      else if (/Pháp lý|Legal/i.test(text))
        h3.textContent = t("footer.legal", lang);
    });

    document.querySelectorAll(".footer-section p").forEach((p) => {
      if (p.closest(".footer-section")?.querySelector(".social-links")) {
        p.textContent = t("footer.tagline", lang);
      }
    });

    document.querySelectorAll(".footer-section a[href]").forEach((link) => {
      const href = normalizeHref(link.getAttribute("href"));
      const key = FOOTER_HREF_KEYS[href];
      if (key) link.textContent = t(key, lang);
    });

    document.querySelectorAll(".footer-bottom p").forEach((p) => {
      if (/rights reserved|All rights/i.test(p.textContent)) {
        p.innerHTML = `&copy; 2026 AI Translation System. ${t("footer.rights", lang)}`;
      }
    });
  }

  function applyBell(lang) {
    const header = document.querySelector(".nav-bell-header span");
    if (header) header.textContent = t("bell.title", lang);
    const markAll = document.querySelector(".nav-bell-markall");
    if (markAll) markAll.textContent = t("bell.markAll", lang);
    document.querySelectorAll(".nav-bell-empty").forEach((el) => {
      const icon = el.querySelector("i");
      if (icon) {
        el.innerHTML = `<i class="${icon.className}"></i><br>${t("bell.empty", lang)}`;
      } else {
        el.textContent = t("bell.empty", lang);
      }
    });
  }

  function applyUserMenu(lang) {
    const map = [
      ['a.nav-user-item[href="/dashboard"]', "userMenu.dashboard"],
      ['a.nav-user-item[href="/profile"]', "userMenu.profile"],
      ['a.nav-user-item[href="/admin"]', "userMenu.admin"],
      [".nav-user-logout", "userMenu.logout"],
    ];
    map.forEach(([sel, key]) => {
      document.querySelectorAll(sel).forEach((el) => {
        if (key === "userMenu.admin") {
          el.innerHTML = `<i class="fas fa-shield-halved"></i> ${t(key, lang)}`;
        } else {
          el.textContent = t(key, lang);
        }
      });
    });
  }

  function applyDashboardGreeting(lang) {
    const el = document.querySelector(".db-greeting");
    if (!el) return;
    const nameEl = el.querySelector("#userName, .db-username");
    const name = nameEl ? nameEl.textContent.trim() || "User" : "User";
    el.innerHTML = `${t("dash.greeting", lang)} <span id="userName" class="db-username">${name}</span> 👋`;
  }

  function applyAdminPage(lang) {
    if (!document.querySelector(".admin-sidebar")) return;

    const sidebarMap = [
      ["dashboard", "admin.navOverview"],
      ["users", "admin.navUsers"],
      ["translations", "admin.navTranslations"],
      ["payments", "admin.navPayments"],
      ["contacts", "admin.navContacts"],
      ["newsletter", "admin.navNewsletter"],
      ["audit", "admin.navAudit"],
      ["site-config", "admin.navSiteConfig"],
    ];
    sidebarMap.forEach(([tab, key]) => {
      const el = document.querySelector(`a.sidebar-item[data-tab='${tab}']`);
      if (!el) return;
      const icon = el.querySelector("i");
      const iconHtml = icon ? `<i class="${icon.className}"></i> ` : "";
      el.innerHTML = iconHtml + t(key, lang);
    });

    const backEl = document.querySelector('.sidebar-item[href="/dashboard"]');
    if (backEl) {
      const icon = backEl.querySelector("i");
      const iconHtml = icon ? `<i class="${icon.className}"></i> ` : "";
      backEl.innerHTML = iconHtml + t("admin.navBackDashboard", lang);
    }

    const logoSpan = document.querySelector(".sidebar-logo span");
    if (logoSpan) logoSpan.textContent = t("admin.panelTitle", lang);

    injectAdminLangSwitcher();

    const activeTab = document.querySelector(".sidebar-item.active[data-tab]");
    const topbarTitle = document.getElementById("topbarTitle");
    const topbarSubtitle = document.getElementById("topbarSubtitle");
    if (activeTab && topbarTitle) {
      const tabKey = `admin.tab.${activeTab.dataset.tab}`;
      topbarTitle.textContent = t(tabKey, lang) || activeTab.dataset.tab;
    }
    if (topbarSubtitle) {
      const showSubtitle = activeTab?.dataset.tab === "site-config";
      topbarSubtitle.style.display = showSubtitle ? "" : "none";
      if (showSubtitle) {
        topbarSubtitle.textContent = t("admin.config.pageSubtitle", lang);
      }
    }

    const deniedTitle = document.querySelector(".admin-denied h2");
    const deniedMsg = document.querySelector(".admin-denied p");
    const deniedBtn = document.querySelector(".admin-denied .btn-accent");
    if (deniedTitle) deniedTitle.textContent = t("admin.deniedTitle", lang);
    if (deniedMsg) deniedMsg.textContent = t("admin.deniedMsg", lang);
    if (deniedBtn) deniedBtn.textContent = t("admin.deniedLogin", lang);

    applyAdminPolicyConfig(lang);
  }

  const ADMIN_LEGAL_PAGE_KEYS = {
    privacy: "admin.config.page.privacy",
    terms: "admin.config.page.terms",
    "ai-terms": "admin.config.page.aiTerms",
    "payment-policy": "admin.config.page.paymentPolicy",
    "data-deletion": "admin.config.page.dataDeletion",
    support: "admin.config.page.support",
  };

  function applyAdminPolicyConfig(lang) {
    document.querySelectorAll(".legal-page-tab[data-slug]").forEach((btn) => {
      const key = ADMIN_LEGAL_PAGE_KEYS[btn.dataset.slug];
      if (key) btn.textContent = t(key, lang);
    });

    document
      .querySelectorAll(".legal-lang-btn[data-lang='vi']")
      .forEach((btn) => {
        btn.textContent = t("admin.config.langVi", lang);
      });
    document
      .querySelectorAll(".legal-lang-btn[data-lang='en']")
      .forEach((btn) => {
        btn.textContent = t("admin.config.langEn", lang);
      });

    const logoType = document.getElementById("cfgLogoType");
    if (logoType && logoType.options.length >= 2) {
      logoType.options[0].textContent = t("admin.config.logoIcon", lang);
      logoType.options[1].textContent = t("admin.config.logoImage", lang);
    }
  }

  function injectAdminLangSwitcher() {
    const topbar = document.querySelector(".topbar-right");
    if (!topbar || topbar.querySelector(".nav-lang-switch")) return;

    const wrap = document.createElement("div");
    wrap.className = "nav-lang-switch";
    wrap.setAttribute("role", "group");
    wrap.setAttribute("aria-label", "Language");
    wrap.innerHTML = `
      <button type="button" data-ui-lang="en" title="English">EN</button>
      <button type="button" data-ui-lang="vi" title="Tiếng Việt">VI</button>
    `;
    topbar.insertBefore(wrap, topbar.firstChild);

    wrap.querySelectorAll("button[data-ui-lang]").forEach((btn) => {
      btn.addEventListener("click", () => setLang(btn.dataset.uiLang));
    });
    updateLangSwitcher(getLang());
  }

  function applyUiLangPanels(lang) {
    document
      .querySelectorAll(".docs-lang-panel, .ui-lang-panel")
      .forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.lang === lang);
      });
    document
      .querySelectorAll(".docs-lang-switch button[data-lang]")
      .forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.lang === lang);
      });
  }

  function applyDocumentTitle(lang) {
    const path = getPagePath();
    const titleKey = {
      "/": "meta.titleHome",
      "/about": "meta.titleAbout",
      "/contact": "meta.titleContact",
      "/auth": "meta.titleAuth",
      "/dashboard": "meta.titleDashboard",
      "/history": "meta.titleHistory",
      "/profile": "meta.titleProfile",
      "/support": "meta.titleSupport",
      "/terms": "meta.titleTerms",
      "/privacy": "meta.titlePrivacy",
      "/ai-terms": "meta.titleAiTerms",
      "/payment-policy": "meta.titlePaymentPolicy",
      "/data-deletion": "meta.titleDataDeletion",
      "/installation": "meta.titleInstallation",
      "/user-guide": "meta.titleUserGuide",
      "/admin": "meta.titleAdmin",
    }[path];
    if (titleKey && t(titleKey, lang)) {
      document.title = t(titleKey, lang);
    }
  }

  function updateLangSwitcher(lang) {
    document
      .querySelectorAll(".nav-lang-switch button[data-ui-lang]")
      .forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.uiLang === lang);
      });
  }

  function injectLangSwitcher() {
    document.querySelectorAll(".nav-links").forEach((navLinks) => {
      if (navLinks.querySelector(".nav-lang-switch")) return;

      const wrap = document.createElement("div");
      wrap.className = "nav-lang-switch";
      wrap.setAttribute("role", "group");
      wrap.setAttribute("aria-label", "Language");
      wrap.innerHTML = `
        <button type="button" data-ui-lang="en" title="English">EN</button>
        <button type="button" data-ui-lang="vi" title="Tiếng Việt">VI</button>
      `;

      const anchor = navLinks.querySelector(
        ".btn-login, .btn-register, .nav-user, .nav-bell",
      );
      if (anchor) {
        navLinks.insertBefore(wrap, anchor);
      } else {
        navLinks.appendChild(wrap);
      }

      wrap.querySelectorAll("button[data-ui-lang]").forEach((btn) => {
        btn.addEventListener("click", () => setLang(btn.dataset.uiLang));
      });
    });
  }

  function applySiteLanguage(lang) {
    const active = lang === "vi" ? "vi" : "en";
    document.documentElement.lang = active;
    cacheLegalArticleVi();
    cacheFullPageVi();
    applyLegalArticleLanguage(active);
    const skipPageBindings = applyFullPageLanguage(active);
    applyLegalHero(active);
    applyDataI18n(active);
    if (!skipPageBindings) {
      applyPageBindings(active);
    }
    applyNavLinks(active);
    applyFooter(active);
    applyLegalNav(active);
    applyDocsNav(active);
    applyBell(active);
    applyUserMenu(active);
    applyDashboardGreeting(active);
    applyAdminPage(active);
    applyUiLangPanels(active);
    applyDocumentTitle(active);
    updateLangSwitcher(active);
  }

  window.SiteI18n = {
    getLang,
    setLang,
    t,
    applySiteLanguage,
    injectLangSwitcher,
    previewLegalEnFromVi,
    invalidateLegalPagesEnCache,
    invalidateManagedContentCaches,
    updateManagedContentCache,
    isPageEditMode,
    hasLegalArticleBindings(slug) {
      const path = `/${String(slug || "").replace(/^\//, "")}`;
      return hasArticleBindings(path);
    },
  };
  window.t = t;

  function boot() {
    injectLangSwitcher();
    const path = getPagePath();
    if (ADMIN_MANAGED_FULL_PAGE_SLUGS[path]) {
      cacheFullPageVi();
      applySiteLanguage(getLang());
      loadLegalPagesEn().finally(() => applySiteLanguage(getLang()));
      return;
    }
    if (ADMIN_MANAGED_LEGAL_PATHS.has(path)) {
      cacheLegalArticleVi();
      applySiteLanguage(getLang());
      loadLegalPagesEn().finally(() => applySiteLanguage(getLang()));
      return;
    }
    applySiteLanguage(getLang());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.addEventListener("siteLanguageChanged", () => {
    const path = getPagePath();
    if (
      (ADMIN_MANAGED_LEGAL_PATHS.has(path) ||
        ADMIN_MANAGED_FULL_PAGE_SLUGS[path]) &&
      !legalPagesEnCache
    ) {
      loadLegalPagesEn().finally(() => applySiteLanguage(getLang()));
      return;
    }
    applySiteLanguage(getLang());
  });

  window.addEventListener("authUiReady", () => {
    applySiteLanguage(getLang());
  });
})();
