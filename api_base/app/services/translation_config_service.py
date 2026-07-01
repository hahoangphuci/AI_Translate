"""Translation API model config — stored in frontend/config/translation_config.json."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_API_BASE = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _API_BASE.parent / "frontend" / "config" / "translation_config.json"

BUILTIN_MODEL_IDS = frozenset({"google", "deepl", "gemini"})

_BUILTIN_MODELS = [
    {
        "id": "google",
        "label": "Google Translate",
        "engine": "google",
        "model": "",
        "api_key": "",
        "plans": ["free", "pro", "promax"],
        "enabled": True,
        "builtin": True,
    },
    {
        "id": "deepl",
        "label": "DeepL",
        "engine": "deepl",
        "model": "",
        "api_key": "",
        "plans": ["pro", "promax"],
        "enabled": True,
        "builtin": True,
    },
    {
        "id": "gemini",
        "label": "Gemini 2.5 Flash (OpenRouter)",
        "engine": "openrouter",
        "model": "google/gemini-2.5-flash",
        "api_key": "",
        "plans": ["promax"],
        "enabled": True,
        "builtin": True,
    },
]

_DEFAULT_CONFIG = {
    "custom_models": [],
    "default_by_plan": {
        "free": "google",
        "pro": "google",
        "promax": "gemini",
    },
}

_MASK_PATTERN = re.compile(r"^\*{2,}|.{0,4}\*{4}.{0,4}$")
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


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
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def builtin_models() -> list[dict]:
    return [dict(item) for item in _BUILTIN_MODELS]


def get_all_models(cfg: dict | None = None) -> list[dict]:
    if cfg is None:
        cfg = load_translation_config()
    custom = [
        dict(m)
        for m in (cfg.get("custom_models") or [])
        if isinstance(m, dict)
    ]
    return builtin_models() + custom


def _migrate_legacy_file(data: dict) -> dict:
    data = dict(data or {})
    if "custom_models" not in data and isinstance(data.get("models"), list):
        data["custom_models"] = [
            m
            for m in data["models"]
            if isinstance(m, dict)
            and str(m.get("id") or "").lower() not in BUILTIN_MODEL_IDS
        ]
    if "custom_models" not in data:
        data["custom_models"] = []
    data.pop("models", None)
    if "providers" in data:
        data.pop("providers")
    return data


def _infer_engine(model: str, item: dict, base: dict) -> str:
    explicit = str(item.get("engine") or base.get("engine") or "").strip().lower()
    if explicit in ("google", "deepl", "openrouter", "gemini", "openai"):
        return explicit
    m = (model or "").strip().lower()
    if m in ("deepl",) or m.startswith("deepl"):
        return "deepl"
    if m in ("google", "google-translate"):
        return "google"
    return "openrouter"


def _slug_from_model(model: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (model or "").strip().lower()).strip("-")
    return slug[:47] if slug else ""


def _normalize_model_item(item: dict, existing: dict | None = None) -> dict | None:
    if not isinstance(item, dict):
        return None
    base = dict(existing or {})

    model = str(
        item.get("model") if "model" in item else (base.get("model") or item.get("label") or base.get("label") or "")
    ).strip()
    if not model:
        return None

    raw_id = str(item.get("id") or base.get("id") or "").strip().lower()
    raw_id = re.sub(r"[^a-z0-9_-]+", "-", raw_id).strip("-")
    if not raw_id:
        raw_id = _slug_from_model(model)
    if not raw_id or not _ID_PATTERN.match(raw_id):
        return None
    if raw_id in BUILTIN_MODEL_IDS:
        return None

    plans_raw = item.get("plans", base.get("plans") or [])
    if not isinstance(plans_raw, list):
        plans_raw = []
    plans: list[str] = []
    for p in plans_raw:
        pn = str(p).strip().lower()
        if pn in ("free", "pro", "promax") and pn not in plans:
            plans.append(pn)
    if not plans:
        plans = ["promax"]

    engine = _infer_engine(model, item, base)

    api_key = str(item.get("api_key") or "").strip()
    if api_key and _is_masked_key(api_key):
        api_key = str(base.get("api_key") or "").strip()

    enabled = bool(item.get("enabled", base.get("enabled", True)))

    return {
        "id": raw_id,
        "label": model,
        "engine": engine,
        "model": model,
        "api_key": api_key,
        "plans": plans,
        "enabled": enabled,
        "builtin": False,
    }


def load_translation_config() -> dict:
    _ensure_config_dir()
    if not _CONFIG_PATH.is_file():
        cfg = dict(_DEFAULT_CONFIG)
        cfg["updated_at"] = _utc_now_iso()
        save_translation_config(cfg)
        out = dict(cfg)
        out["models"] = get_all_models(cfg)
        return out

    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        cfg = dict(_DEFAULT_CONFIG)
        cfg["models"] = get_all_models(cfg)
        return cfg

    data = _migrate_legacy_file(data if isinstance(data, dict) else {})
    merged = _deep_merge(_DEFAULT_CONFIG, data)
    merged["models"] = get_all_models(merged)
    return merged


def save_translation_config(config: dict) -> dict:
    _ensure_config_dir()
    incoming = dict(config or {})
    to_save = {
        "custom_models": incoming.get("custom_models") or [],
        "default_by_plan": incoming.get("default_by_plan")
        or _DEFAULT_CONFIG["default_by_plan"],
        "updated_at": _utc_now_iso(),
    }
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return load_translation_config()


def _mask_api_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _is_masked_key(value: str) -> bool:
    return bool(_MASK_PATTERN.search((value or "").strip()))


def _enabled_models(cfg: dict | None = None) -> list[dict]:
    if cfg is None:
        cfg = load_translation_config()
    models = []
    for item in get_all_models(cfg):
        if isinstance(item, dict) and item.get("enabled", True):
            models.append(item)
    return models


def validate_translation_api_key(engine: str, model: str, api_key: str) -> tuple[bool, str]:
    key = (api_key or "").strip()
    if not key:
        return False, "API Key không được để trống."
    if _is_masked_key(key):
        return True, "OK"

    engine_norm = (engine or "openrouter").strip().lower()
    model_id = (model or "google/gemini-2.5-flash").strip() or "google/gemini-2.5-flash"

    if engine_norm == "deepl":
        try:
            import deepl

            translator = deepl.Translator(key)
            translator.translate_text("hello", target_lang="EN-US")
            return True, "OK"
        except Exception as exc:
            return False, f"DeepL API Key không hợp lệ hoặc không dùng được: {exc}"

    if engine_norm in ("openrouter", "openai", "gemini"):
        payload = json.dumps(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                if resp.status >= 400:
                    return False, f"OpenRouter trả về lỗi HTTP {resp.status}."
            return True, "OK"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace") if exc.fp else str(exc)
            detail = body[:240] if body else str(exc)
            return False, f"API Key hoặc model không hợp lệ (HTTP {exc.code}): {detail}"
        except Exception as exc:
            return False, f"Không kết nối được API: {exc}"

    if engine_norm == "google":
        return True, "OK"

    return False, f"Engine '{engine_norm}' chưa hỗ trợ kiểm tra tự động."


def admin_translation_config() -> dict:
    cfg = load_translation_config()
    custom_models = []
    for item in cfg.get("custom_models") or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["api_key"] = _mask_api_key(row.get("api_key") or "")
        custom_models.append(row)
    return {
        "custom_models": custom_models,
        "builtin_models": [
            {"id": m["id"], "label": m["label"], "plans": m["plans"]}
            for m in builtin_models()
        ],
        "default_by_plan": cfg.get("default_by_plan") or {},
        "updated_at": cfg.get("updated_at"),
    }


def update_translation_config(patch: dict) -> tuple[bool, str, dict | None]:
    current = load_translation_config()
    incoming = patch or {}
    existing_by_id = {
        str(m.get("id") or "").strip().lower(): m
        for m in (current.get("custom_models") or [])
        if isinstance(m, dict) and m.get("id")
    }

    incoming_models = incoming.get("custom_models")
    if incoming_models is None and isinstance(incoming.get("models"), list):
        incoming_models = [
            m
            for m in incoming["models"]
            if str((m or {}).get("id") or "").lower() not in BUILTIN_MODEL_IDS
        ]

    if isinstance(incoming_models, list):
        normalized: list[dict] = []
        seen_ids: set[str] = set()
        for item in incoming_models:
            mid = str((item or {}).get("id") or "")
            existing = existing_by_id.get(mid.strip().lower()) or {}
            merged_item = {**existing, **(item or {})}
            row = _normalize_model_item(merged_item, existing)
            if not row:
                continue
            base_id = row["id"]
            candidate = base_id
            suffix = 2
            while candidate in seen_ids:
                tail = f"-{suffix}"
                candidate = f"{base_id[: max(1, 47 - len(tail))]}{tail}"
                suffix += 1
            row["id"] = candidate
            seen_ids.add(candidate)

            prev_key = str(existing.get("api_key") or "").strip()
            new_key = str(row.get("api_key") or "").strip()
            should_validate = bool(new_key) and new_key != prev_key and not _is_masked_key(new_key)
            if should_validate:
                ok, msg = validate_translation_api_key(
                    row.get("engine"),
                    row.get("model"),
                    new_key,
                )
                if not ok:
                    label = row.get("label") or row.get("id")
                    return False, f"{label}: {msg}", None

            normalized.append(row)
        current["custom_models"] = normalized

    if isinstance(incoming.get("default_by_plan"), dict):
        current["default_by_plan"] = {
            **(current.get("default_by_plan") or {}),
            **incoming["default_by_plan"],
        }

    save_translation_config(current)
    return True, "Đã lưu cấu hình API dịch.", {"config": admin_translation_config()}


def get_model_by_id(model_id: str) -> dict | None:
    mid = (model_id or "").strip().lower()
    for item in get_all_models():
        if str(item.get("id") or "").lower() == mid:
            return item
    return None


def get_provider_api_key(provider: str) -> str:
    item = get_model_by_id(provider)
    if not item:
        return ""
    return str(item.get("api_key") or "").strip()


def get_provider_model(provider: str) -> str:
    item = get_model_by_id(provider)
    if not item:
        return ""
    return str(item.get("model") or "").strip()


def get_model_engine(provider: str) -> str:
    item = get_model_by_id(provider)
    if not item:
        return ""
    return str(item.get("engine") or "").strip().lower()


def providers_for_plan(plan: str) -> list[str]:
    plan_norm = (plan or "free").strip().lower()
    if plan_norm not in ("free", "pro", "promax"):
        plan_norm = "free"
    result: list[str] = []
    for item in _enabled_models():
        plans = [str(p).lower() for p in (item.get("plans") or [])]
        if plan_norm in plans:
            result.append(str(item.get("id") or ""))
    return result or ["google"]


def default_provider_for_plan(plan: str) -> str:
    plan_norm = (plan or "free").strip().lower()
    cfg = load_translation_config()
    default = (cfg.get("default_by_plan") or {}).get(plan_norm) or "google"
    allowed = providers_for_plan(plan_norm)
    if default in allowed:
        return default
    return allowed[0] if allowed else "google"


def provider_allowed_for_plan(plan: str, provider: str) -> bool:
    provider_norm = (provider or "").strip().lower()
    if provider_norm in ("gg", "ggtranslate", "googletranslate"):
        provider_norm = "google"
    return provider_norm in providers_for_plan(plan)


def public_translation_providers() -> dict:
    cfg = load_translation_config()
    models = []
    for item in _enabled_models(cfg):
        models.append(
            {
                "id": item.get("id"),
                "label": item.get("label") or item.get("id"),
                "engine": item.get("engine") or "",
                "model": item.get("model") or "",
                "plans": item.get("plans") or [],
                "builtin": bool(item.get("builtin")),
            }
        )
    return {
        "models": models,
        "default_by_plan": cfg.get("default_by_plan") or {},
        "updated_at": cfg.get("updated_at"),
    }
