(function () {
  "use strict";

  var cached = null;

  function formatVnd(n) {
    return Number(n || 0).toLocaleString("vi-VN");
  }

  function formatHomePriceVnd(n) {
    var num = Number(n || 0);
    if (!num) return "0đ";
    return formatVnd(num) + " VNĐ";
  }

  function applyHomePricing(plans) {
    if (!plans) return;
    var grid = document.querySelector("#pricing .pricing-grid");
    if (!grid) return;
    var cards = grid.querySelectorAll(".pricing-card");
    if (cards.length < 3) return;

    var free = plans.free || {};
    var pro = plans.pro || {};
    var promax = plans.promax || {};

    var freeAmount = cards[0].querySelector(".amount");
    if (freeAmount) freeAmount.textContent = formatHomePriceVnd(free.price_vnd);

    var proAmount = cards[1].querySelector(".amount");
    if (proAmount) proAmount.textContent = formatHomePriceVnd(pro.price_vnd);

    var promaxAmount = cards[2].querySelector(".amount");
    if (promaxAmount) {
      promaxAmount.textContent = formatHomePriceVnd(promax.price_vnd);
    }
  }

  function applyBrand(brand) {
    if (!brand) return;
    document.querySelectorAll(".nav-logo").forEach(function (el) {
      var iconClass = (brand.logo_icon || "fa-language").replace(/^fas\s+/, "");
      if (brand.logo_type === "image" && brand.logo_image_url) {
        el.innerHTML =
          '<img src="' +
          brand.logo_image_url +
          '" alt="' +
          (brand.name || "Logo") +
          '" style="height:32px;width:auto;border-radius:6px" />' +
          "<span>" +
          (brand.name || "AI Translator") +
          "</span>";
      } else {
        el.innerHTML =
          '<i class="fas ' +
          iconClass +
          '"></i><span>' +
          (brand.name || "AI Translator") +
          "</span>";
      }
    });
    if (brand.system_name) {
      document.querySelectorAll("title").forEach(function (t) {
        if (t.textContent.indexOf("AI Translation") !== -1) {
          t.textContent = t.textContent.replace(
            /AI Translation System/g,
            brand.system_name,
          );
        }
      });
    }
  }

  function applyContact(contact) {
    if (!contact || !contact.support_email) return;
    var email = contact.support_email;
    document.querySelectorAll('a[href^="mailto:"]').forEach(function (a) {
      a.href = "mailto:" + email;
      if (a.textContent.indexOf("@") !== -1) a.textContent = email;
    });
  }

  function applyPlans(plans) {
    if (!plans) return;
    window.SITE_PLAN_CAPS = window.SITE_PLAN_CAPS || {};
    ["free", "pro", "promax"].forEach(function (key) {
      if (plans[key] && plans[key].token_cap != null) {
        window.SITE_PLAN_CAPS[key] = parseInt(plans[key].token_cap, 10);
      }
    });

    var pro = plans.pro || {};
    var promax = plans.promax || {};
    var free = plans.free || {};

    document
      .querySelectorAll(".upgrade-plan-card.pro-card .price-amount")
      .forEach(function (el) {
        el.textContent = formatVnd(pro.price_vnd);
      });
    document
      .querySelectorAll(".upgrade-plan-card.promax-card .price-amount")
      .forEach(function (el) {
        el.textContent = formatVnd(promax.price_vnd);
      });
    document
      .querySelectorAll(".upgrade-plan-card.free-card .plan-features li")
      .forEach(function (el, i) {
        if (i === 0 && free.token_cap) {
          el.innerHTML =
            '<i class="fas fa-check"></i> ' +
            formatVnd(free.token_cap) +
            " token khởi đầu";
        }
      });
    document
      .querySelectorAll(".upgrade-plan-card.pro-card .plan-features li")
      .forEach(function (el, i) {
        if (i === 0 && pro.token_cap) {
          el.innerHTML =
            '<i class="fas fa-check"></i> <strong>' +
            formatVnd(pro.token_cap) +
            " token</strong>";
        }
      });
    document
      .querySelectorAll(".upgrade-plan-card.promax-card .plan-features li")
      .forEach(function (el, i) {
        if (i === 0 && promax.token_cap) {
          el.innerHTML =
            '<i class="fas fa-check"></i> <strong>' +
            formatVnd(promax.token_cap) +
            " token</strong>";
        }
      });

    var quota = document.getElementById("dailyQuota");
    if (quota && free.token_cap) {
      quota.setAttribute("data-cap", String(free.token_cap));
    }

    applyHomePricing(plans);
  }

  window.loadSiteConfigPublic = function () {
    if (cached) {
      applyBrand(cached.brand);
      applyContact(cached.contact);
      applyPlans(cached.plans);
      return Promise.resolve(cached);
    }
    return fetch("/api/public/site-config")
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (!data) return null;
        cached = data;
        applyBrand(data.brand);
        applyContact(data.contact);
        applyPlans(data.plans);
        return data;
      })
      .catch(function () {
        return null;
      });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      window.loadSiteConfigPublic();
    });
  } else {
    window.loadSiteConfigPublic();
  }

  window.addEventListener("siteLanguageChanged", function () {
    if (cached) {
      applyBrand(cached.brand);
      applyContact(cached.contact);
      applyPlans(cached.plans);
      return;
    }
    window.loadSiteConfigPublic();
  });
})();
