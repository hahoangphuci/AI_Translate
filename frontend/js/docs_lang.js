(function () {
  function initDocsLangSwitch() {
    const switcher = document.querySelector(".docs-lang-switch");
    if (!switcher) return;

    switcher.querySelectorAll("button[data-lang]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const lang = btn.dataset.lang === "vi" ? "vi" : "en";
        if (window.SiteI18n) {
          window.SiteI18n.setLang(lang);
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDocsLangSwitch);
  } else {
    initDocsLangSwitch();
  }
})();
