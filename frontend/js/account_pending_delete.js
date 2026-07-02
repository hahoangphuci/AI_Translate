(function () {
  function authHeaders() {
    const token = localStorage.getItem("token");
    return {
      "Content-Type": "application/json",
      Authorization: token ? `Bearer ${token}` : "",
    };
  }

  function fmtScheduled(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("vi-VN", {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch (e) {
      return iso;
    }
  }

  function showMsg(el, text, type) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "msg" + (type ? " " + type : "");
  }

  function redirectIfNotPending(profile) {
    const status = (profile && profile.account_status) || "active";
    if (status === "deleted") {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/auth?error=account_deleted";
      return true;
    }
    if (status === "active") {
      window.location.href = "/dashboard";
      return true;
    }
    return false;
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      window.location.href = "/auth?returnUrl=/account-pending-delete";
      return;
    }

    const scheduledEl = document.getElementById("scheduledAt");
    const otpPanel = document.getElementById("otpPanel");
    const restoreMsg = document.getElementById("restoreMsg");
    const otpInput = document.getElementById("restoreOtp");

    let profile = null;
    try {
      const res = await fetch("/api/auth/profile", { headers: authHeaders() });
      if (!res.ok) {
        window.location.href = "/auth?returnUrl=/account-pending-delete";
        return;
      }
      profile = await res.json();
      localStorage.setItem("user", JSON.stringify(profile));
    } catch (e) {
      window.location.href = "/auth";
      return;
    }

    if (redirectIfNotPending(profile)) return;

    scheduledEl.textContent = fmtScheduled(profile.delete_scheduled_at);

    document.getElementById("btnLogout").addEventListener("click", () => {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/auth";
    });

    document.getElementById("btnRestore").addEventListener("click", async () => {
      showMsg(restoreMsg, "Đang gửi OTP...", "");
      try {
        const res = await fetch("/api/auth/account/restore/request", {
          method: "POST",
          headers: authHeaders(),
        });
        const data = await res.json();
        if (!res.ok) {
          showMsg(restoreMsg, data.message || data.error || "Lỗi gửi OTP", "error");
          return;
        }
        otpPanel.classList.add("show");
        otpInput.focus();
        showMsg(restoreMsg, data.message || "Đã gửi OTP.", "success");
      } catch (e) {
        showMsg(restoreMsg, "Lỗi kết nối.", "error");
      }
    });

    document.getElementById("btnConfirmRestore").addEventListener("click", async () => {
      const otp = (otpInput.value || "").trim();
      if (otp.length !== 6) {
        showMsg(restoreMsg, "Vui lòng nhập đủ 6 chữ số OTP.", "error");
        return;
      }
      showMsg(restoreMsg, "Đang xác nhận...", "");
      try {
        const res = await fetch("/api/auth/account/restore/confirm", {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({ otp }),
        });
        const data = await res.json();
        if (!res.ok) {
          showMsg(restoreMsg, data.message || data.error || "OTP không hợp lệ", "error");
          return;
        }
        if (data.user) localStorage.setItem("user", JSON.stringify(data.user));
        showMsg(restoreMsg, data.message || "Khôi phục thành công!", "success");
        setTimeout(() => {
          window.location.href = "/dashboard";
        }, 1200);
      } catch (e) {
        showMsg(restoreMsg, "Lỗi kết nối.", "error");
      }
    });
  });
})();
