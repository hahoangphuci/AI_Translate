/* ── Admin Panel JS ─────────────────────────────────────────── */
"use strict";

const API = "";

function adminT(key, vars) {
  let text = typeof window.t === "function" ? window.t(key) : key;
  if (vars && text) {
    Object.entries(vars).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, "g"), v);
    });
  }
  return text || key;
}

function emptyRow(cols) {
  return `<tr><td colspan="${cols}" style="text-align:center;color:var(--muted);padding:30px">${esc(adminT("admin.noData"))}</td></tr>`;
}

function statusLabel(status) {
  const s = String(status || "").toLowerCase();
  const key = `admin.status.${s}`;
  const tr = adminT(key);
  return tr === key ? status : tr;
}

// ─── Auth guard ──────────────────────────────────────────────
async function checkAdminAccess() {
  const token = localStorage.getItem("token");
  if (!token) return false;
  try {
    const res = await fetch(`${API}/api/auth/profile`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return false;
    const profile = await res.json();
    if (profile.role !== "admin") return false;
    document.getElementById("adminName").textContent =
      profile.name || profile.email || "Admin";
    return true;
  } catch {
    return false;
  }
}

// ─── Helpers ─────────────────────────────────────────────────
function authHeaders() {
  return {
    Authorization: `Bearer ${localStorage.getItem("token")}`,
    "Content-Type": "application/json",
  };
}

function fmt(dt) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function esc(str) {
  return String(str ?? "").replace(
    /[&<>"']/g,
    (m) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        m
      ],
  );
}

function badge(text, cls) {
  const display = statusLabel(text);
  return `<span class="badge badge-${esc(cls)}">${esc(display)}</span>`;
}

function planBadge(plan) {
  const p = (plan || "free").toLowerCase();
  return badge(p.toUpperCase(), p);
}

function roleBadge(role) {
  const r = (role || "user").toLowerCase();
  const label =
    r === "admin" ? adminT("admin.role.admin") : adminT("admin.role.user");
  return badge(label, r);
}

function fmtVnd(amount) {
  return Number(amount || 0).toLocaleString("vi-VN") + " ₫";
}

function closeModal(id) {
  document.getElementById(id).style.display = "none";
}

function openModal(id) {
  document.getElementById(id).style.display = "flex";
}

function buildPagination(containerId, currentPage, totalPages, loadFn) {
  const el = document.getElementById(containerId);
  if (totalPages <= 1) {
    el.innerHTML = "";
    return;
  }
  let html = "";
  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, currentPage + 2);
  if (start > 1)
    html += `<button class="page-btn" onclick="${loadFn}(1)">1</button>`;
  if (start > 2)
    html += `<span style="color:var(--muted);padding:0 4px">…</span>`;
  for (let i = start; i <= end; i++) {
    html += `<button class="page-btn${i === currentPage ? " active" : ""}" onclick="${loadFn}(${i})">${i}</button>`;
  }
  if (end < totalPages - 1)
    html += `<span style="color:var(--muted);padding:0 4px">…</span>`;
  if (end < totalPages)
    html += `<button class="page-btn" onclick="${loadFn}(${totalPages})">${totalPages}</button>`;
  el.innerHTML = html;
}

// ─── Stats ───────────────────────────────────────────────────
let _adminCharts = {};

function _chartColors() {
  return {
    text: "#a8b8c8",
    grid: "rgba(255,255,255,0.08)",
    teal: "#00ffd1",
    blue: "#4dabf7",
    gold: "#ffd43b",
    purple: "#b197fc",
    pie: ["#00ffd1", "#4dabf7", "#ffd43b", "#b197fc"],
  };
}

function _destroyAdminCharts() {
  Object.values(_adminCharts).forEach((c) => {
    try {
      c.destroy();
    } catch (e) {
      /* ignore */
    }
  });
  _adminCharts = {};
}

function renderAdminCharts(charts) {
  if (typeof Chart === "undefined" || !charts) return;
  _destroyAdminCharts();

  const c = _chartColors();
  const labels = charts.labels || [];
  const commonScale = {
    ticks: { color: c.text },
    grid: { color: c.grid },
  };

  const ctxT = document.getElementById("chartTranslations");
  if (ctxT) {
    _adminCharts.translations = new Chart(ctxT, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: adminT("admin.chart.labelTranslations"),
            data: charts.translations_per_day || [],
            borderColor: c.teal,
            backgroundColor: "rgba(0,255,209,0.15)",
            fill: true,
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: c.text } } },
        scales: { x: commonScale, y: { ...commonScale, beginAtZero: true } },
      },
    });
  }

  const ctxU = document.getElementById("chartUsers");
  if (ctxU) {
    _adminCharts.users = new Chart(ctxU, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: adminT("admin.chart.labelNewUsers"),
            data: charts.users_per_day || [],
            backgroundColor: "rgba(77,171,247,0.7)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: commonScale, y: { ...commonScale, beginAtZero: true } },
      },
    });
  }

  const ctxR = document.getElementById("chartRevenue");
  if (ctxR) {
    _adminCharts.revenue = new Chart(ctxR, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: adminT("admin.chart.labelRevenue"),
            data: charts.revenue_per_day || [],
            backgroundColor: "rgba(255,212,59,0.75)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: commonScale, y: { ...commonScale, beginAtZero: true } },
      },
    });
  }

  const plans = charts.plan_distribution || {};
  const ctxP = document.getElementById("chartPlans");
  if (ctxP) {
    _adminCharts.plans = new Chart(ctxP, {
      type: "doughnut",
      data: {
        labels: ["Free", "Pro", "ProMax"],
        datasets: [
          {
            data: [plans.free || 0, plans.pro || 0, plans.promax || 0],
            backgroundColor: c.pie,
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: c.text } },
        },
      },
    });
  }
}

async function loadStats() {
  try {
    const res = await fetch(`${API}/api/admin/stats`, {
      headers: authHeaders(),
    });
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById("stat-users").textContent = d.total_users ?? "—";
    document.getElementById("stat-translations").textContent =
      d.total_translations ?? "—";
    document.getElementById("stat-payments").textContent =
      d.total_payments ?? "—";
    document.getElementById("stat-revenue").textContent = fmtVnd(
      d.total_revenue_vnd ?? 0,
    );
    document.getElementById("stat-admins").textContent = d.admin_count ?? "—";
    document.getElementById("stat-members").textContent =
      d.member_count ?? d.role_distribution?.member ?? "—";
    document.getElementById("stat-free").textContent =
      d.plan_distribution?.free ?? "—";
    document.getElementById("stat-pro").textContent =
      d.plan_distribution?.pro ?? "—";
    document.getElementById("stat-promax").textContent =
      d.plan_distribution?.promax ?? "—";
    renderAdminCharts(
      d.charts || {
        labels: [],
        translations_per_day: [],
        users_per_day: [],
        revenue_per_day: [],
        plan_distribution: d.plan_distribution,
      },
    );
  } catch (e) {
    console.error(e);
  }
}

// ─── Users ───────────────────────────────────────────────────
let _usersPage = 1;
async function loadUsers(page = 1) {
  _usersPage = page;
  const q = (document.getElementById("userSearch")?.value || "").trim();
  const url = `${API}/api/admin/users?page=${page}&per_page=15${q ? "&q=" + encodeURIComponent(q) : ""}`;
  try {
    const res = await fetch(url, { headers: authHeaders() });
    const d = await res.json();
    const tbody = document.getElementById("usersBody");
    tbody.innerHTML =
      (d.users || [])
        .map(
          (u) => `
      <tr>
        <td>${esc(u.id)}</td>
        <td>${esc(u.name || "—")}</td>
        <td>${esc(u.email)}</td>
        <td>${planBadge(u.plan)}</td>
        <td>${roleBadge(u.role)}</td>
        <td>${Number(u.token_balance || 0).toLocaleString()}</td>
        <td>${fmt(u.created_at)}</td>
        <td>
          <button class="btn-icon" title="${esc(adminT("admin.btn.view"))}" onclick="viewUser(${u.id})"><i class="fas fa-eye"></i></button>
          ${
            u.role !== "admin"
              ? `<button class="btn-icon" title="${esc(adminT("admin.btn.grantAdmin"))}" onclick="grantAdmin(${u.id})"><i class="fas fa-user-shield"></i></button>`
              : `<button class="btn-icon danger" title="${esc(adminT("admin.btn.revokeAdmin"))}" onclick="revokeAdmin(${u.id})"><i class="fas fa-user-minus"></i></button>`
          }
          <button class="btn-icon danger" title="${esc(adminT("admin.btn.delete"))}" onclick="deleteUser(${u.id}, '${esc(u.email)}')"><i class="fas fa-trash"></i></button>
        </td>
      </tr>`,
        )
        .join("") || emptyRow(8);
    buildPagination("usersPagination", page, d.pages || 1, "loadUsers");
  } catch (e) {
    console.error(e);
    showToast(adminT("admin.toast.loadUsersError"), "error");
  }
}

async function viewUser(id) {
  try {
    const res = await fetch(`${API}/api/admin/users/${id}`, {
      headers: authHeaders(),
    });
    const u = await res.json();
    document.getElementById("modalUserTitle").textContent = adminT(
      "admin.modal.userTitle",
      {
        id: u.id,
      },
    );
    document.getElementById("modalUserBody").innerHTML = `
      <div class="detail-row"><span class="detail-label">ID</span><span class="detail-value">${esc(u.id)}</span></div>
      <div class="detail-row"><span class="detail-label">Email</span><span class="detail-value">${esc(u.email)}</span></div>
      <div class="detail-row"><span class="detail-label">Tên</span><span class="detail-value">${esc(u.name || "—")}</span></div>
      <div class="detail-row"><span class="detail-label">Plan</span><span class="detail-value">${planBadge(u.plan)}</span></div>
      <div class="detail-row"><span class="detail-label">Role</span><span class="detail-value">${roleBadge(u.role)}</span></div>
      <div class="detail-row"><span class="detail-label">Tokens</span><span class="detail-value">${Number(u.token_balance || 0).toLocaleString()}</span></div>
      <div class="detail-row"><span class="detail-label">Google ID</span><span class="detail-value">${esc(u.google_id || adminT("admin.modal.noGoogle"))}</span></div>
      <div class="detail-row"><span class="detail-label">Ngày tạo</span><span class="detail-value">${fmt(u.created_at)}</span></div>
    `;
    document.getElementById("modalUserFooter").innerHTML = `
      <button class="btn-icon" onclick="closeModal('userModal')">${esc(adminT("admin.btn.close"))}</button>
      ${
        u.role !== "admin"
          ? `<button class="btn-accent" onclick="grantAdmin(${u.id}); closeModal('userModal')"><i class="fas fa-user-shield"></i> ${esc(adminT("admin.btn.grantAdmin"))}</button>`
          : `<button class="btn-icon danger" onclick="revokeAdmin(${u.id}); closeModal('userModal')"><i class="fas fa-user-minus"></i> ${esc(adminT("admin.btn.revokeAdmin"))}</button>`
      }
    `;
    openModal("userModal");
  } catch (e) {
    showToast(adminT("admin.toast.loadUserError"), "error");
  }
}

async function grantAdmin(id) {
  if (
    !(await showConfirm({
      title: adminT("admin.confirm.grantAdminTitle"),
      message: adminT("admin.confirm.grantAdminMsg"),
      confirmText: adminT("admin.confirm.grantAdminBtn"),
    }))
  )
    return;
  const res = await fetch(`${API}/api/admin/users/${id}/grant-admin`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (res.ok) {
    showToast(adminT("admin.toast.grantedAdmin"));
    loadUsers(_usersPage);
  } else showToast(adminT("admin.toast.error"), "error");
}

async function revokeAdmin(id) {
  if (
    !(await showConfirm({
      title: adminT("admin.confirm.revokeAdminTitle"),
      message: adminT("admin.confirm.revokeAdminMsg"),
      confirmText: adminT("admin.confirm.revokeAdminBtn"),
      danger: true,
    }))
  )
    return;
  const res = await fetch(`${API}/api/admin/users/${id}/revoke-admin`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (res.ok) {
    showToast(adminT("admin.toast.revokedAdmin"));
    loadUsers(_usersPage);
  } else showToast(adminT("admin.toast.error"), "error");
}

async function deleteUser(id, email) {
  if (
    !(await showConfirm({
      title: "Xóa người dùng",
      message: `Xóa người dùng "${email}"? Hành động này không thể hoàn tác.`,
      confirmText: "Xóa",
      danger: true,
    }))
  )
    return;
  const res = await fetch(`${API}/api/admin/users/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (res.ok) {
    showToast("Đã xóa người dùng");
    loadUsers(_usersPage);
  } else {
    const d = await res.json();
    showToast(d.error || "Lỗi xóa", "error");
  }
}

// ─── Translations ─────────────────────────────────────────────
let _transPage = 1;
async function loadTranslations(page = 1) {
  _transPage = page;
  try {
    const res = await fetch(
      `${API}/api/admin/translations?page=${page}&per_page=15`,
      { headers: authHeaders() },
    );
    const d = await res.json();
    const tbody = document.getElementById("translationsBody");
    tbody.innerHTML =
      (d.translations || [])
        .map(
          (t) => `
      <tr>
        <td>${esc(t.id)}</td>
        <td>${esc(t.user_id)}</td>
        <td>${esc(t.source_lang || "—")}</td>
        <td>${esc(t.target_lang || "—")}</td>
        <td title="${esc(t.original_text)}">${esc((t.original_text || "—").substring(0, 60))}…</td>
        <td>${fmt(t.created_at)}</td>
        <td>
          <button class="btn-icon danger" title="${esc(adminT("admin.btn.delete"))}" onclick="deleteTranslation(${t.id})"><i class="fas fa-trash"></i></button>
        </td>
      </tr>`,
        )
        .join("") || emptyRow(7);
    buildPagination(
      "translationsPagination",
      page,
      d.pages || 1,
      "loadTranslations",
    );
  } catch (e) {
    showToast(adminT("admin.toast.loadTransError"), "error");
  }
}

async function deleteTranslation(id) {
  if (
    !(await showConfirm({
      title: adminT("admin.confirm.deleteTransTitle"),
      message: adminT("admin.confirm.deleteTransMsg"),
      confirmText: adminT("admin.confirm.deleteBtn"),
      danger: true,
    }))
  )
    return;
  const res = await fetch(`${API}/api/admin/translations/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (res.ok) {
    showToast(adminT("admin.toast.deleted"));
    loadTranslations(_transPage);
  } else showToast(adminT("admin.toast.error"), "error");
}

// ─── Payments ─────────────────────────────────────────────────
let _payPage = 1;
async function loadPayments(page = 1) {
  _payPage = page;
  try {
    const res = await fetch(
      `${API}/api/admin/payments?page=${page}&per_page=15`,
      { headers: authHeaders() },
    );
    const d = await res.json();
    const tbody = document.getElementById("paymentsBody");
    tbody.innerHTML =
      (d.payments || [])
        .map((p) => {
          const status = p.status || "pending";
          return `<tr>
        <td>${esc(p.id)}</td>
        <td>${esc(p.user_id)}</td>
        <td>${planBadge(p.plan_type || p.plan || "")}</td>
        <td>${fmtVnd(p.amount)}</td>
        <td>${badge(status, status)}</td>
        <td>${esc(p.sepay_transaction_id || "—")}</td>
        <td>${fmt(p.created_at)}</td>
        <td>
          ${status !== "completed" ? `<button class="btn-icon" title="${esc(adminT("admin.btn.markComplete"))}" onclick="markPayment(${p.id},'completed')"><i class="fas fa-check"></i></button>` : ""}
          ${status !== "failed" ? `<button class="btn-icon danger" title="${esc(adminT("admin.btn.markFailed"))}" onclick="markPayment(${p.id},'failed')"><i class="fas fa-times"></i></button>` : ""}
        </td>
      </tr>`;
        })
        .join("") || emptyRow(8);
    buildPagination("paymentsPagination", page, d.pages || 1, "loadPayments");
  } catch (e) {
    showToast(adminT("admin.toast.loadPayError"), "error");
  }
}

async function markPayment(id, status) {
  const res = await fetch(`${API}/api/admin/payments/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
  if (res.ok) {
    showToast(adminT("admin.toast.payUpdated", { status }));
    loadPayments(_payPage);
  } else showToast(adminT("admin.toast.payUpdateError"), "error");
}

// ─── Contacts ─────────────────────────────────────────────────
let _contactPage = 1;
async function loadContacts(page = 1) {
  _contactPage = page;
  try {
    const res = await fetch(
      `${API}/api/admin/contacts?page=${page}&per_page=15`,
      { headers: authHeaders() },
    );
    const d = await res.json();
    const tbody = document.getElementById("contactsBody");
    tbody.innerHTML =
      (d.contacts || [])
        .map((c) => {
          const status = c.status || "unread";
          return `<tr>
        <td>${esc(c.id)}</td>
        <td>${esc((c.first_name || "") + " " + (c.last_name || ""))}</td>
        <td>${esc(c.email)}</td>
        <td>${esc(c.subject || "—")}</td>
        <td title="${esc(c.message)}">${esc((c.message || "").substring(0, 50))}…</td>
        <td>${badge(status, status)}</td>
        <td>${fmt(c.created_at)}</td>
        <td>
          <button class="btn-icon" title="${esc(adminT("admin.btn.view"))}" onclick="viewContact(${c.id})"><i class="fas fa-eye"></i></button>
          <button class="btn-icon danger" title="${esc(adminT("admin.btn.delete"))}" onclick="deleteContact(${c.id})"><i class="fas fa-trash"></i></button>
        </td>
      </tr>`;
        })
        .join("") || emptyRow(8);
    buildPagination("contactsPagination", page, d.pages || 1, "loadContacts");
  } catch (e) {
    showToast(adminT("admin.toast.loadContactError"), "error");
  }
}

async function viewContact(id) {
  try {
    const res = await fetch(`${API}/api/admin/contacts/${id}`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      // Fallback: fetch list and find by id
      const listRes = await fetch(
        `${API}/api/admin/contacts?page=1&per_page=200`,
        { headers: authHeaders() },
      );
      const d = await listRes.json();
      const found = (d.contacts || []).find((x) => x.id === id);
      if (!found) {
        showToast(adminT("admin.toast.notFound"), "error");
        return;
      }
      _renderContactModal(found);
    } else {
      const c = await res.json();
      _renderContactModal(c);
    }
  } catch (e) {
    showToast(adminT("admin.toast.error"), "error");
  }
}

function _renderContactModal(c) {
  document.getElementById("modalContactBody").innerHTML = `
    <div class="detail-row"><span class="detail-label">${esc(adminT("admin.modal.sender"))}</span><span class="detail-value">${esc((c.first_name || "") + " " + (c.last_name || ""))}</span></div>
    <div class="detail-row"><span class="detail-label">Email</span><span class="detail-value">${esc(c.email)}</span></div>
    <div class="detail-row"><span class="detail-label">Chủ đề</span><span class="detail-value">${esc(c.subject || "—")}</span></div>
    <div class="detail-row"><span class="detail-label">Trạng thái</span><span class="detail-value">${badge(c.status || "unread", c.status || "unread")}</span></div>
    <div class="detail-row"><span class="detail-label">Thời gian</span><span class="detail-value">${fmt(c.created_at)}</span></div>
    <div class="detail-row"><span class="detail-label">Nội dung</span><span class="detail-value" style="white-space:pre-wrap">${esc(c.message || "—")}</span></div>
    ${
      c.admin_reply
        ? `
    <div class="detail-row" style="margin-top:12px">
      <span class="detail-label" style="color:var(--accent)">${esc(adminT("admin.modal.replied"))}</span>
      <span class="detail-value" style="color:var(--accent);white-space:pre-wrap">${esc(c.admin_reply)}</span>
    </div>`
        : ""
    }
    <div style="margin-top:16px">
      <label style="color:var(--muted);font-size:0.8rem;font-weight:600;display:block;margin-bottom:6px">
        ${c.admin_reply ? esc(adminT("admin.modal.editReply")) : esc(adminT("admin.modal.replyLabel"))}
      </label>
      <textarea id="replyText" rows="5" placeholder="Nhập nội dung phản hồi…"
        style="width:100%;background:#0b1a24;border:1px solid var(--border);color:var(--text);
               padding:10px 14px;border-radius:var(--radius);font-size:0.9rem;resize:vertical;
               outline:none;font-family:inherit"
        onfocus="this.style.borderColor='var(--accent)'" onblur="this.style.borderColor='var(--border)'"
      >${esc(c.admin_reply || "")}</textarea>
    </div>
  `;
  document.getElementById("modalContactFooter").innerHTML = `
    <button class="btn-icon" onclick="closeModal('contactModal')">${esc(adminT("admin.btn.close"))}</button>
    <button class="btn-accent" onclick="sendReply(${c.id})">
      <i class="fas fa-paper-plane"></i> ${esc(adminT("admin.btn.sendReply"))}
    </button>
  `;
  openModal("contactModal");
  // Mark as read silently
  if (c.status === "unread") markContact(c.id, "read");
}

async function sendReply(id) {
  const text = (document.getElementById("replyText")?.value || "").trim();
  if (!text) {
    showToast(adminT("admin.toast.replyRequired"), "error");
    return;
  }

  const btn = document.querySelector("#modalContactFooter .btn-accent");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${esc(adminT("admin.btn.saving"))}`;
  }

  try {
    const res = await fetch(`${API}/api/admin/contacts/${id}/reply`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ reply: text }),
    });
    const d = await res.json();
    if (!res.ok) {
      showToast(d.error || "Lỗi gửi phản hồi", "error");
      return;
    }
    showToast(adminT("admin.toast.replySent"));
    closeModal("contactModal");
    loadContacts(_contactPage);
  } catch (e) {
    showToast(adminT("admin.toast.connectionError"), "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fas fa-paper-plane"></i> ${esc(adminT("admin.btn.sendReply"))}`;
    }
  }
}

async function markContact(id, status) {
  await fetch(`${API}/api/admin/contacts/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
  loadContacts(_contactPage);
}

async function deleteContact(id) {
  if (
    !(await showConfirm({
      title: "Xóa tin nhắn",
      message: "Xóa tin nhắn liên hệ này?",
      confirmText: "Xóa",
      danger: true,
    }))
  )
    return;
  const res = await fetch(`${API}/api/admin/contacts/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (res.ok) {
    showToast("Đã xóa");
    loadContacts(_contactPage);
  } else showToast("Lỗi", "error");
}

// ─── Newsletter ───────────────────────────────────────────────
let _newsPage = 1;
async function loadNewsletter(page = 1) {
  _newsPage = page;
  try {
    const res = await fetch(
      `${API}/api/admin/newsletter?page=${page}&per_page=20`,
      { headers: authHeaders() },
    );
    const d = await res.json();
    const tbody = document.getElementById("newsletterBody");
    tbody.innerHTML =
      (d.subscribers || [])
        .map(
          (s) => `
      <tr>
        <td>${esc(s.id)}</td>
        <td>${esc(s.email)}</td>
        <td>${badge(s.status || "active", s.status || "active")}</td>
        <td>${fmt(s.created_at)}</td>
      </tr>`,
        )
        .join("") || emptyRow(4);
    buildPagination(
      "newsletterPagination",
      page,
      d.pages || 1,
      "loadNewsletter",
    );
  } catch (e) {
    showToast(adminT("admin.toast.error"), "error");
  }
}

// ─── Audit ────────────────────────────────────────────────────
let _auditPage = 1;
async function loadAudit(page = 1) {
  _auditPage = page;
  try {
    const res = await fetch(
      `${API}/api/admin/audit-log?page=${page}&per_page=20`,
      { headers: authHeaders() },
    );
    const d = await res.json();
    const tbody = document.getElementById("auditBody");
    tbody.innerHTML =
      (d.logs || [])
        .map((l) => {
          const ACTION_LABELS = {
            grant_admin: "🛡️ Cấp admin",
            revoke_admin: "🔓 Thu hồi admin",
            update_user: "✏️ Sửa user",
            delete_user: "🗑️ Xóa user",
            reply_contact: "💬 Trả lời LH",
            delete_contact: "🗑️ Xóa LH",
            update_payment: "💳 Sửa TT",
            delete_translation: "🗑️ Xóa BD",
          };
          const label = ACTION_LABELS[l.action] || esc(l.action || "—");
          let detail = "";
          try {
            const obj =
              typeof l.detail === "string"
                ? JSON.parse(l.detail)
                : l.detail || {};
            detail = Object.entries(obj)
              .map(([k, v]) => `${k}: ${v}`)
              .join(", ");
          } catch (e) {
            detail = l.detail || "";
          }
          return `
      <tr>
        <td>${esc(l.id)}</td>
        <td style="color:var(--accent);font-size:0.82rem">${esc(l.admin_email || l.admin_id)}</td>
        <td>${label}</td>
        <td>${esc(l.target_type || "—")} ${l.target_id ? "#" + l.target_id : ""}</td>
        <td style="font-size:0.78rem;color:var(--muted)" title="${esc(detail)}">${esc(detail.length > 60 ? detail.slice(0, 60) + "…" : detail)}</td>
        <td>${esc(l.ip_address || "—")}</td>
        <td>${fmt(l.created_at)}</td>
      </tr>`;
        })
        .join("") || emptyRow(7);
    buildPagination("auditPagination", page, d.pages || 1, "loadAudit");
  } catch (e) {
    showToast(adminT("admin.toast.error"), "error");
  }
}

// ─── Site Config ──────────────────────────────────────────────
let _siteConfigCache = null;

const CMS_PAGE_LINKS = [
  { slug: "home", url: "/", icon: "fa-house", labelKey: "admin.config.page.home" },
  {
    slug: "contact",
    url: "/contact",
    icon: "fa-envelope",
    labelKey: "admin.config.page.contact",
  },
  {
    slug: "privacy",
    url: "/privacy",
    icon: "fa-shield-halved",
    labelKey: "admin.config.page.privacy",
  },
  {
    slug: "terms",
    url: "/terms",
    icon: "fa-file-contract",
    labelKey: "admin.config.page.terms",
  },
  {
    slug: "ai-terms",
    url: "/ai-terms",
    icon: "fa-robot",
    labelKey: "admin.config.page.aiTerms",
  },
  {
    slug: "payment-policy",
    url: "/payment-policy",
    icon: "fa-credit-card",
    labelKey: "admin.config.page.paymentPolicy",
  },
  {
    slug: "data-deletion",
    url: "/data-deletion",
    icon: "fa-trash-can",
    labelKey: "admin.config.page.dataDeletion",
  },
  {
    slug: "support",
    url: "/support",
    icon: "fa-circle-question",
    labelKey: "admin.config.page.support",
  },
];

function renderCmsPageLinks() {
  const wrap = document.getElementById("cmsPageLinks");
  if (!wrap) return;
  wrap.innerHTML = CMS_PAGE_LINKS.map(
    (p) =>
      `<a class="cms-page-link" href="${esc(p.url)}?edit=1">` +
      `<i class="fas ${esc(p.icon)}"></i>` +
      `<span>${esc(adminT(p.labelKey))}</span></a>`,
  ).join("");
}

async function loadSiteConfigTab() {
  try {
    const res = await fetch(`${API}/api/admin/site-config`, {
      headers: authHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || "Không tải được cấu hình");
    _siteConfigCache = data.config || {};
    fillSiteConfigForm(_siteConfigCache);
    renderCmsPageLinks();
    const meta = document.getElementById("cfgUpdatedAt");
    if (meta && _siteConfigCache.updated_at) {
      meta.textContent = adminT("admin.config.updatedAt", {
        time: _siteConfigCache.updated_at,
      });
    }
    await loadTranslationConfigTab();
  } catch (e) {
    showToast(e.message || adminT("admin.toast.loadConfigError"), "error");
  }
}

function fillSiteConfigForm(cfg) {
  const brand = cfg.brand || {};
  const contact = cfg.contact || {};
  const plans = cfg.plans || {};
  const prompts = cfg.prompts || {};
  setVal("cfgBrandName", brand.name);
  setVal("cfgSystemName", brand.system_name);
  setVal("cfgLogoType", brand.logo_type || "icon");
  setVal("cfgLogoIcon", brand.logo_icon);
  setVal("cfgLogoImageUrl", brand.logo_image_url);
  setVal("cfgSupportEmail", contact.support_email);
  setVal("cfgCompanyName", contact.company_name);
  setVal("cfgCompanyAddress", contact.company_address);
  setVal("cfgWebsiteUrl", contact.website_url);
  setVal("cfgFreeTokens", plans.free?.token_cap);
  setVal("cfgProPrice", plans.pro?.price_vnd);
  setVal("cfgProTokens", plans.pro?.token_cap);
  setVal("cfgProMaxPrice", plans.promax?.price_vnd);
  setVal("cfgProMaxTokens", plans.promax?.token_cap);
  setVal("cfgPromptAiTerms", prompts.ai_terms);
  setVal("cfgPromptPrivacy", prompts.privacy_payment);
}

function setVal(id, v) {
  const el = document.getElementById(id);
  if (el) el.value = v == null ? "" : v;
}

function buildConfigPatch() {
  const base = _siteConfigCache || {};
  return {
    brand: {
      ...(base.brand || {}),
      name: val("cfgBrandName"),
      system_name: val("cfgSystemName"),
      logo_type: val("cfgLogoType") || "icon",
      logo_icon: val("cfgLogoIcon") || "fa-language",
      logo_image_url: val("cfgLogoImageUrl"),
    },
    contact: {
      ...(base.contact || {}),
      support_email: val("cfgSupportEmail"),
      company_name: val("cfgCompanyName"),
      company_address: val("cfgCompanyAddress"),
      website_url: val("cfgWebsiteUrl"),
    },
    plans: {
      free: {
        label: "Free",
        token_cap: intVal("cfgFreeTokens", 5000),
        price_vnd: 0,
      },
      pro: {
        label: "Pro",
        token_cap: intVal("cfgProTokens", 120000),
        price_vnd: intVal("cfgProPrice", 99000),
      },
      promax: {
        label: "ProMax",
        token_cap: intVal("cfgProMaxTokens", 300000),
        price_vnd: intVal("cfgProMaxPrice", 199000),
      },
    },
    prompts: {
      ai_terms: val("cfgPromptAiTerms"),
      privacy_payment: val("cfgPromptPrivacy"),
    },
  };
}

function val(id) {
  return (document.getElementById(id)?.value || "").trim();
}

function intVal(id, fallback) {
  const n = parseInt(document.getElementById(id)?.value, 10);
  return Number.isFinite(n) ? n : fallback;
}

async function saveSiteConfigPartial(patch, successMsg) {
  try {
    const res = await fetch(`${API}/api/admin/site-config`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify(patch),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || "Lưu thất bại");
    _siteConfigCache = data.config || patch;
    fillSiteConfigForm(_siteConfigCache);
    const meta = document.getElementById("cfgUpdatedAt");
    if (meta && _siteConfigCache.updated_at) {
      meta.textContent = adminT("admin.config.updatedAt", {
        time: _siteConfigCache.updated_at,
      });
    }
    const n = (data.html_files_updated || []).length;
    showToast(successMsg + (n ? ` · Đã đồng bộ ${n} file HTML` : ""));
  } catch (e) {
    showToast(e.message || adminT("admin.toast.saveError"), "error");
  }
}

async function saveSiteConfigGeneral() {
  const patch = buildConfigPatch();
  await saveSiteConfigPartial(
    { brand: patch.brand, contact: patch.contact },
    adminT("admin.toast.savedBrand"),
  );
}

async function saveSiteConfigPlans() {
  const patch = buildConfigPatch();
  await saveSiteConfigPartial(
    { plans: patch.plans },
    adminT("admin.toast.savedPlans"),
  );
}

async function saveSiteConfigPrompts() {
  const patch = buildConfigPatch();
  await saveSiteConfigPartial(
    { prompts: patch.prompts },
    adminT("admin.toast.savedPrompts"),
  );
}

// ─── Translation API config ───────────────────────────────────
let _translationConfigCache = null;

function formatPlanList(plans) {
  const labels = { free: "Free", pro: "Pro", promax: "ProMax" };
  return (plans || [])
    .map((p) => labels[String(p).toLowerCase()] || p)
    .join(", ");
}

function renderBuiltinModelsInfo(models) {
  const el = document.getElementById("cfgBuiltinModelsInfo");
  if (!el) return;
  const intro = adminT("admin.config.translationApiBuiltinIntro");
  const footer = adminT("admin.config.translationApiBuiltinFooter");
  el.innerHTML = `
    <p class="config-hint" data-i18n-html>${intro}</p>
    <p class="config-hint">${footer}</p>
  `;
}

function renderTranslationModelsList(models) {
  const el = document.getElementById("cfgTranslationModelsList");
  if (!el) return;
  if (!models || !models.length) {
    el.innerHTML = `<p class="config-hint config-hint-muted">${esc(adminT("admin.config.noCustomApis"))}</p>`;
    return;
  }
  el.innerHTML = models.map((m, idx) => buildTranslationModelRow(m, idx)).join("");
}

function buildTranslationModelRow(m, idx) {
  const plans = m.plans || [];
  const modelVal = m.model || m.label || "";
  const planChecks = ["free", "pro", "promax"]
    .map(
      (p) =>
        `<label class="tm-plan-label"><input type="checkbox" class="tm-plan" value="${p}" ${plans.includes(p) ? "checked" : ""}/> ${p}</label>`,
    )
    .join("");
  return `
    <div class="translation-model-row" data-id="${esc(m.id || "")}" data-idx="${idx}">
      <div class="tm-field tm-field-model">
        <label>${esc(adminT("admin.config.labelModel"))}</label>
        <input type="text" class="tm-model" value="${esc(modelVal)}" placeholder="google/gemini-2.5-flash" />
      </div>
      <div class="tm-field tm-field-key">
        <label>${esc(adminT("admin.config.labelApiKey"))}</label>
        <input type="password" class="tm-key" value="${esc(m.api_key || "")}" placeholder="sk-..." autocomplete="off" />
      </div>
      <div class="tm-field tm-field-plans">
        <label>${esc(adminT("admin.config.labelPlans"))}</label>
        <div class="tm-plans">${planChecks}</div>
      </div>
      <button type="button" class="btn-icon danger tm-remove" onclick="removeTranslationModelRow(${idx})" title="${esc(adminT("admin.btn.delete"))}">
        <i class="fas fa-trash"></i>
      </button>
    </div>`;
}

function collectTranslationModelsFromDom() {
  return Array.from(
    document.querySelectorAll("#cfgTranslationModelsList .translation-model-row"),
  ).map((row) => {
    const payload = {
      model: row.querySelector(".tm-model")?.value.trim(),
      api_key: row.querySelector(".tm-key")?.value.trim(),
      plans: Array.from(row.querySelectorAll(".tm-plan:checked")).map((c) => c.value),
      enabled: true,
    };
    const id = row.dataset.id?.trim();
    if (id) payload.id = id;
    return payload;
  });
}

function addTranslationModelRow() {
  const models = collectTranslationModelsFromDom();
  models.push({
    model: "",
    api_key: "",
    plans: ["promax"],
    enabled: true,
  });
  renderTranslationModelsList(models);
}

function removeTranslationModelRow(idx) {
  const models = collectTranslationModelsFromDom();
  models.splice(idx, 1);
  renderTranslationModelsList(models);
}

async function loadTranslationConfigTab() {
  try {
    const res = await fetch(`${API}/api/admin/translation-config`, {
      headers: authHeaders(),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || adminT("admin.toast.loadConfigError"));
    _translationConfigCache = data.config || {};
    renderBuiltinModelsInfo(_translationConfigCache.builtin_models || []);
    renderTranslationModelsList(_translationConfigCache.custom_models || []);
  } catch (e) {
    showToast(e.message || adminT("admin.toast.loadConfigError"), "error");
  }
}

async function saveTranslationConfig() {
  const custom_models = collectTranslationModelsFromDom().filter((m) => m.model);
  try {
    const res = await fetch(`${API}/api/admin/translation-config`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ custom_models }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || adminT("admin.toast.saveError"));
    _translationConfigCache = data.config || {};
    renderBuiltinModelsInfo(_translationConfigCache.builtin_models || []);
    renderTranslationModelsList(_translationConfigCache.custom_models || []);
    showToast(adminT("admin.toast.savedTranslationApi"));
  } catch (e) {
    showToast(e.message || adminT("admin.toast.saveError"), "error");
  }
}

const TAB_LOADERS = {
  dashboard: () => loadStats(),
  users: () => loadUsers(1),
  translations: () => loadTranslations(1),
  payments: () => loadPayments(1),
  contacts: () => loadContacts(1),
  newsletter: () => loadNewsletter(1),
  audit: () => loadAudit(1),
  "site-config": () => loadSiteConfigTab(),
};

const TAB_TITLE_KEYS = {
  dashboard: "admin.tab.dashboard",
  users: "admin.tab.users",
  translations: "admin.tab.translations",
  payments: "admin.tab.payments",
  contacts: "admin.tab.contacts",
  newsletter: "admin.tab.newsletter",
  audit: "admin.tab.audit",
  "site-config": "admin.tab.site-config",
};

function updateSiteConfigTopbar(tabName) {
  const subtitle = document.getElementById("topbarSubtitle");
  const isSiteConfig = tabName === "site-config";
  if (subtitle) subtitle.style.display = isSiteConfig ? "" : "none";
}

function switchTab(tabName) {
  document
    .querySelectorAll(".admin-tab")
    .forEach((el) => el.classList.remove("active"));
  document
    .querySelectorAll(".sidebar-item")
    .forEach((el) => el.classList.remove("active"));
  const tab = document.getElementById(`tab-${tabName}`);
  if (tab) tab.classList.add("active");
  const link = document.querySelector(`.sidebar-item[data-tab="${tabName}"]`);
  if (link) link.classList.add("active");
  document.getElementById("topbarTitle").textContent = adminT(
    TAB_TITLE_KEYS[tabName] || tabName,
  );
  updateSiteConfigTopbar(tabName);
  TAB_LOADERS[tabName]?.();
}

// ─── Init ─────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  const loading = document.getElementById("adminLoading");
  const denied = document.getElementById("adminDenied");

  const ok = await checkAdminAccess();
  loading.style.display = "none";

  if (!ok) {
    denied.style.display = "block";
    return;
  }

  // Sidebar links
  document.querySelectorAll(".sidebar-item[data-tab]").forEach((item) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      switchTab(item.dataset.tab);
      // close sidebar on mobile
      document.getElementById("sidebar").classList.remove("open");
    });
  });

  // Mobile sidebar toggle
  document.getElementById("sidebarToggle")?.addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });

  // Close modal on backdrop click
  document.querySelectorAll(".admin-modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.style.display = "none";
    });
  });

  // Enter key on user search
  document.getElementById("userSearch")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadUsers(1);
  });

  window.addEventListener("siteLanguageChanged", () => {
    renderCmsPageLinks();
    const active = document.querySelector(".sidebar-item.active[data-tab]");
    if (active) {
      switchTab(active.dataset.tab);
    }
  });

  // Load default tab
  switchTab("dashboard");
});
