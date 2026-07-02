from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, Payment, User
from app.services.payment_service import PaymentService

payment_bp = Blueprint('payment', __name__)
payment_service = PaymentService()


def _resolve_user(identity):
    """Lookup User from JWT identity.

    Identity can be google_id (Google OAuth) or str(user.id) (email/password).
    """
    user = User.query.filter_by(google_id=identity).first()
    if user:
        return user
    try:
        return User.query.filter_by(id=int(identity)).first()
    except (TypeError, ValueError):
        return None


def _plan_rank(plan_name):
    plan_order = {
        'free': 0,
        'pro': 1,
        'promax': 2,
    }
    return plan_order.get(str(plan_name or '').strip().lower(), 0)


REPURCHASE_TOKEN_THRESHOLD = 0.10


def _can_repurchase_package(user, package):
    """Cho phép mua lại cùng gói khi token còn <= 10% hạn mức gói."""
    if not user or not package:
        return False
    user_plan = str(user.plan or 'free').strip().lower()
    package_plan = str(package.get('plan') or package.get('package_id') or '').strip().lower()
    if user_plan != package_plan or user_plan == 'free':
        return False
    token_amount = int(package.get('token_amount') or 0)
    if token_amount <= 0:
        return False
    balance = int(user.token_balance or 0)
    threshold = max(1, int(token_amount * REPURCHASE_TOKEN_THRESHOLD))
    return balance <= threshold


def _can_purchase_package(user, package_id):
    package = payment_service.get_package(package_id)
    if not package:
        return False, 'Invalid package_id'

    user_plan = str(user.plan or 'free').strip().lower()
    package_plan = str(package.get('plan') or package_id).strip().lower()
    user_rank = _plan_rank(user_plan)
    package_rank = _plan_rank(package_plan)

    if package_rank > user_rank:
        return True, None
    if package_rank == user_rank:
        if _can_repurchase_package(user, package):
            return True, None
        return False, (
            'Bạn còn quá nhiều token. Chỉ có thể mua lại gói này khi token còn lại '
            f'≤ {int(REPURCHASE_TOKEN_THRESHOLD * 100)}% hạn mức gói.'
        )
    return False, 'Không thể mua gói thấp hơn gói hiện tại.'


def _serialize_invoice(payment, package, reused=False):
    hex_id = payment_service.encode_payment_id(payment.id)
    transfer_content = payment_service.build_transfer_content(hex_id)
    expires_at = payment_service.get_expire_at(payment.created_at)
    now = datetime.utcnow()
    remaining_seconds = max(0, int((expires_at - now).total_seconds()))

    return {
        "payment_id": payment.id,
        "hex_id": hex_id,
        "status": payment.status,
        "package_id": package['package_id'] if package else None,
        "package_name": package['name'] if package else None,
        "token_amount": int(package.get('token_amount', 0)) if package else 0,
        "amount_vnd": int(round(float(payment.amount or 0))),
        "currency": payment.currency,
        "transfer_prefix": payment_service.get_transfer_prefix(),
        "transfer_content": transfer_content,
        "qr_image_url": payment_service.get_qr_image_url(payment.amount, transfer_content),
        "bank": {
            "code": payment_service.bank_code,
            "account_number": payment_service.bank_account,
            "account_name": payment_service.bank_account_name,
        },
        "sepay_transaction_id": payment.sepay_transaction_id,
        "created_at": payment.created_at.isoformat() + 'Z',
        "expires_at": expires_at.isoformat() + 'Z',
        "remaining_seconds": remaining_seconds,
        "is_expired": remaining_seconds <= 0,
        "is_reused": bool(reused),
        "server_time": now.isoformat() + 'Z',
    }


def _mark_user_expired_pending(user_id):
    dirty = False
    pending_rows = Payment.query.filter_by(user_id=user_id, status='pending').all()
    for row in pending_rows:
        if payment_service.is_expired(row.created_at):
            row.status = 'failed'
            dirty = True
    if dirty:
        db.session.commit()


def _complete_payment(payment, user, transaction_id=None):
    payment.status = 'completed'
    if transaction_id:
        payment.sepay_transaction_id = str(transaction_id)

    target_plan = payment_service.get_plan_by_amount(payment.amount)
    package = payment_service.get_package(target_plan)

    if target_plan and _plan_rank(target_plan) > _plan_rank(user.plan):
        user.plan = target_plan

    if package and package.get('token_amount'):
        current_balance = int(user.token_balance or 0)
        user.token_balance = current_balance + int(package.get('token_amount', 0))

    return package


@payment_bp.route('/packages', methods=['GET'])
@jwt_required()
def list_packages():
    user_identity = get_jwt_identity()
    user = _resolve_user(user_identity)

    packages = []
    for pkg in sorted(payment_service.PACKAGES.values(), key=lambda p: p['amount_vnd']):
        item = dict(pkg)
        if user:
            can_buy, reason = _can_purchase_package(user, pkg['package_id'])
            item['can_purchase'] = can_buy
            item['repurchase_available'] = _can_repurchase_package(user, pkg)
            if not can_buy:
                item['purchase_blocked_reason'] = reason
        else:
            item['can_purchase'] = True
            item['repurchase_available'] = False
        packages.append(item)

    return jsonify({
        "packages": packages,
        "bank": {
            "code": payment_service.bank_code,
            "account_number": payment_service.bank_account,
            "account_name": payment_service.bank_account_name,
        },
    }), 200


@payment_bp.route('/current', methods=['GET'])
@jwt_required()
def current_pending_invoice():
    user_identity = get_jwt_identity()
    user = _resolve_user(user_identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    _mark_user_expired_pending(user.id)

    payment = (
        Payment.query
        .filter_by(user_id=user.id, status='pending')
        .order_by(Payment.created_at.desc())
        .first()
    )
    if not payment:
        return jsonify({"has_pending": False}), 200

    package = payment_service.get_package(payment_service.get_plan_by_amount(payment.amount))
    return jsonify({
        "has_pending": True,
        "invoice": _serialize_invoice(payment, package, reused=True),
    }), 200

@payment_bp.route('/create', methods=['POST'])
@jwt_required()
def create_payment():
    data = request.get_json(silent=True) or {}
    package_id = str(data.get('package_id') or '').strip().lower()
    force_new = bool(data.get('force_new', False))

    package = payment_service.get_package(package_id)
    if not package:
        return jsonify({
            "error": "Invalid package_id",
            "allowed": sorted(list(payment_service.PACKAGES.keys())),
        }), 400

    user_identity = get_jwt_identity()
    user = _resolve_user(user_identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    can_buy, blocked_reason = _can_purchase_package(user, package_id)
    if not can_buy:
        return jsonify({"error": blocked_reason}), 403

    _mark_user_expired_pending(user.id)

    existing_pending = (
        Payment.query
        .filter_by(user_id=user.id, status='pending', currency='VND')
        .order_by(Payment.created_at.desc())
        .first()
    )
    same_amount = bool(existing_pending) and int(round(float(existing_pending.amount or 0))) == int(
        package['amount_vnd']
    )
    if (not force_new) and existing_pending and same_amount and not payment_service.is_expired(existing_pending.created_at):
        existing_package = payment_service.get_package(payment_service.get_plan_by_amount(existing_pending.amount))
        return jsonify(_serialize_invoice(existing_pending, existing_package, reused=True)), 200

    payment = Payment(
        user_id=user.id,
        plan_type=package.get('plan'),
        amount=package['amount_vnd'],
        currency='VND',
        status='pending'
    )
    db.session.add(payment)
    db.session.commit()

    return jsonify(_serialize_invoice(payment, package, reused=False)), 200


@payment_bp.route('/status/<payment_ref>', methods=['GET'])
@jwt_required()
def check_payment_status(payment_ref):
    user_identity = get_jwt_identity()
    user = _resolve_user(user_identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    ref_value = str(payment_ref or '').strip()
    payment = None

    if ref_value.isdigit():
        payment = Payment.query.filter_by(id=int(ref_value), user_id=user.id).first()
    else:
        try:
            decoded_id = payment_service.decode_payment_id(ref_value)
            payment = Payment.query.filter_by(id=decoded_id, user_id=user.id).first()
        except Exception:
            return jsonify({"error": "Invalid payment id"}), 400

    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    if payment.status in ('pending', 'failed'):
        matched, transaction_id = payment_service.reconcile_payment(payment)
        if matched:
            package = _complete_payment(payment, user, transaction_id=transaction_id)
            db.session.commit()
        elif payment.status == 'pending' and payment_service.is_expired(payment.created_at):
            payment.status = 'failed'
            db.session.commit()

    package = payment_service.get_package(payment_service.get_plan_by_amount(payment.amount))
    return jsonify(_serialize_invoice(payment, package, reused=False)), 200


@payment_bp.route('/debug/sepay', methods=['GET'])
@jwt_required()
def debug_sepay():
    """Debug endpoint: show raw SePay API response + reconcile status for user's latest pending invoice.

    Only available when DEBUG=True.
    """
    if not current_app.config.get('DEBUG'):
        return jsonify({"error": "Not available in production"}), 404

    user_identity = get_jwt_identity()
    user = _resolve_user(user_identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Raw SePay API response (latest 5 transactions)
    raw_payload = payment_service.get_recent_transactions_raw()
    transactions = payment_service.get_recent_transactions()

    # User's latest payment
    latest = Payment.query.filter_by(user_id=user.id).order_by(Payment.created_at.desc()).first()
    invoice_info = None
    reconcile_result = None
    if latest:
        target_hex = payment_service.encode_payment_id(latest.id)
        invoice_info = {
            "id": latest.id,
            "status": latest.status,
            "amount": float(latest.amount or 0),
            "target_hex": target_hex,
            "transfer_content": payment_service.build_transfer_content(target_hex),
            "created_at": latest.created_at.isoformat() + 'Z',
        }
        # Show how each transaction was parsed
        parsed_txs = []
        for tx in transactions:
            found_hex = payment_service.extract_payment_hex_from_tx(tx)
            amount_in = payment_service._pick_amount_in(tx)
            parsed_txs.append({
                "id": tx.get("id"),
                "transaction_content": tx.get("transaction_content"),
                "content": tx.get("content"),
                "code": tx.get("code"),
                "amount_in_raw": tx.get("amount_in"),
                "amount_in_parsed": amount_in,
                "found_hex": found_hex,
                "hex_match": found_hex == target_hex if found_hex else False,
                "amount_ok": amount_in >= float(latest.amount or 0) if amount_in else False,
            })
        reconcile_result = {
            "transactions_fetched": len(transactions),
            "parsed": parsed_txs,
        }

    return jsonify({
        "sepay_api_key_set": bool(payment_service.api_key),
        "transfer_prefix": payment_service.get_transfer_prefix(),
        "bank_code": payment_service.bank_code,
        "bank_account": payment_service.bank_account,
        "raw_sepay_response": raw_payload,
        "latest_invoice": invoice_info,
        "reconcile_debug": reconcile_result,
    }), 200


@payment_bp.route('/dev/activate-plan', methods=['POST'])
@jwt_required()
def dev_activate_plan():
    """Dev helper: activate a plan immediately (no payment verification).

    This is only enabled when DEBUG=True.
    """
    if not current_app.config.get('DEBUG'):
        return jsonify({"error": "Not available"}), 404

    data = request.get_json(silent=True) or {}
    plan = str(data.get('plan') or '').strip().lower()
    allowed = {'free', 'pro', 'promax'}
    if plan not in allowed:
        return jsonify({"error": "Invalid plan", "allowed": sorted(list(allowed))}), 400

    user_identity = get_jwt_identity()
    user = _resolve_user(user_identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.plan = plan
    db.session.commit()

    return jsonify({
        "plan": user.plan,
        "plan_name": {"free": "Free", "pro": "Pro", "promax": "ProMax"}[plan]
    }), 200


@payment_bp.route('/sepay/webhook', methods=['POST'])
def sepay_webhook():
    """Receive transaction webhooks from SePay.

    SePay (API Key auth) sends header: Authorization: Apikey <API_KEY>
    Payload fields (json or form): id, transferType, transferAmount, content, ...
    """

    expected_key = str(payment_service.webhook_api_key or '').strip()
    auth_header = str(request.headers.get('Authorization') or '').strip()

    if not expected_key:
        return jsonify({"success": False, "error": "Webhook not configured"}), 500

    normalized = auth_header.replace("\t", " ").strip()
    allowed = {
        f"Apikey {expected_key}",
        f"ApiKey {expected_key}",
        f"apikey {expected_key}",
        f"Bearer {expected_key}",
    }
    if normalized not in allowed:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict(flat=True) or {}

    transfer_type = str(payload.get('transferType') or payload.get('transfer_type') or '').strip().lower()
    if transfer_type and transfer_type != 'in':
        return jsonify({"success": True, "ignored": True}), 200

    tx_id = payload.get('id') or payload.get('transactionId') or payload.get('transaction_id')
    code = payload.get('code')
    content = payload.get('content') or payload.get('description') or ''
    amount = payload.get('transferAmount') or payload.get('transfer_amount') or payload.get('amount')

    found_hex = payment_service.extract_payment_hex(code) or payment_service.extract_payment_hex(content)
    if not found_hex:
        return jsonify({"success": True, "ignored": True, "reason": "no_code"}), 200

    try:
        payment_id = payment_service.decode_payment_id(found_hex)
    except Exception:
        return jsonify({"success": True, "ignored": True, "reason": "bad_code"}), 200

    payment = Payment.query.filter_by(id=payment_id).first()
    if not payment:
        return jsonify({"success": True, "ignored": True, "reason": "payment_not_found"}), 200

    if payment.status == 'completed':
        return jsonify({"success": True, "duplicate": True}), 200

    # Idempotency guard: if we already processed the same SePay transaction id
    if tx_id and payment.sepay_transaction_id and str(payment.sepay_transaction_id) == str(tx_id):
        payment.status = 'completed'
        db.session.commit()
        return jsonify({"success": True, "duplicate": True}), 200

    if amount is None:
        return jsonify({"success": True, "ignored": True, "reason": "missing_amount"}), 200

    amount_value = payment_service._to_float(amount)
    if amount_value <= 0:
        return jsonify({"success": True, "ignored": True, "reason": "bad_amount"}), 200

    if amount_value < float(payment.amount or 0):
        return jsonify({"success": True, "ignored": True, "reason": "amount_too_low"}), 200

    user = User.query.filter_by(id=payment.user_id).first()
    if not user:
        return jsonify({"success": True, "ignored": True, "reason": "user_not_found"}), 200

    _complete_payment(payment, user, transaction_id=tx_id)
    db.session.commit()

    return jsonify({
        "success": True,
        "payment_id": payment.id,
        "hex_id": found_hex,
        "status": payment.status,
    }), 201