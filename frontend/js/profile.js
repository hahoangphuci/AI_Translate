document.addEventListener("DOMContentLoaded", function () {
  const nameInput = document.getElementById("profile-name");
  const emailInput = document.getElementById("profile-email");
  const avatarInput = document.getElementById("profile-avatar");
  const bioInput = document.getElementById("profile-bio");
  const avatarCircle = document.getElementById("avatarCircle");

  function escapeHtml(str) {
    return String(str).replace(/[&<>\"]/g, (m) => {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
      }[m];
    });
  }

  function getInitials(name) {
    const s = String(name || "U").trim();
    return (s[0] || "U").toUpperCase();
  }

  function setAvatarPreview(name, avatarUrl) {
    if (!avatarCircle) return;
    const initials = getInitials(name);
    if (!avatarUrl) {
      avatarCircle.textContent = initials;
      return;
    }
    avatarCircle.innerHTML = `<img src="${escapeHtml(avatarUrl)}" alt="avatar" referrerpolicy="no-referrer" />`;
    const img = avatarCircle.querySelector("img");
    if (img) {
      img.onerror = () => {
        avatarCircle.textContent = initials;
      };
    }
  }

  async function loadProfileFromBackendIfPossible() {
    const token = localStorage.getItem("token");
    if (!token || String(token).startsWith("fake")) return null;

    try {
      const res = await fetch("/api/auth/profile", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      console.warn("Failed to fetch /api/auth/profile", e);
      return null;
    }
  }

  async function patchProfileToBackendIfPossible(user) {
    const token = localStorage.getItem("token");
    if (!token || String(token).startsWith("fake")) return null;

    try {
      const res = await fetch("/api/auth/profile", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: user.name,
          avatar_url: user.avatarUrl || "",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Cập nhật backend thất bại");
      }
      return await res.json();
    } catch (e) {
      console.warn("Profile PATCH failed", e);
      return null;
    }
  }

  (async () => {
    let local = null;
    try {
      const cached = localStorage.getItem("user");
      local = cached ? JSON.parse(cached) : null;
    } catch (e) {
      local = null;
    }

    const remote = await loadProfileFromBackendIfPossible();
    const merged = { ...(local || {}), ...(remote || {}) };
    if (remote) localStorage.setItem("user", JSON.stringify(merged));

    if (nameInput && merged.name) nameInput.value = merged.name;
    if (emailInput && merged.email) emailInput.value = merged.email;
    if (avatarInput && (merged.avatarUrl || merged.avatar_url))
      avatarInput.value = merged.avatarUrl || merged.avatar_url;
    if (bioInput && merged.bio) bioInput.value = merged.bio;

    setAvatarPreview(merged.name, merged.avatarUrl || merged.avatar_url);

    // Sync avatar panel display fields
    const avatarNameEl = document.getElementById("avatarName");
    const avatarEmailEl = document.getElementById("avatarEmail");
    if (avatarNameEl && merged.name) avatarNameEl.textContent = merged.name;
    if (avatarEmailEl && merged.email) avatarEmailEl.textContent = merged.email;
  })();

  if (avatarInput) {
    avatarInput.addEventListener("input", () => {
      setAvatarPreview(
        nameInput ? nameInput.value : "",
        avatarInput.value.trim(),
      );
    });
  }

  if (nameInput) {
    nameInput.addEventListener("input", () => {
      setAvatarPreview(
        nameInput.value,
        avatarInput ? avatarInput.value.trim() : "",
      );
    });
  }
  // Saving is handled by window.saveProfile() defined in profile.html
});
