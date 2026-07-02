// home.js - Home page JavaScript
document.addEventListener("DOMContentLoaded", function () {
  initializeHomePage();
});

async function initializeHomePage() {
  setupSmoothScrolling();
  setupPricingButtons();
  setupMobileMenu();
  await loadPublicStats();
}

async function loadPublicStats() {
  try {
    const response = await fetch("/api/public/stats", { cache: "no-store" });
    if (!response.ok) {
      console.warn("Public stats unavailable (HTTP", response.status, "). Restart backend: python run_api.py");
      return;
    }
    const data = await response.json();
    applyPublicStats(data);
  } catch (error) {
    console.warn("Failed to load public stats:", error);
  }
}

function applyPublicStats(data) {
  setStatTarget("statTranslations", data.translations_completed);
  setStatTarget("statUsers", data.total_users);
  setStatTarget("statLanguages", data.languages_count);

  document.querySelectorAll("#stats .stat-number").forEach((el) => {
    const rawTarget = el.getAttribute("data-target");
    const target = Number(rawTarget);
    el.textContent = Number.isFinite(target)
      ? Math.round(target).toLocaleString()
      : "0";
  });
}

function setStatTarget(elementId, value) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const num = Number(value);
  el.setAttribute("data-target", String(Number.isFinite(num) ? num : 0));
}

// Global helper used by pricing CTA buttons
function goToUpgrade(plan) {
  const selected = String(plan || "")
    .trim()
    .toLowerCase();
  const token = localStorage.getItem("token") || "";

  // If already logged in, go straight to dashboard and auto-open upgrade flow
  if (token) {
    if (selected && selected !== "free") {
      window.location.href = `/dashboard?upgrade_plan=${encodeURIComponent(selected)}&autocreate=1`;
    } else {
      window.location.href = "/dashboard";
    }
    return;
  }

  // Not logged in: remember intended plan for after login
  if (selected && selected !== "free") {
    try {
      localStorage.setItem("pending_upgrade_plan", selected);
    } catch (e) {
      // ignore
    }
  }

  window.location.href = "/auth";
}

function setupMobileMenu() {
  // Mobile menu toggle
  window.toggleMenu = function () {
    const navLinks = document.querySelector(".nav-links");
    const hamburger = document.querySelector(".hamburger");

    navLinks.classList.toggle("mobile-menu");
    hamburger.classList.toggle("active");
  };

  // Close mobile menu when clicking outside or on a link
  document.addEventListener("click", function (e) {
    const navLinks = document.querySelector(".nav-links");
    const hamburger = document.querySelector(".hamburger");

    if (
      !e.target.closest(".nav-container") &&
      navLinks.classList.contains("mobile-menu")
    ) {
      navLinks.classList.remove("mobile-menu");
      hamburger.classList.remove("active");
    }
  });

  // Close mobile menu when clicking on nav links
  document.querySelectorAll(".nav-links a").forEach((link) => {
    link.addEventListener("click", function () {
      const navLinks = document.querySelector(".nav-links");
      const hamburger = document.querySelector(".hamburger");

      navLinks.classList.remove("mobile-menu");
      hamburger.classList.remove("active");
    });
  });
}

function setupSmoothScrolling() {
  // Smooth scrolling for navigation links
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute("href"));
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    });
  });
}

function scrollToFeatures() {
  const featuresSection = document.getElementById("features");
  if (featuresSection) {
    featuresSection.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }
}

function setupPricingButtons() {
  // Pricing CTA buttons are wired via onclick="goToUpgrade(...)" in home.html.
}

window.addEventListener("siteLanguageChanged", () => {
  loadPublicStats();
});

function quickTranslate() {
  const text = document.getElementById("quick-text").value.trim();
  const targetLang = document.getElementById("quick-target-lang").value;
  const resultDiv = document.getElementById("quick-result");
  const outputSpan = document.getElementById("quick-output");

  if (!text) {
    showQuickMessage("Vui lòng nhập văn bản cần dịch!", "error");
    return;
  }

  // Simple demo translations for common phrases
  const translations = {
    hello: { vi: "xin chào", en: "hello", fr: "bonjour", de: "hallo" },
    "how are you": {
      vi: "bạn thế nào",
      en: "how are you",
      fr: "comment allez-vous",
      de: "wie geht es dir",
    },
    "thank you": { vi: "cảm ơn", en: "thank you", fr: "merci", de: "danke" },
    "good morning": {
      vi: "chào buổi sáng",
      en: "good morning",
      fr: "bonjour",
      de: "guten morgen",
    },
    goodbye: {
      vi: "tạm biệt",
      en: "goodbye",
      fr: "au revoir",
      de: "auf wiedersehen",
    },
  };

  // Try to find exact match first
  const lowerText = text.toLowerCase();
  let translation = translations[lowerText]?.[targetLang];

  // If no exact match, try partial match
  if (!translation) {
    for (const [key, value] of Object.entries(translations)) {
      if (lowerText.includes(key)) {
        translation = value[targetLang];
        break;
      }
    }
  }

  // If still no translation, provide a generic response
  if (!translation) {
    if (targetLang === "vi") {
      translation = "[Dịch sang tiếng Việt: " + text + "]";
    } else if (targetLang === "en") {
      translation = "[Translated to English: " + text + "]";
    } else if (targetLang === "fr") {
      translation = "[Traduit en français: " + text + "]";
    } else if (targetLang === "de") {
      translation = "[Übersetzt auf Deutsch: " + text + "]";
    }
  }

  outputSpan.textContent = translation;
  resultDiv.style.display = "block";

  // Hide result after 10 seconds
  setTimeout(() => {
    resultDiv.style.display = "none";
  }, 10000);
}

function showQuickMessage(message, type = "info") {
  // Simple notification for quick translate
  const notification = document.createElement("div");
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${type === "error" ? "rgba(220, 53, 69, 0.9)" : "rgba(40, 167, 69, 0.9)"};
    color: white;
    padding: 15px 20px;
    border-radius: 8px;
    z-index: 10000;
    font-weight: 500;
  `;
  notification.textContent = message;
  document.body.appendChild(notification);

  setTimeout(() => {
    document.body.removeChild(notification);
  }, 3000);
}
