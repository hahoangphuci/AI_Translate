"""Public endpoints (no auth) — site-wide stats for landing pages."""

import os

from flask import Blueprint, jsonify, request

from app.models import db, User, Translation

public_bp = Blueprint("public", __name__)

# Khớp frontend/js/languages.js (~104 ngôn ngữ, không tính "auto")
SUPPORTED_LANGUAGES_COUNT = int(os.getenv("SUPPORTED_LANGUAGES_COUNT", "104"))


@public_bp.route("/stats", methods=["GET"])
def public_stats():
    """Aggregate counters for homepage / marketing sections."""
    try:
        translations_completed = Translation.query.count()
        total_users = User.query.filter(User.account_status != "deleted").count()
        languages_count = SUPPORTED_LANGUAGES_COUNT
    except Exception as exc:
        return jsonify({"error": "Failed to load stats", "detail": str(exc)}), 500

    return jsonify(
        {
            "translations_completed": translations_completed,
            "total_users": total_users,
            "languages_count": languages_count,
        }
    ), 200


@public_bp.route("/site-config", methods=["GET"])
def public_site_config():
    """Branding, contact, plan caps for frontend (no auth)."""
    from app.services.site_config_service import public_site_config as load_public
    return jsonify(load_public()), 200


@public_bp.route("/site-config/legal-pages-en", methods=["GET"])
def public_legal_pages_en():
    """English HTML bodies for policy pages (no auth)."""
    from app.services.site_config_service import public_legal_pages_en as load_en
    return jsonify(load_en()), 200


@public_bp.route("/legal-content/<slug>", methods=["GET"])
def public_legal_content(slug):
    """Single policy page body by language (no auth)."""
    from app.services.site_config_service import public_legal_page_content
    lang = request.args.get("lang", "en")
    ok, message, meta = public_legal_page_content(slug, lang=lang)
    if not ok:
        return jsonify({"message": message}), 404
    return jsonify(meta), 200


@public_bp.route("/translation-providers", methods=["GET"])
def public_translation_providers():
    """Built-in + custom translation APIs and plan availability (no auth)."""
    from app.services.translation_config_service import public_translation_providers as load_providers
    return jsonify(load_providers()), 200
