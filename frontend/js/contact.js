// contact.js - Contact page JavaScript
document.addEventListener("DOMContentLoaded", function () {
  initializeContactPage();
});

function initializeContactPage() {
  setupFormValidation();
  setupQuickContact();
  setupNewsletterForm();
  setupMapPlaceholder();
  prefillContactForm();
  loadMyMessages();
}

/** Nếu đã đăng nhập, điền sẵn thông tin vào form liên hệ */
function prefillContactForm() {
  try {
    const raw = localStorage.getItem("user");
    if (!raw) return;
    const user = JSON.parse(raw);
    if (!user) return;

    const emailEl = document.getElementById("contact-email");
    if (emailEl && user.email) {
      emailEl.value = user.email;
      emailEl.setAttribute("readonly", "readonly");
      emailEl.style.opacity = "0.7";
      emailEl.title = "Email lấy từ tài khoản đăng nhập";
    }

    // Tách tên thành họ + tên nếu có
    if (user.name) {
      const parts = user.name.trim().split(/\s+/);
      const lastEl = document.getElementById("contact-lastname");
      const firstEl = document.getElementById("contact-firstname");
      if (lastEl && parts.length > 1) lastEl.value = parts[0];
      if (firstEl && parts.length > 0) firstEl.value = parts[parts.length - 1];
    }
  } catch (e) {
    /* ignore */
  }
}

function setupFormValidation() {
  const contactForm = document.querySelector(".contact-form");
  if (!contactForm) return;

  // Real-time validation
  const inputs = contactForm.querySelectorAll("input, textarea, select");
  inputs.forEach((input) => {
    input.addEventListener("blur", function () {
      validateField(this);
    });

    input.addEventListener("input", function () {
      if (this.classList.contains("invalid")) {
        validateField(this);
      }
    });
  });

  // Character counter for message
  const messageTextarea = document.getElementById("contact-message");
  const charCounter = document.createElement("div");
  charCounter.className = "char-counter";
  charCounter.innerHTML = '<span id="message-count">0</span>/1000 ký tự';
  messageTextarea.parentNode.appendChild(charCounter);

  messageTextarea.addEventListener("input", function () {
    const count = this.value.length;
    document.getElementById("message-count").textContent = count;

    if (count > 900) {
      charCounter.style.color = "#ff6b6b";
    } else if (count > 800) {
      charCounter.style.color = "#ffaa00";
    } else {
      charCounter.style.color = "rgba(255, 255, 255, 0.7)";
    }
  });
}

function validateField(field) {
  const value = field.value.trim();
  let isValid = true;
  let errorMessage = "";

  // Remove existing error
  removeFieldError(field);

  switch (field.id) {
    case "contact-firstname":
    case "contact-lastname":
      if (!value) {
        isValid = false;
        errorMessage = "Vui lòng nhập tên";
      } else if (value.length < 2) {
        isValid = false;
        errorMessage = "Tên phải có ít nhất 2 ký tự";
      }
      break;

    case "contact-email":
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!value) {
        isValid = false;
        errorMessage = "Vui lòng nhập email";
      } else if (!emailRegex.test(value)) {
        isValid = false;
        errorMessage = "Email không hợp lệ";
      }
      break;

    case "contact-company":
      // Optional field, no validation needed
      break;

    case "contact-subject":
      if (!value) {
        isValid = false;
        errorMessage = "Vui lòng chọn chủ đề";
      }
      break;

    case "contact-message":
      if (!value) {
        isValid = false;
        errorMessage = "Vui lòng nhập nội dung tin nhắn";
      } else if (value.length < 10) {
        isValid = false;
        errorMessage = "Tin nhắn phải có ít nhất 10 ký tự";
      } else if (value.length > 1000) {
        isValid = false;
        errorMessage = "Tin nhắn không được vượt quá 1000 ký tự";
      }
      break;
  }

  if (!isValid) {
    showFieldError(field, errorMessage);
  }

  return isValid;
}

function showFieldError(field, message) {
  field.classList.add("invalid");

  const errorDiv = document.createElement("div");
  errorDiv.className = "field-error";
  errorDiv.textContent = message;

  field.parentNode.appendChild(errorDiv);
}

function removeFieldError(field) {
  field.classList.remove("invalid");
  const errorDiv = field.parentNode.querySelector(".field-error");
  if (errorDiv) {
    errorDiv.remove();
  }
}

async function handleContactSubmit(event) {
  event.preventDefault();

  const form = event.target;
  const submitBtn = form.querySelector(".contact-submit");

  // Validate all fields
  const inputs = form.querySelectorAll("input, textarea, select");
  let isFormValid = true;

  inputs.forEach((input) => {
    if (!validateField(input)) {
      isFormValid = false;
    }
  });

  if (!isFormValid) {
    showContactMessage("Vui lòng kiểm tra lại thông tin đã nhập", "error");
    return;
  }

  // Collect form data (optional fields may be absent on some page variants)
  const formData = {
    firstName: form.querySelector("#contact-firstname")?.value?.trim() ?? "",
    lastName: form.querySelector("#contact-lastname")?.value?.trim() ?? "",
    email: form.querySelector("#contact-email")?.value?.trim() ?? "",
    company: form.querySelector("#contact-company")?.value?.trim() ?? "",
    subject: form.querySelector("#contact-subject")?.value ?? "",
    message: form.querySelector("#contact-message")?.value?.trim() ?? "",
    newsletter: form.querySelector("#contact-newsletter")?.checked ?? false,
  };

  // Show loading
  const originalText = submitBtn.innerHTML;
  submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang gửi...';
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/contact/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: formData.firstName,
        last_name: formData.lastName,
        email: formData.email,
        subject: formData.subject || "general",
        message: formData.message,
      }),
    });
    const result = await res.json();
    if (!res.ok) {
      const fieldErrors = result.fields
        ? Object.values(result.fields).join(" | ")
        : "";
      showContactMessage(
        fieldErrors || result.error || "Có lỗi xảy ra.",
        "error",
      );
      return;
    }

    // Also subscribe newsletter if checked
    if (formData.newsletter && formData.email) {
      fetch("/api/contact/newsletter/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: formData.email }),
      }).catch(() => {});
    }

    showContactMessage(
      "Cảm ơn bạn đã liên hệ! Chúng tôi sẽ phản hồi trong vòng 24 giờ.",
      "success",
    );
    form.reset();
    const mc = document.getElementById("message-count");
    if (mc) mc.textContent = "0";
    // Khôi phục email readonly sau khi reset
    prefillContactForm();
    // Refresh danh sách tin nhắn
    setTimeout(loadMyMessages, 800);
  } catch (error) {
    console.error("Contact submission error:", error);
    showContactMessage("Có lỗi xảy ra. Vui lòng thử lại sau.", "error");
  } finally {
    submitBtn.innerHTML = originalText;
    submitBtn.disabled = false;
  }
}

function setupQuickContact() {
  const quickOptions = document.querySelectorAll(".quick-option");

  quickOptions.forEach((option) => {
    option.addEventListener("click", function (e) {
      e.preventDefault();

      const platform = this.querySelector("span").textContent;
      showContactMessage(`Đang mở ${platform}...`, "info");

      // Here you would open the respective messaging platform
      // For demo purposes, we'll just show a message
      setTimeout(() => {
        showContactMessage(
          `Không thể kết nối đến ${platform}. Vui lòng liên hệ trực tiếp qua email hoặc điện thoại.`,
          "error",
        );
      }, 2000);
    });
  });
}

function setupNewsletterForm() {
  const newsletterForm = document.getElementById("newsletter-form");

  if (newsletterForm) {
    newsletterForm.addEventListener("submit", handleNewsletterSubmit);
  }
}

async function handleNewsletterSubmit(event) {
  event.preventDefault();

  const email = document.getElementById("newsletter-email").value;

  if (!email) {
    showNewsletterMessage("Vui lòng nhập email", "error");
    return;
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    showNewsletterMessage("Email không hợp lệ", "error");
    return;
  }

  // Show loading
  const submitBtn = event.target.querySelector("button");
  const originalText = submitBtn.innerHTML;
  submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/contact/newsletter/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const result = await res.json();
    if (!res.ok) {
      showNewsletterMessage(result.error || "Có lỗi xảy ra.", "error");
      return;
    }
    showNewsletterMessage(
      result.message ||
        "Đăng ký thành công! Cảm ơn bạn đã quan tâm đến AI Translator.",
      "success",
    );
    document.getElementById("newsletter-email").value = "";
  } catch (error) {
    console.error("Newsletter subscription error:", error);
    showNewsletterMessage("Có lỗi xảy ra. Vui lòng thử lại sau.", "error");
  } finally {
    submitBtn.innerHTML = originalText;
    submitBtn.disabled = false;
  }
}

function setupMapPlaceholder() {
  const mapPlaceholder = document.querySelector(".map-placeholder");

  if (mapPlaceholder) {
    mapPlaceholder.addEventListener("click", function () {
      showContactMessage(
        "Tính năng bản đồ sẽ được cập nhật sớm. Vui lòng liên hệ qua thông tin bên cạnh.",
        "info",
      );
    });
  }
}

function showContactMessage(message, type = "info") {
  showMessage(message, type, "contact-message");
}

function showNewsletterMessage(message, type = "info") {
  showMessage(message, type, "newsletter-message");
}

function showMessage(message, type, className) {
  // Remove existing messages
  const existingMessages = document.querySelectorAll(`.${className}`);
  existingMessages.forEach((msg) => msg.remove());

  // Create new message
  const messageDiv = document.createElement("div");
  messageDiv.className = `${className} ${type}`;
  messageDiv.innerHTML = `
        <i class="fas ${type === "success" ? "fa-check-circle" : type === "error" ? "fa-exclamation-circle" : "fa-info-circle"}"></i>
        ${message}
    `;

  // Add to appropriate container
  if (className === "contact-message") {
    const form = document.querySelector(".contact-form");
    form.insertBefore(messageDiv, form.firstChild);
  } else if (className === "newsletter-message") {
    const newsletterContent = document.querySelector(".newsletter-content");
    newsletterContent.insertBefore(messageDiv, newsletterContent.firstChild);
  }

  // Auto remove after 5 seconds for non-error messages
  if (type !== "error") {
    setTimeout(() => {
      if (messageDiv.parentNode) {
        messageDiv.remove();
      }
    }, 5000);
  }
}

// ─── My Messages ───────────────────────────────────────────────────────────
async function loadMyMessages() {
  const section = document.getElementById("my-messages-section");
  const listEl = document.getElementById("my-messages-list");
  if (!section || !listEl) return;

  const token = localStorage.getItem("token");
  if (!token) {
    // Chưa đăng nhập → ẩn section
    section.style.display = "none";
    return;
  }

  section.style.display = "block";

  try {
    const res = await fetch("/api/contact/my-messages", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      section.style.display = "none";
      return;
    }
    const d = await res.json();
    const msgs = d.messages || [];

    if (!msgs.length) {
      listEl.innerHTML = `
        <p style="color:var(--muted,#9aa4b2);text-align:center;padding:24px">
          <i class="fas fa-inbox"></i> Bạn chưa gửi tin nhắn nào.
        </p>`;
      return;
    }

    const SUBJECT_LABELS = {
      general: "Câu hỏi chung",
      technical: "Hỗ trợ kỹ thuật",
      billing: "Thanh toán",
      partnership: "Hợp tác",
      other: "Khác",
    };
    const STATUS_LABELS = {
      unread: "Chờ xử lý",
      read: "Đã xem",
      replied: "Đã phản hồi",
    };
    const STATUS_COLORS = {
      unread: "#ffc832",
      read: "#00a8ff",
      replied: "#00ffd1",
    };

    listEl.innerHTML = msgs
      .map((m) => {
        const statusColor = STATUS_COLORS[m.status] || "#9aa4b2";
        const statusLabel = STATUS_LABELS[m.status] || m.status;
        const subjectLabel = SUBJECT_LABELS[m.subject] || m.subject;
        const dateStr = m.created_at
          ? new Date(m.created_at).toLocaleString("vi-VN", {
              dateStyle: "short",
              timeStyle: "short",
            })
          : "";

        const replyBlock = m.admin_reply
          ? `
        <div style="margin-top:12px;background:rgba(0,255,209,0.06);border-left:3px solid #00ffd1;
                    border-radius:0 8px 8px 0;padding:12px 16px">
          <div style="color:#00ffd1;font-size:0.78rem;font-weight:600;margin-bottom:6px">
            <i class="fas fa-reply"></i> Phản hồi từ đội ngũ hỗ trợ
            ${m.replied_at ? `<span style="color:#4a6a7a;font-weight:400;margin-left:8px">${new Date(m.replied_at).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" })}</span>` : ""}
          </div>
          <p style="margin:0;color:#cfe8f0;font-size:0.9rem;line-height:1.6;white-space:pre-wrap">${escHtml(m.admin_reply)}</p>
        </div>`
          : "";

        return `
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);
                    border-radius:10px;padding:18px;margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px">
            <span style="font-weight:600;color:#e6eef3">${escHtml(subjectLabel)}</span>
            <div style="display:flex;align-items:center;gap:10px">
              <span style="color:${statusColor};font-size:0.8rem;font-weight:600">${statusLabel}</span>
              <span style="color:#4a6a7a;font-size:0.78rem">${dateStr}</span>
            </div>
          </div>
          <p style="margin:0;color:#9aa4b2;font-size:0.88rem;line-height:1.6;white-space:pre-wrap">${escHtml(m.message)}</p>
          ${replyBlock}
        </div>`;
      })
      .join("");
  } catch (e) {
    section.style.display = "none";
  }
}

function escHtml(str) {
  return String(str ?? "").replace(
    /[&<>"']/g,
    (m) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        m
      ],
  );
}

// Add custom styles for contact page
const contactStyle = document.createElement("style");
contactStyle.textContent = `
    /* Form validation styles */
    .form-group input.invalid,
    .form-group textarea.invalid,
    .form-group select.invalid {
        border-color: #ff6b6b;
        box-shadow: 0 0 0 2px rgba(255, 107, 107, 0.2);
    }

    .field-error {
        color: #ff6b6b;
        font-size: 0.875rem;
        margin-top: 5px;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    .field-error::before {
        content: '⚠';
        font-size: 1rem;
    }

    .char-counter {
        text-align: right;
        font-size: 0.875rem;
        color: rgba(255, 255, 255, 0.7);
        margin-top: 5px;
    }

    /* Message styles */
    .contact-message, .newsletter-message {
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 500;
        animation: slideDown 0.3s ease;
    }

    .contact-message.success, .newsletter-message.success {
        background: rgba(76, 175, 80, 0.1);
        border: 1px solid #4CAF50;
        color: #4CAF50;
    }

    .contact-message.error, .newsletter-message.error {
        background: rgba(244, 67, 54, 0.1);
        border: 1px solid #f44336;
        color: #f44336;
    }

    .contact-message.info, .newsletter-message.info {
        background: rgba(33, 150, 243, 0.1);
        border: 1px solid #2196F3;
        color: #2196F3;
    }

    /* Quick contact styles */
    .quick-options {
        display: flex;
        gap: 15px;
        justify-content: center;
        margin-top: 15px;
    }

    .quick-option {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 15px;
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        text-decoration: none;
        color: white;
        transition: all 0.3s ease;
        min-width: 80px;
    }

    .quick-option:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
        background: rgba(255, 255, 255, 0.15);
    }

    .quick-option i {
        font-size: 1.5rem;
        margin-bottom: 5px;
    }

    .quick-option span {
        font-size: 0.875rem;
        font-weight: 500;
    }

    /* Map placeholder */
    .map-placeholder {
        height: 300px;
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 15px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.3s ease;
        border: 2px dashed rgba(255, 255, 255, 0.3);
    }

    .map-placeholder:hover {
        background: rgba(255, 255, 255, 0.15);
        border-color: rgba(255, 215, 0, 0.5);
    }

    .map-placeholder i {
        font-size: 3rem;
        color: rgba(255, 255, 255, 0.6);
        margin-bottom: 15px;
    }

    .map-placeholder p {
        color: rgba(255, 255, 255, 0.8);
        text-align: center;
        margin: 0;
    }

    .map-placeholder small {
        color: rgba(255, 255, 255, 0.6);
        margin-top: 10px;
        display: block;
    }

    /* Newsletter form */
    .newsletter-input-group {
        display: flex;
        gap: 10px;
        max-width: 400px;
    }

    .newsletter-input-group input {
        flex: 1;
        padding: 12px 16px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 25px;
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        color: white;
        font-size: 1rem;
    }

    .newsletter-input-group input::placeholder {
        color: rgba(255, 255, 255, 0.6);
    }

    .newsletter-input-group button {
        padding: 12px 24px;
        border: none;
        border-radius: 25px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.3s ease;
    }

    .newsletter-input-group button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
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

    /* Responsive adjustments */
    @media (max-width: 768px) {
        .quick-options {
            flex-wrap: wrap;
        }

        .newsletter-input-group {
            flex-direction: column;
        }

        .newsletter-input-group button {
            align-self: stretch;
        }
    }
`;
document.head.appendChild(contactStyle);
