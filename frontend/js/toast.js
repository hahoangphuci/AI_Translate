(function () {
  if (window.__appUiInit) return;
  window.__appUiInit = true;

  var hideTimer = null;

  var style = document.createElement("style");
  style.textContent =
    ".app-toast{position:fixed;top:24px;right:24px;min-width:280px;max-width:min(420px,calc(100vw - 32px));display:flex;align-items:flex-start;gap:12px;padding:16px 18px;border-radius:14px;background:#0e1a2b;border:1px solid rgba(255,255,255,.12);box-shadow:0 12px 40px rgba(0,0,0,.45);color:rgba(255,255,255,.92);font-size:.92rem;line-height:1.5;z-index:10050;transform:translateX(calc(100% + 32px));opacity:0;transition:transform .35s cubic-bezier(.4,0,.2,1),opacity .35s ease}" +
    ".app-toast.show{transform:translateX(0);opacity:1}" +
    ".app-toast i{margin-top:2px;font-size:1.1rem;flex-shrink:0}" +
    ".app-toast-msg{flex:1;padding-right:4px}" +
    ".app-toast.success{border-color:rgba(0,255,209,.35);background:linear-gradient(135deg,rgba(0,255,209,.08),#0e1a2b 55%)}" +
    ".app-toast.success i{color:#00ffd1}" +
    ".app-toast.error{border-color:rgba(255,100,100,.35);background:linear-gradient(135deg,rgba(255,80,80,.1),#0e1a2b 55%)}" +
    ".app-toast.error i{color:#ff8a8a}" +
    ".app-toast.info{border-color:rgba(0,168,255,.35);background:linear-gradient(135deg,rgba(0,168,255,.08),#0e1a2b 55%)}" +
    ".app-toast.info i{color:#00a8ff}" +
    ".app-toast.warning{border-color:rgba(255,193,7,.35);background:linear-gradient(135deg,rgba(255,193,7,.08),#0e1a2b 55%)}" +
    ".app-toast.warning i{color:#ffc107}" +
    ".app-toast-close{margin-left:auto;background:none;border:none;color:rgba(255,255,255,.45);font-size:1.25rem;cursor:pointer;line-height:1;padding:0 0 0 8px;flex-shrink:0}" +
    ".app-toast-close:hover{color:#fff}" +
    ".app-dialog-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.65);display:flex;align-items:center;justify-content:center;z-index:10060;padding:20px;opacity:0;transition:opacity .2s ease}" +
    ".app-dialog-backdrop.show{opacity:1}" +
    ".app-dialog{background:#0e1a2b;border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:24px;max-width:440px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.5);transform:translateY(12px) scale(.98);transition:transform .25s ease}" +
    ".app-dialog-backdrop.show .app-dialog{transform:translateY(0) scale(1)}" +
    ".app-dialog-title{margin:0 0 10px;color:#fff;font-size:1.05rem;display:flex;align-items:center;gap:10px}" +
    ".app-dialog-title.danger{color:#ffb4b4}" +
    ".app-dialog-title i{font-size:1rem}" +
    ".app-dialog-message{margin:0 0 18px;color:rgba(255,255,255,.72);line-height:1.65;font-size:.92rem}" +
    ".app-dialog-input{width:100%;padding:11px 12px;border-radius:10px;border:1px solid rgba(255,255,255,.15);background:rgba(0,0,0,.3);color:#fff;font-size:.92rem;margin-bottom:18px;box-sizing:border-box}" +
    ".app-dialog-input:focus{outline:none;border-color:rgba(0,255,209,.45)}" +
    ".app-dialog-actions{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}" +
    ".app-dialog-btn{border:none;border-radius:10px;padding:10px 18px;font-size:.88rem;font-weight:600;cursor:pointer;transition:opacity .15s ease}" +
    ".app-dialog-btn:hover{opacity:.88}" +
    ".app-dialog-btn-cancel{background:rgba(255,255,255,.08);color:rgba(255,255,255,.85)}" +
    ".app-dialog-btn-confirm{background:linear-gradient(135deg,#007a63,#005fa3);color:#fff}" +
    ".app-dialog-btn-confirm.danger{background:linear-gradient(135deg,#8b1a1a,#5c1010);color:#ffb4b4}" +
    "@media (max-width:480px){.app-toast{top:auto;bottom:24px;right:16px;left:16px;max-width:none;transform:translateY(calc(100% + 32px))}.app-toast.show{transform:translateY(0)}}";
  document.head.appendChild(style);

  var toastIcons = {
    success: "fa-check-circle",
    error: "fa-exclamation-circle",
    info: "fa-info-circle",
    warning: "fa-exclamation-triangle",
  };

  window.showToast = function (message, type, options) {
    type = type || "success";
    options = options || {};
    var duration = options.duration != null ? options.duration : 3500;
    var onClose = options.onClose;

    document.querySelectorAll(".app-toast").forEach(function (el) {
      el.remove();
    });
    if (hideTimer) clearTimeout(hideTimer);

    var toast = document.createElement("div");
    toast.className = "app-toast " + type;
    toast.innerHTML =
      '<i class="fas ' +
      (toastIcons[type] || toastIcons.info) +
      '"></i>' +
      '<span class="app-toast-msg"></span>' +
      '<button type="button" class="app-toast-close" aria-label="Đóng">&times;</button>';
    toast.querySelector(".app-toast-msg").textContent = message;
    document.body.appendChild(toast);

    var closed = false;
    function hide() {
      if (closed) return;
      closed = true;
      toast.classList.remove("show");
      setTimeout(function () {
        toast.remove();
        if (typeof onClose === "function") onClose();
      }, 300);
    }

    toast.querySelector(".app-toast-close").addEventListener("click", hide);
    requestAnimationFrame(function () {
      toast.classList.add("show");
    });
    hideTimer = setTimeout(hide, duration);
  };

  function mountDialog(html) {
    var backdrop = document.createElement("div");
    backdrop.className = "app-dialog-backdrop";
    backdrop.innerHTML = html;
    document.body.appendChild(backdrop);
    requestAnimationFrame(function () {
      backdrop.classList.add("show");
    });
    return backdrop;
  }

  function closeDialog(backdrop, result, resolve) {
    backdrop.classList.remove("show");
    setTimeout(function () {
      backdrop.remove();
      resolve(result);
    }, 200);
  }

  window.showConfirm = function (options) {
    options = options || {};
    var title = options.title || "Xác nhận";
    var message = options.message || "";
    var confirmText = options.confirmText || "Xác nhận";
    var cancelText = options.cancelText || "Huỷ";
    var danger = options.danger === true || options.type === "danger";
    var icon = danger ? "fa-exclamation-triangle" : "fa-question-circle";

    return new Promise(function (resolve) {
      var backdrop = mountDialog(
        '<div class="app-dialog" role="dialog" aria-modal="true">' +
          '<h3 class="app-dialog-title' +
          (danger ? " danger" : "") +
          '"><i class="fas ' +
          icon +
          '"></i>' +
          escapeHtml(title) +
          "</h3>" +
          (message
            ? '<p class="app-dialog-message">' + escapeHtml(message) + "</p>"
            : "") +
          '<div class="app-dialog-actions">' +
          '<button type="button" class="app-dialog-btn app-dialog-btn-cancel">' +
          escapeHtml(cancelText) +
          "</button>" +
          '<button type="button" class="app-dialog-btn app-dialog-btn-confirm' +
          (danger ? " danger" : "") +
          '">' +
          escapeHtml(confirmText) +
          "</button>" +
          "</div></div>",
      );

      backdrop.querySelector(".app-dialog-btn-cancel").addEventListener("click", function () {
        closeDialog(backdrop, false, resolve);
      });
      backdrop.querySelector(".app-dialog-btn-confirm").addEventListener("click", function () {
        closeDialog(backdrop, true, resolve);
      });
      backdrop.addEventListener("click", function (e) {
        if (e.target === backdrop) closeDialog(backdrop, false, resolve);
      });
    });
  };

  window.showPrompt = function (options) {
    options = options || {};
    var title = options.title || "Nhập thông tin";
    var message = options.message || "";
    var placeholder = options.placeholder || "";
    var defaultValue = options.defaultValue || "";
    var confirmText = options.confirmText || "OK";
    var cancelText = options.cancelText || "Huỷ";

    return new Promise(function (resolve) {
      var backdrop = mountDialog(
        '<div class="app-dialog" role="dialog" aria-modal="true">' +
          '<h3 class="app-dialog-title"><i class="fas fa-link"></i>' +
          escapeHtml(title) +
          "</h3>" +
          (message
            ? '<p class="app-dialog-message">' + escapeHtml(message) + "</p>"
            : "") +
          '<input type="text" class="app-dialog-input" placeholder="' +
          escapeHtml(placeholder) +
          '" value="' +
          escapeHtml(defaultValue) +
          '" />' +
          '<div class="app-dialog-actions">' +
          '<button type="button" class="app-dialog-btn app-dialog-btn-cancel">' +
          escapeHtml(cancelText) +
          "</button>" +
          '<button type="button" class="app-dialog-btn app-dialog-btn-confirm">' +
          escapeHtml(confirmText) +
          "</button>" +
          "</div></div>",
      );

      var input = backdrop.querySelector(".app-dialog-input");
      input.focus();
      input.select();

      function submit() {
        var value = (input.value || "").trim();
        closeDialog(backdrop, value || null, resolve);
      }

      backdrop.querySelector(".app-dialog-btn-cancel").addEventListener("click", function () {
        closeDialog(backdrop, null, resolve);
      });
      backdrop.querySelector(".app-dialog-btn-confirm").addEventListener("click", submit);
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          submit();
        }
        if (e.key === "Escape") closeDialog(backdrop, null, resolve);
      });
      backdrop.addEventListener("click", function (e) {
        if (e.target === backdrop) closeDialog(backdrop, null, resolve);
      });
    });
  };

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
})();
