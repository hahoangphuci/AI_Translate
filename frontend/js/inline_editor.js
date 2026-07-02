/* Edit page content directly on live pages (?edit=1). Language follows SiteI18n. */
(function () {
  "use strict";

  const API = "";

  const PAGE_MAP = {
    "/": { slug: "home", kind: "main", selector: "#page-main" },
    "/home": { slug: "home", kind: "main", selector: "#page-main" },
    "/contact": { slug: "contact", kind: "main", selector: "#page-main" },
    "/privacy": {
      slug: "privacy",
      kind: "legal",
      selector: "article.legal-content",
    },
    "/terms": {
      slug: "terms",
      kind: "legal",
      selector: "article.legal-content",
    },
    "/ai-terms": {
      slug: "ai-terms",
      kind: "legal",
      selector: "article.legal-content",
    },
    "/payment-policy": {
      slug: "payment-policy",
      kind: "legal",
      selector: "article.legal-content",
    },
    "/data-deletion": {
      slug: "data-deletion",
      kind: "legal",
      selector: "article.legal-content",
    },
    "/support": {
      slug: "support",
      kind: "legal",
      selector: "article.legal-content",
    },
  };

  const TEXT_EDITABLE_SELECTOR =
    "h1,h2,h3,h4,h5,h6,p,li,td,th,label,summary,figcaption," +
    ".hero-subtitle,.hero-title,.stat-label,.section-header p,.contact-subtitle," +
    ".pricing-features li,.feature-card p,.how-step p,.cta-content p";

  const TEXT_EDITABLE_SKIP =
    "button, input, textarea, select, option, form, .quick-form, .quick-translate, .newsletter-form";

  let activeConfig = null;
  let activeEl = null;
  let dirty = false;
  let loadingLang = false;

  function getPagePath() {
    return window.location.pathname.replace(/\/$/, "") || "/";
  }

  function isEditMode() {
    return new URLSearchParams(window.location.search).get("edit") === "1";
  }

  function getContentLang() {
    return window.SiteI18n?.getLang?.() === "vi" ? "vi" : "en";
  }

  function msg(key, fallback) {
    if (typeof window.t === "function") {
      const v = window.t(key);
      if (v && v !== key) return v;
    }
    return fallback;
  }

  function authHeaders() {
    return {
      Authorization: "Bearer " + (localStorage.getItem("token") || ""),
      "Content-Type": "application/json",
    };
  }

  async function checkAdmin() {
    const token = localStorage.getItem("token");
    if (!token) return false;
    try {
      const res = await fetch(API + "/api/auth/profile", {
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) return false;
      const profile = await res.json();
      return profile.role === "admin";
    } catch {
      return false;
    }
  }

  function showToast(text, type) {
    document.querySelectorAll(".cms-toast").forEach((n) => n.remove());
    const el = document.createElement("div");
    el.className = "cms-toast" + (type === "error" ? " error" : "");
    el.textContent = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  function stripCmsEditHtml(html) {
    if (!html) return html;
    return String(html)
      .replace(/\scontenteditable="(?:true|false)"/gi, "")
      .replace(/\sspellcheck="(?:true|false)"/gi, "")
      .replace(/\sclass="([^"]*)"/g, function (_match, classNames) {
        const cleaned = String(classNames || "")
          .split(/\s+/)
          .filter(function (token) {
            return (
              token && token !== "cms-editing" && token !== "cms-text-editable"
            );
          })
          .join(" ");
        return cleaned ? ' class="' + cleaned + '"' : "";
      });
  }

  function stripPersistedEditArtifacts() {
    if (isEditMode()) return;
    document.querySelectorAll("[contenteditable]").forEach(function (el) {
      el.removeAttribute("contenteditable");
      el.removeAttribute("spellcheck");
      el.classList.remove("cms-text-editable", "cms-editing");
    });
    document
      .querySelectorAll("#page-main.cms-editing, article.cms-editing")
      .forEach(function (el) {
        el.classList.remove("cms-editing");
      });
  }

  window.stripCmsEditHtml = stripCmsEditHtml;

  function getEditableElement(cfg) {
    return document.querySelector(cfg.selector);
  }

  function readContent(cfg, el) {
    if (!el) return "";
    if (cfg.kind === "main") return stripCmsEditHtml(el.outerHTML.trim());
    return stripCmsEditHtml(el.innerHTML.trim());
  }

  function applyContent(cfg, el, html) {
    if (!el || !html) return el;
    const trimmed = html.trim();
    if (cfg.kind === "main") {
      if (
        trimmed.startsWith('<div id="page-main"') ||
        trimmed.startsWith("<div id='page-main'")
      ) {
        el.outerHTML = trimmed;
        return document.querySelector(cfg.selector);
      }
      el.innerHTML = trimmed;
      return el;
    }
    el.innerHTML = trimmed;
    return el;
  }

  function clearTextEditing(container) {
    if (!container) return;
    container.querySelectorAll(".cms-text-editable").forEach((node) => {
      node.removeAttribute("contenteditable");
      node.classList.remove("cms-text-editable");
    });
  }

  function enableTextEditing(container) {
    if (!container) return;
    clearTextEditing(container);
    container.querySelectorAll(TEXT_EDITABLE_SELECTOR).forEach((el) => {
      if (el.closest(TEXT_EDITABLE_SKIP)) return;
      if (el.querySelector("input, textarea, select, button, form")) return;
      el.contentEditable = "true";
      el.classList.add("cms-text-editable");
      el.spellcheck = true;
    });
  }

  function attachEditing(cfg, el) {
    if (!el) return el;
    if (cfg.kind === "main") {
      enableTextEditing(el);
      el.classList.add("cms-editing");
    } else {
      el.setAttribute("contenteditable", "true");
      el.classList.add("cms-editing");
    }
    el.addEventListener("input", () => {
      dirty = true;
    });
    return el;
  }

  async function fetchPageContent(slug, lang) {
    const res = await fetch(
      API +
        "/api/admin/site-config/pages/" +
        encodeURIComponent(slug) +
        "?lang=" +
        encodeURIComponent(lang),
      { headers: authHeaders() },
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.message || "Không tải được nội dung");
    return (data.content || "").trim();
  }

  async function savePageContent(slug, lang, content) {
    const res = await fetch(
      API + "/api/admin/site-config/pages/" + encodeURIComponent(slug),
      {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({ content, lang }),
      },
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.message || "Lưu thất bại");
    return data;
  }

  function syncCachesAfterSave(cfg, lang, content) {
    if (window.SiteI18n?.invalidateLegalPagesEnCache) {
      window.SiteI18n.invalidateLegalPagesEnCache();
    }
    if (lang === "vi" && window.SiteI18n?.updateManagedContentCache) {
      window.SiteI18n.updateManagedContentCache(getPagePath(), "vi", content);
    }
  }

  function execCmd(cmd, value) {
    if (cfgIsMain()) {
      let target = document.activeElement;
      if (!target?.classList?.contains("cms-text-editable")) {
        target = activeEl?.querySelector(".cms-text-editable");
        target?.focus();
      }
    } else {
      activeEl?.focus();
    }
    if (cmd === "formatBlock" && value) {
      document.execCommand(cmd, false, "<" + value + ">");
    } else {
      document.execCommand(cmd, false, value || null);
    }
    dirty = true;
  }

  function cfgIsMain() {
    return activeConfig?.kind === "main";
  }

  async function insertLink() {
    const url = window.prompt(
      msg("cms.promptLink", "Nhập URL (vd: /contact hoặc https://...)"),
    );
    if (!url) return;
    execCmd("createLink", url);
  }

  function removeEditorBar() {
    document.getElementById("cmsEditorBar")?.remove();
    document.body.classList.remove("cms-editing-active");
  }

  function buildEditorBar() {
    removeEditorBar();
    const bar = document.createElement("div");
    bar.id = "cmsEditorBar";
    bar.className = "cms-editor-bar";
    bar.innerHTML =
      '<span class="cms-editor-label">' +
      msg("cms.editing", "Đang sửa") +
      '</span><span class="cms-editor-lang" id="cmsEditorLang"></span>' +
      '<button type="button" title="H2" data-cmd="formatBlock" data-val="h2"><b>H2</b></button>' +
      '<button type="button" title="H3" data-cmd="formatBlock" data-val="h3"><b>H3</b></button>' +
      '<button type="button" title="Bold" data-cmd="bold"><i class="fas fa-bold"></i></button>' +
      '<button type="button" title="Italic" data-cmd="italic"><i class="fas fa-italic"></i></button>' +
      '<button type="button" title="List" data-cmd="insertUnorderedList"><i class="fas fa-list-ul"></i></button>' +
      '<button type="button" title="Link" data-action="link"><i class="fas fa-link"></i></button>' +
      '<button type="button" class="cms-btn-primary" data-action="save"><i class="fas fa-save"></i> ' +
      msg("cms.save", "Lưu") +
      "</button>" +
      '<a class="cms-btn cms-btn-danger" href="' +
      escAttr(window.location.pathname) +
      '"><i class="fas fa-times"></i> ' +
      msg("cms.exit", "Thoát") +
      "</a>";

    bar.querySelectorAll("button[data-cmd]").forEach((btn) => {
      btn.addEventListener("click", () => {
        execCmd(btn.dataset.cmd, btn.dataset.val);
      });
    });
    bar
      .querySelector('[data-action="link"]')
      ?.addEventListener("click", insertLink);
    bar
      .querySelector('[data-action="save"]')
      ?.addEventListener("click", () => saveCurrent());
    document.body.appendChild(bar);
    document.body.classList.add("cms-editing-active");
    updateLangBadge();
  }

  function escAttr(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  function updateLangBadge() {
    const badge = document.getElementById("cmsEditorLang");
    if (!badge) return;
    badge.textContent = getContentLang() === "vi" ? "VI" : "EN";
  }

  async function loadIntoEditor(cfg, lang) {
    loadingLang = true;
    try {
      let content = await fetchPageContent(cfg.slug, lang);
      if (!content && lang === "en") {
        content = await fetchPageContent(cfg.slug, "vi");
      }
      activeEl = getEditableElement(cfg);
      if (!activeEl) {
        showToast(
          msg("cms.noTarget", "Không tìm thấy vùng nội dung trên trang"),
          "error",
        );
        return;
      }
      clearTextEditing(activeEl);
      activeEl = applyContent(cfg, activeEl, content) || activeEl;
      activeEl = attachEditing(cfg, activeEl);
      dirty = false;
    } catch (e) {
      showToast(
        e.message || msg("cms.loadError", "Không tải nội dung"),
        "error",
      );
    } finally {
      loadingLang = false;
    }
  }

  async function saveCurrent() {
    if (!activeConfig || !activeEl) return;
    const lang = getContentLang();
    const content = readContent(activeConfig, getEditableElement(activeConfig));
    if (!content) {
      showToast(msg("cms.empty", "Nội dung không được để trống"), "error");
      return;
    }
    try {
      const data = await savePageContent(activeConfig.slug, lang, content);
      dirty = false;
      syncCachesAfterSave(activeConfig, lang, content);
      showToast(data.message || msg("cms.saved", "Đã lưu"));
      await loadIntoEditor(activeConfig, lang);
    } catch (e) {
      showToast(e.message || msg("cms.saveError", "Lưu thất bại"), "error");
    }
  }

  async function onSiteLanguageChanged() {
    if (!activeConfig || !isEditMode() || loadingLang) return;
    if (dirty) {
      const ok = window.confirm(
        msg(
          "cms.langSwitchConfirm",
          "Bạn có thay đổi chưa lưu. Chuyển ngôn ngữ sẽ bỏ các thay đổi này. Tiếp tục?",
        ),
      );
      if (!ok) return;
    }
    await loadIntoEditor(activeConfig, getContentLang());
    updateLangBadge();
  }

  async function startEditMode(cfg) {
    window.__CMS_EDIT_MODE = true;
    activeConfig = cfg;
    buildEditorBar();
    await loadIntoEditor(cfg, getContentLang());
    window.addEventListener("siteLanguageChanged", onSiteLanguageChanged);
  }

  async function boot() {
    stripPersistedEditArtifacts();

    const path = getPagePath();
    const cfg = PAGE_MAP[path];
    if (!cfg || !isEditMode()) return;

    const isAdmin = await checkAdmin();
    if (!isAdmin) return;

    await startEditMode(cfg);
  }

  if (document.readyState === "complete") {
    boot();
  } else {
    window.addEventListener("load", boot);
  }
})();
