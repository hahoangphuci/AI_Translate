"""Site-wide policy/branding config — stored in JSON + HTML files (no database)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

_API_BASE = Path(__file__).resolve().parents[2]
_FRONTEND = _API_BASE.parent / "frontend"
_CONFIG_DIR = _FRONTEND / "config"
_SITE_CONFIG_PATH = _CONFIG_DIR / "site_config.json"
_PACKAGES_PATH = _CONFIG_DIR / "packages.json"
_LEGAL_EN_PATH = _CONFIG_DIR / "legal_pages_en.json"
_PAGES_DIR = _FRONTEND / "pages"

MANAGED_PAGES = {
    "privacy": {"filename": "privacy.html", "kind": "legal", "url": "/privacy"},
    "terms": {"filename": "terms.html", "kind": "legal", "url": "/terms"},
    "ai-terms": {"filename": "ai-terms.html", "kind": "legal", "url": "/ai-terms"},
    "payment-policy": {"filename": "payment-policy.html", "kind": "legal", "url": "/payment-policy"},
    "data-deletion": {"filename": "data-deletion.html", "kind": "legal", "url": "/data-deletion"},
    "support": {"filename": "support.html", "kind": "legal", "url": "/support"},
    "home": {"filename": "home.html", "kind": "main", "url": "/"},
    "contact": {"filename": "contact.html", "kind": "main", "url": "/contact"},
}

LEGAL_PAGES = {
    slug: meta["filename"]
    for slug, meta in MANAGED_PAGES.items()
    if meta["kind"] == "legal"
}

_ARTICLE_PATTERN = re.compile(
    r'(<article\s+class="legal-content glassmorphism">)(.*?)(</article>)',
    re.DOTALL | re.IGNORECASE,
)

_MAIN_MARKERS_PATTERN = re.compile(
    r"(<!--\s*page-main-start\s*-->)(.*?)(<!--\s*page-main-end\s*-->)",
    re.DOTALL | re.IGNORECASE,
)

_NAV_FOOTER_PATTERN = re.compile(
    r"(</nav>\s*)(.*?)(\s*<footer\b)",
    re.DOTALL | re.IGNORECASE,
)

_DEFAULT_CONFIG = {
    "brand": {
        "name": "AI Translator",
        "system_name": "AI Translation System",
        "logo_type": "icon",
        "logo_icon": "fa-language",
        "logo_image_url": "",
    },
    "contact": {
        "support_email": "support@aitranslator.vn",
        "company_name": "[Tên công ty hoặc cá nhân đăng ký]",
        "company_address": "[Địa chỉ liên hệ]",
        "website_url": "[https://yourdomain.com]",
    },
    "plans": {
        "free": {"label": "Free", "token_cap": 5000, "price_vnd": 0},
        "pro": {"label": "Pro", "token_cap": 120000, "price_vnd": 99000},
        "promax": {"label": "ProMax", "token_cap": 300000, "price_vnd": 199000},
    },
    "payment": {
        "bank_code": "MB",
        "bank_account": "",
        "bank_account_name": "",
        "qr_template_url": "https://qr.sepay.vn/img?acc={account_number}&bank={bank_code}&amount={amount}&des={content}&template=compact",
    },
    "prompts": {
        "ai_terms": "",
        "privacy_payment": "",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, val in (patch or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _ensure_config_dir() -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_site_config() -> dict:
    _ensure_config_dir()
    if not _SITE_CONFIG_PATH.is_file():
        cfg = dict(_DEFAULT_CONFIG)
        cfg["updated_at"] = _utc_now_iso()
        save_site_config(cfg)
        return cfg
    try:
        with open(_SITE_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _deep_merge(_DEFAULT_CONFIG, data if isinstance(data, dict) else {})
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_CONFIG)


def save_site_config(config: dict) -> dict:
    _ensure_config_dir()
    merged = _deep_merge(_DEFAULT_CONFIG, config or {})
    merged["updated_at"] = _utc_now_iso()
    with open(_SITE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        f.write("\n")
    sync_packages_json(merged.get("plans") or {})
    return merged


def load_packages_config() -> dict:
    _ensure_config_dir()
    if _PACKAGES_PATH.is_file():
        try:
            with open(_PACKAGES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
    site = load_site_config()
    sync_packages_json(site.get("plans") or {})
    try:
        with open(_PACKAGES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def load_payment_config() -> dict:
    """Bank/QR settings for SePay — env vars win; site_config.json is fallback for Azure deploy."""
    cfg = load_site_config().get("payment") or {}
    default_qr = (
        "https://qr.sepay.vn/img?acc={account_number}&bank={bank_code}"
        "&amount={amount}&des={content}&template=compact"
    )
    return {
        "bank_code": (cfg.get("bank_code") or "MB").strip().upper(),
        "bank_account": (cfg.get("bank_account") or "").strip(),
        "bank_account_name": (cfg.get("bank_account_name") or "").strip(),
        "qr_template_url": (cfg.get("qr_template_url") or default_qr).strip(),
    }


def sync_packages_json(plans: dict) -> None:
    packages = {}
    pro = plans.get("pro") or {}
    promax = plans.get("promax") or {}
    if pro:
        packages["pro"] = {
            "package_id": "pro",
            "plan": "pro",
            "name": pro.get("label") or "Pro",
            "amount_vnd": int(pro.get("price_vnd") or 99000),
            "token_amount": int(pro.get("token_cap") or 120000),
        }
    if promax:
        packages["promax"] = {
            "package_id": "promax",
            "plan": "promax",
            "name": promax.get("label") or "ProMax",
            "amount_vnd": int(promax.get("price_vnd") or 199000),
            "token_amount": int(promax.get("token_cap") or 300000),
        }
    _ensure_config_dir()
    with open(_PACKAGES_PATH, "w", encoding="utf-8") as f:
        json.dump(packages, f, ensure_ascii=False, indent=2)
        f.write("\n")


def public_site_config() -> dict:
    cfg = load_site_config()
    return {
        "brand": cfg.get("brand") or {},
        "contact": cfg.get("contact") or {},
        "plans": cfg.get("plans") or {},
        "updated_at": cfg.get("updated_at"),
    }


def _page_meta(slug: str) -> dict | None:
    return MANAGED_PAGES.get(slug)


_HTML_COMMENT_PATTERN = re.compile(r"<!--[\s\S]*?-->")
_CONTENTEDITABLE_ATTR = re.compile(
    r'\s*contenteditable\s*=\s*["\']?(?:true|false)["\']?',
    re.IGNORECASE,
)
_SPELLCHECK_ATTR = re.compile(
    r'\s*spellcheck\s*=\s*["\']?(?:true|false)["\']?',
    re.IGNORECASE,
)
_CMS_CLASS_TOKENS = frozenset({"cms-editing", "cms-text-editable"})


def _strip_cms_class_tokens(class_value: str) -> str:
    tokens = [
        token
        for token in (class_value or "").split()
        if token and token not in _CMS_CLASS_TOKENS
    ]
    return " ".join(tokens)


def _clean_cms_classes_in_html(html: str) -> str:
    def repl(match: re.Match) -> str:
        cleaned = _strip_cms_class_tokens(match.group(1))
        if not cleaned:
            return ""
        return f' class="{cleaned}"'

    return re.sub(r'\sclass="([^"]*)"', repl, html)


def _sanitize_page_html(html: str) -> str:
    """Remove HTML comments and inline-editor artifacts from saved page HTML."""
    text = (html or "").strip()
    if not text:
        return ""
    text = _HTML_COMMENT_PATTERN.sub("", text).strip()
    text = _CONTENTEDITABLE_ATTR.sub("", text)
    text = _SPELLCHECK_ATTR.sub("", text)
    text = _clean_cms_classes_in_html(text)
    return text.strip()


def _auto_translate_vi_to_en(html: str) -> str:
    body = _sanitize_page_html(html)
    if not body:
        return ""
    try:
        from app.services.translation_service import TranslationService

        svc = TranslationService()
        translated = svc.translate_html(body, "vi", "en", provider="google")
        return (translated or "").strip()
    except Exception:
        return ""


def _auto_translate_en_to_vi(html: str) -> str:
    body = _sanitize_page_html(html)
    if not body:
        return ""
    try:
        from app.services.translation_service import TranslationService

        svc = TranslationService()
        translated = svc.translate_html(body, "en", "vi", provider="google")
        return (translated or "").strip()
    except Exception:
        return ""


def _sync_en_from_vi(slug: str, vi_html: str) -> None:
    en_html = _auto_translate_vi_to_en(vi_html)
    if not en_html:
        return
    en_pages = load_legal_pages_en()
    en_pages[slug] = en_html
    save_legal_pages_en(en_pages)


def _sync_vi_from_en(slug: str, en_html: str) -> None:
    meta = _page_meta(slug)
    if not meta:
        return
    vi_html = _auto_translate_en_to_vi(en_html)
    if not vi_html:
        return

    filename = meta["filename"]
    path = _PAGES_DIR / filename
    if not path.is_file():
        return
    html = path.read_text(encoding="utf-8")

    if meta.get("kind") == "main":
        ok, updated = _write_main_content(html, vi_html)
        if ok:
            path.write_text(updated, encoding="utf-8")
        return

    match = _ARTICLE_PATTERN.search(html)
    if not match:
        return
    updated = html[: match.start(2)] + "\n          " + vi_html + "\n        " + html[match.end(2) :]
    path.write_text(updated, encoding="utf-8")


def _extract_main_content(html: str) -> tuple[bool, str]:
    match = _MAIN_MARKERS_PATTERN.search(html)
    if match:
        return True, match.group(2).strip()
    match = _NAV_FOOTER_PATTERN.search(html)
    if match:
        return True, match.group(2).strip()
    return False, ""


def _write_main_content(html: str, new_inner: str) -> tuple[bool, str]:
    inner = (new_inner or "").strip()
    if not inner:
        return False, "Nội dung không được để trống."

    match = _MAIN_MARKERS_PATTERN.search(html)
    if match:
        updated = (
            html[: match.start(2)]
            + "\n    "
            + inner
            + "\n    "
            + html[match.end(2) :]
        )
        return True, updated

    match = _NAV_FOOTER_PATTERN.search(html)
    if not match:
        return False, "Không tìm thấy khối nội dung chính (page-main hoặc nav/footer)."
    updated = html[: match.start(2)] + "\n\n    " + inner + "\n\n    " + html[match.end(2) :]
    return True, updated


def list_legal_pages() -> list[dict]:
    items = []
    for slug, meta in MANAGED_PAGES.items():
        filename = meta["filename"]
        path = _PAGES_DIR / filename
        items.append({
            "slug": slug,
            "filename": filename,
            "url": meta.get("url") or f"/{slug}",
            "kind": meta.get("kind") or "legal",
            "exists": path.is_file(),
        })
    return items


def load_legal_pages_en() -> dict:
    _ensure_config_dir()
    if not _LEGAL_EN_PATH.is_file():
        return {}
    try:
        with open(_LEGAL_EN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_legal_pages_en(pages: dict) -> None:
    _ensure_config_dir()
    with open(_LEGAL_EN_PATH, "w", encoding="utf-8") as f:
        json.dump(pages or {}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def public_legal_page_content(slug: str, lang: str = "en") -> tuple[bool, str, dict | None]:
    if slug not in MANAGED_PAGES:
        return False, "Trang không hợp lệ.", None
    meta = _page_meta(slug) or {}
    lang_norm = (lang or "en").strip().lower()
    if lang_norm == "en":
        en_pages = load_legal_pages_en()
        content = (en_pages.get(slug) or "").strip()
        if not content:
            ok, message, vi_meta = get_legal_page_content(slug, lang="vi")
            if ok and vi_meta:
                content = _auto_translate_vi_to_en(vi_meta.get("content") or "")
        return True, "OK", {
            "slug": slug,
            "lang": "en",
            "content": _sanitize_page_html(content),
            "url": meta.get("url") or f"/{slug}",
        }
    ok, message, page_meta = get_legal_page_content(slug, lang="vi")
    return ok, message, page_meta


def public_legal_pages_en() -> dict:
    pages = load_legal_pages_en()
    return {slug: _sanitize_page_html(html) for slug, html in pages.items()}


def get_legal_page_content(slug: str, lang: str = "vi") -> tuple[bool, str, dict | None]:
    meta = _page_meta(slug)
    if not meta:
        return False, "Trang không hợp lệ.", None

    lang_norm = (lang or "vi").strip().lower()
    filename = meta["filename"]
    page_url = meta.get("url") or f"/{slug}"

    if lang_norm == "en":
        en_pages = load_legal_pages_en()
        content = (en_pages.get(slug) or "").strip()
        if not content:
            ok, message, vi_meta = get_legal_page_content(slug, lang="vi")
            if ok and vi_meta:
                content = _auto_translate_vi_to_en(vi_meta.get("content") or "")
        return True, "OK", {
            "slug": slug,
            "lang": "en",
            "filename": filename,
            "url": page_url,
            "content": _sanitize_page_html(content),
        }

    path = _PAGES_DIR / filename
    if not path.is_file():
        return False, "Không tìm thấy file HTML.", None
    html = path.read_text(encoding="utf-8")

    if meta.get("kind") == "main":
        ok, content = _extract_main_content(html)
        if not ok:
            return False, "Không tìm thấy khối nội dung chính trong file.", None
        return True, "OK", {
            "slug": slug,
            "lang": "vi",
            "filename": filename,
            "url": page_url,
            "content": _sanitize_page_html(content),
        }

    match = _ARTICLE_PATTERN.search(html)
    if not match:
        return False, "Không tìm thấy khối nội dung legal-content trong file.", None
    return True, "OK", {
        "slug": slug,
        "lang": "vi",
        "filename": filename,
        "url": page_url,
        "content": _sanitize_page_html(match.group(2).strip()),
    }


def save_legal_page_content(slug: str, content: str, lang: str = "vi") -> tuple[bool, str]:
    meta = _page_meta(slug)
    if not meta:
        return False, "Trang không hợp lệ."

    new_inner = _sanitize_page_html(content)
    if not new_inner:
        return False, "Nội dung không được để trống."

    lang_norm = (lang or "vi").strip().lower()
    page_url = meta.get("url") or f"/{slug}"

    if lang_norm == "en":
        en_pages = load_legal_pages_en()
        en_pages[slug] = new_inner
        save_legal_pages_en(en_pages)
        _sync_vi_from_en(slug, new_inner)
        return True, f"Đã lưu bản tiếng Anh cho {page_url} và tự dịch sang tiếng Việt."

    filename = meta["filename"]
    path = _PAGES_DIR / filename
    if not path.is_file():
        return False, "Không tìm thấy file HTML."
    html = path.read_text(encoding="utf-8")

    if meta.get("kind") == "main":
        ok, updated = _write_main_content(html, new_inner)
        if not ok:
            return False, updated
        path.write_text(updated, encoding="utf-8")
        _sync_en_from_vi(slug, new_inner)
        return True, f"Đã lưu {filename} và tự dịch sang tiếng Anh."

    match = _ARTICLE_PATTERN.search(html)
    if not match:
        return False, "Không tìm thấy khối nội dung legal-content trong file."

    updated = html[: match.start(2)] + "\n          " + new_inner + "\n        " + html[match.end(2) :]
    path.write_text(updated, encoding="utf-8")
    _sync_en_from_vi(slug, new_inner)
    return True, f"Đã lưu {filename} và tự dịch sang tiếng Anh."


def _replace_in_file(path: Path, replacements: list[tuple[str, str]]) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        if old and new is not None and old != new:
            text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def sync_html_from_config(old_cfg: dict, new_cfg: dict) -> list[str]:
    """Replace email, company info, brand names across HTML files."""
    changes: list[str] = []
    old_contact = old_cfg.get("contact") or {}
    new_contact = new_cfg.get("contact") or {}
    old_brand = old_cfg.get("brand") or {}
    new_brand = new_cfg.get("brand") or {}

    replacements: list[tuple[str, str]] = []
    pairs = [
        (old_contact.get("support_email"), new_contact.get("support_email")),
        (old_contact.get("company_name"), new_contact.get("company_name")),
        (old_contact.get("company_address"), new_contact.get("company_address")),
        (old_contact.get("website_url"), new_contact.get("website_url")),
        (old_brand.get("system_name"), new_brand.get("system_name")),
        (old_brand.get("name"), new_brand.get("name")),
    ]
    for old, new in pairs:
        if old and new and old != new:
            replacements.append((old, new))

    if not replacements:
        return changes

    html_roots = [_PAGES_DIR, _FRONTEND]
    seen: set[str] = set()
    for root in html_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.html"):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            if _replace_in_file(path, replacements):
                changes.append(str(path.relative_to(_FRONTEND.parent)))

    return changes


def update_site_config(patch: dict) -> tuple[bool, str, dict | None]:
    old = load_site_config()
    merged = _deep_merge(old, patch or {})
    merged = save_site_config(merged)
    html_changes = sync_html_from_config(old, merged)
    return True, "Đã lưu cấu hình.", {
        "config": merged,
        "html_files_updated": html_changes,
    }
