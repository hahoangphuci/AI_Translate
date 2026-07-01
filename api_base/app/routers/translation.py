from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, Translation, User
from app.services.translation_service import TranslationService
from werkzeug.utils import secure_filename
import os
import re
import uuid

translation_bp = Blueprint('translation', __name__)
translation_service = None


def _get_translation_service():
    global translation_service
    if translation_service is None:
        translation_service = TranslationService()
    return translation_service


def _resolve_user(identity):
    """JWT identity = google_id (Google OAuth) hoặc str(user.id) (email/password)."""
    if not identity:
        return None
    user = User.query.filter_by(google_id=identity).first()
    if user:
        return user
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (TypeError, ValueError):
        return None


def _count_tokens_from_text(value):
    text = str(value or "").strip()
    if not text:
        return 1
    return max(1, len(re.findall(r"\S+", text)))


def _estimate_document_tokens(file_path):
    try:
        size_bytes = os.path.getsize(file_path)
    except Exception:
        size_bytes = 0
    size_kb = max(1, int((size_bytes + 1023) / 1024))
    return max(200, size_kb * 3)


def _is_admin(user):
    if not user:
        return False
    return str(getattr(user, "role", "") or "").strip().lower() == "admin"


def _has_enough_tokens(user, needed_tokens):
    if not user:
        return True, None
    balance = int(user.token_balance or 0)
    if _is_admin(user):
        return True, balance
    return balance >= int(needed_tokens), balance


def _deduct_tokens(user, token_cost):
    if user and not _is_admin(user):
        user.token_balance = int(user.token_balance or 0) - int(token_cost)


def _refund_tokens(user, token_cost):
    if user and not _is_admin(user):
        user.token_balance = int(user.token_balance or 0) + int(token_cost)


def _user_plan(user) -> str:
    if not user:
        return "free"
    plan = str(getattr(user, "plan", None) or "free").strip().lower()
    return plan if plan in ("free", "pro", "promax") else "free"


def _resolve_translation_provider(user, requested: str | None) -> str:
    from app.services.translation_config_service import (
        default_provider_for_plan,
        provider_allowed_for_plan,
        providers_for_plan,
    )

    plan = _user_plan(user)
    provider = (requested or "").strip() or None
    if not provider:
        return default_provider_for_plan(plan)
    if not provider_allowed_for_plan(plan, provider):
        allowed = providers_for_plan(plan)
        raise ValueError(
            f"Gói {plan.upper()} chỉ dùng được: {', '.join(allowed)}."
        )
    return provider

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@translation_bp.route('/detect', methods=['POST'])
@jwt_required(optional=True)
def detect_language():
    svc = _get_translation_service()
    data = request.json
    text = data.get('text') if data else None

    if not text or not str(text).strip():
        return jsonify({"error": "No text provided"}), 400

    try:
        result = svc.detect_language(str(text))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    return jsonify(result), 200


@translation_bp.route('/text', methods=['POST'])
@jwt_required(optional=True)
def translate_text():
    svc = _get_translation_service()
    data = request.json
    text = data.get('text')
    source_lang = data.get('source_lang', 'auto')
    target_lang = data.get('target_lang')
    translation_provider = ((data.get('translation_provider') if data else None) or '').strip() or None

    if not text or not str(text).strip():
        return jsonify({"error": "No text provided"}), 400
    if not target_lang or not str(target_lang).strip():
        return jsonify({"error": "target_lang is required"}), 400

    user = _resolve_user(get_jwt_identity())

    is_html = data.get('is_html', False)
    cost_source_text = re.sub(r"<[^>]+>", " ", str(text)) if is_html else str(text)
    token_cost = _count_tokens_from_text(cost_source_text)

    can_translate, balance = _has_enough_tokens(user, token_cost)
    if not can_translate:
        return jsonify({
            "error": "Insufficient tokens",
            "required_tokens": token_cost,
            "token_balance": int(balance or 0),
        }), 402

    try:
        translation_provider = _resolve_translation_provider(user, translation_provider)
    except ValueError as e:
        return jsonify({"error": str(e)}), 403

    try:
        if is_html:
            translated_text = svc.translate_html(text, source_lang, target_lang, provider=translation_provider)
        else:
            translated_text = svc.translate_text(text, source_lang, target_lang, provider=translation_provider)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    _deduct_tokens(user, token_cost)

    translation = Translation(
        user_id=user.id if user else None,
        type='text',
        original_text=(text[:5000] + '...') if len(text) > 5000 else text,
        translated_text=(translated_text[:5000] + '...') if len(translated_text) > 5000 else translated_text,
        source_lang=source_lang,
        target_lang=target_lang,
        token_cost=token_cost,
    )
    db.session.add(translation)
    db.session.commit()

    return jsonify({
        "translated_text": translated_text,
        "is_html": bool(is_html),
        "token_cost": token_cost,
        "token_balance": int(user.token_balance) if user else None,
    }), 200

@translation_bp.route('/document', methods=['POST'])
@jwt_required(optional=True)
def translate_document():
    svc = _get_translation_service()
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    target_lang = request.form.get('target_lang')

    if not target_lang or not str(target_lang).strip():
        return jsonify({"error": "target_lang is required"}), 400
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    allowed_doc = {'.docx', '.pdf'}
    if ext not in allowed_doc:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, filename))
        except Exception:
            pass
        return jsonify({
            "error": "Unsupported file type",
            "message": "Chỉ hỗ trợ PDF và Word (.docx).",
        }), 400

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    user_id = get_jwt_identity()
    user = _resolve_user(user_id)

    token_cost = _estimate_document_tokens(filepath)
    can_translate, balance = _has_enough_tokens(user, token_cost)
    if not can_translate:
        try:
            os.remove(filepath)
        except Exception:
            pass
        return jsonify({
            "error": "Insufficient tokens",
            "required_tokens": token_cost,
            "token_balance": int(balance or 0),
        }), 402

    _deduct_tokens(user, token_cost)

    # Create DB record indicating processing started
    translation = Translation(
        user_id=user.id if user else None,
        type='document',
        original_text=f"File: {filename}",
        translated_text=f"Processing file...",
        source_lang='auto',
        target_lang=target_lang,
        file_path=filepath,
        token_cost=token_cost,
    )
    db.session.add(translation)
    db.session.commit()

    # Extract optional bilingual / OCR parameters sent by the frontend
    bilingual_mode = (request.form.get('bilingual_mode') or '').strip() or None
    bilingual_delimiter = (request.form.get('bilingual_delimiter') or '').strip() or None
    ocr_images = (request.form.get('ocr_images') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    ocr_mode = (request.form.get('ocr_mode') or '').strip() or None
    ocr_langs = (request.form.get('ocr_langs') or '').strip() or None
    translation_provider = (request.form.get('translation_provider') or '').strip() or None
    print(f"[translate_document] bilingual_mode={bilingual_mode!r}, bilingual_delimiter={bilingual_delimiter!r}, ext={ext}")

    try:
        translation_provider = _resolve_translation_provider(user, translation_provider)
    except ValueError as e:
        _refund_tokens(user, token_cost)
        db.session.commit()
        try:
            os.remove(filepath)
        except Exception:
            pass
        return jsonify({"error": str(e)}), 403

    # Start background job
    try:
        job_id = svc.translate_document_background(
            filepath, target_lang, user_id=user_id,
            ocr_images=ocr_images, ocr_langs=ocr_langs, ocr_mode=ocr_mode,
            bilingual_mode=bilingual_mode, bilingual_delimiter=bilingual_delimiter,
            translation_provider=translation_provider,
        )
    except Exception as e:
        _refund_tokens(user, token_cost)
        db.session.commit()
        return jsonify({"error": f"Unable to start translation job: {str(e)}"}), 500

    return jsonify({
        "job_id": job_id,
        "status_url": f"/api/translation/document/status/{job_id}",
        "token_cost": token_cost,
        "token_balance": int(user.token_balance) if user else None,
    }), 202


@translation_bp.route('/image', methods=['POST'])
@jwt_required(optional=True)
def translate_image():
    """Translate text from an uploaded image using OCR."""
    svc = _get_translation_service()
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if not file or not file.filename:
        return jsonify({"error": "No file selected"}), 400

    source_lang = (request.form.get('source_lang') or 'auto').strip() or 'auto'
    target_lang = (request.form.get('target_lang') or '').strip()
    ocr_langs = (request.form.get('ocr_langs') or '').strip() or None
    translation_provider = (request.form.get('translation_provider') or '').strip() or None
    mode = (request.form.get('mode') or 'auto').strip().lower()
    if mode not in ('auto', 'text', 'image', 'both'):
        mode = 'auto'

    render_raw = request.form.get('render')
    if render_raw is None:
        render_raw = request.form.get('render_overlay')
    if render_raw is None:
        render_overlay = mode in ('auto', 'image', 'both')
        force_render = False
    else:
        render_overlay = str(render_raw).strip().lower() in ('1', 'true', 'yes', 'on')
        force_render = render_overlay

    if not target_lang:
        return jsonify({"error": "target_lang is required"}), 400

    user_id = get_jwt_identity()
    user = _resolve_user(user_id)

    # Basic extension allowlist
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    allowed = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp'}
    if ext not in allowed:
        return jsonify({"error": "Unsupported image type. Use png/jpg/jpeg/bmp/tiff/webp."}), 400

    # Save to uploads with unique prefix
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(filepath)

    try:
        translation_provider = _resolve_translation_provider(user, translation_provider)
    except ValueError as e:
        try:
            os.remove(filepath)
        except Exception:
            pass
        return jsonify({"error": str(e)}), 403

    try:
        svc.set_request_translation_provider(translation_provider)

        rendered_image_data_url = None
        output_mode = mode

        if render_overlay:
            overlay_out = svc.ocr_translate_overlay(
                filepath,
                source_lang=source_lang,
                target_lang=target_lang,
                ocr_langs=ocr_langs,
            )

            if not isinstance(overlay_out, tuple):
                raise RuntimeError("Invalid OCR overlay response")

            if len(overlay_out) >= 4:
                ocr_text, translated_text, png_bytes, recommended_mode = overlay_out[:4]
            elif len(overlay_out) == 3:
                ocr_text, translated_text, png_bytes = overlay_out
                recommended_mode = 'image'
            else:
                raise RuntimeError("Invalid OCR overlay response shape")

            if not ocr_text or not str(ocr_text).strip():
                return jsonify({"error": "OCR found no text in the image."}), 400

            if mode == 'auto':
                output_mode = str(recommended_mode or 'text').strip().lower()
                if output_mode not in ('text', 'image', 'both'):
                    output_mode = 'text'

            include_rendered_image = bool(
                force_render
                or mode in ('auto', 'image', 'both')
                or output_mode in ('image', 'both')
            )

            import base64
            if include_rendered_image and png_bytes:
                rendered_image_data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode('ascii')
                if mode == 'auto' and output_mode == 'text':
                    output_mode = 'both'
        else:
            ocr_text = svc.ocr_image_to_text(filepath, ocr_langs=ocr_langs)
            if not ocr_text or not str(ocr_text).strip():
                return jsonify({"error": "OCR found no text in the image."}), 400
            translated_text = svc.translate_text(ocr_text, source_lang, target_lang, provider=translation_provider)
            output_mode = 'text'
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    finally:
        svc.clear_request_translation_provider()
        # Best-effort cleanup
        try:
            os.remove(filepath)
        except Exception:
            pass

    token_cost = _count_tokens_from_text(ocr_text)
    can_translate, balance = _has_enough_tokens(user, token_cost)
    if not can_translate:
        return jsonify({
            "error": "Insufficient tokens",
            "required_tokens": token_cost,
            "token_balance": int(balance or 0),
        }), 402

    _deduct_tokens(user, token_cost)

    # Persist translation history
    translation = Translation(
        user_id=user.id if user else None,
        type='image',
        original_text=(ocr_text[:5000] + '...') if len(ocr_text) > 5000 else ocr_text,
        translated_text=(translated_text[:5000] + '...') if len(translated_text) > 5000 else translated_text,
        source_lang=source_lang,
        target_lang=target_lang,
        token_cost=token_cost,
    )
    db.session.add(translation)
    db.session.commit()

    payload = {
        "ocr_text": ocr_text,
        "translated_text": translated_text,
        "mode": output_mode,
        "is_html": False,
        "token_cost": token_cost,
        "token_balance": int(user.token_balance) if user else None,
    }
    if rendered_image_data_url:
        payload["rendered_image"] = rendered_image_data_url
    return jsonify(payload), 200

@translation_bp.route('/document/status/<job_id>', methods=['GET'])
@jwt_required(optional=True)
def document_status(job_id):
    svc = _get_translation_service()
    job = svc.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    # When completed, include download_url
    download_url = None
    if job.get('status') == 'completed' and job.get('download_path'):
        download_url = f"/downloads/{os.path.basename(job.get('download_path'))}"
    return jsonify({
        'job_id': job_id,
        'status': job.get('status'),
        'progress': job.get('progress'),
        'message': job.get('message'),
        'download_url': download_url,
        'error': job.get('error'),
        'fallback': job.get('fallback', False),
        'fallback_reason': job.get('fallback_reason')
    }), 200


@translation_bp.route('/save', methods=['POST'])
@jwt_required()
def save_translation():
    """Explicitly save a translation from the dashboard UI.

    Note: /text already persists translations; this endpoint exists to keep the
    dashboard "Lưu" button functional and supports idempotent re-saves.
    """
    data = request.get_json(silent=True) or {}
    original_text = data.get('original_text')
    translated_text = data.get('translated_text')
    source_lang = (data.get('source_lang') or 'auto').strip() if data.get('source_lang') else 'auto'
    target_lang = data.get('target_lang')

    if not original_text or not str(original_text).strip():
        return jsonify({'error': 'original_text is required'}), 400
    if not translated_text or not str(translated_text).strip():
        return jsonify({'error': 'translated_text is required'}), 400
    if not target_lang or not str(target_lang).strip():
        return jsonify({'error': 'target_lang is required'}), 400

    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Best-effort idempotency: if the same record was saved very recently, reuse it.
    from datetime import datetime, timedelta
    window_start = datetime.utcnow() - timedelta(minutes=2)
    existing = Translation.query.filter(
        Translation.user_id == user.id,
        Translation.source_lang == source_lang,
        Translation.target_lang == target_lang,
        Translation.created_at >= window_start,
        Translation.original_text == original_text,
        Translation.translated_text == translated_text,
    ).order_by(Translation.created_at.desc()).first()
    if existing:
        return jsonify({'message': 'already_saved', 'id': existing.id}), 200

    translation = Translation(
        user_id=user.id,
        type='text',
        original_text=(str(original_text)[:5000] + '...') if len(str(original_text)) > 5000 else str(original_text),
        translated_text=(str(translated_text)[:5000] + '...') if len(str(translated_text)) > 5000 else str(translated_text),
        source_lang=source_lang,
        target_lang=str(target_lang).strip(),
    )
    db.session.add(translation)
    db.session.commit()
    return jsonify({'message': 'saved', 'id': translation.id}), 201


@translation_bp.route('/history', methods=['GET'])
@jwt_required(optional=True)
def get_history():
    user = _resolve_user(get_jwt_identity())
    if not user:
        return jsonify({'translations': [], 'total': 0, 'pages': 0, 'current_page': 1}), 200

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    filter_type = (request.args.get('type') or 'all').strip().lower()
    date_str = (request.args.get('date') or '').strip()

    q = Translation.query.filter(Translation.user_id == user.id)

    # Filter by type (text/document)
    if filter_type == 'text':
        q = q.filter(Translation.file_path.is_(None))
    elif filter_type == 'document':
        q = q.filter(Translation.file_path.isnot(None))

    # Optional date filter: YYYY-MM-DD (UTC date)
    if date_str:
        from datetime import datetime
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            q = q.filter(db.func.date(Translation.created_at) == d)
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    q = q.order_by(Translation.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    history = [{
        'id': t.id,
        'original_text': t.original_text,
        'translated_text': t.translated_text,
        'source_lang': t.source_lang,
        'target_lang': t.target_lang,
        'created_at': t.created_at.isoformat(),
        'has_file': bool(t.file_path)
    } for t in pagination.items]

    return jsonify({
        'translations': history,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
    }), 200