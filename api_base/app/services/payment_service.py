import logging
import os
import re
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class PaymentService:
    DEFAULT_PACKAGES = {
        "pro": {
            "package_id": "pro",
            "plan": "pro",
            "name": "Pro",
            "amount_vnd": 99000,
            "token_amount": 120000,
        },
        "promax": {
            "package_id": "promax",
            "plan": "promax",
            "name": "ProMax",
            "amount_vnd": 199000,
            "token_amount": 300000,
        },
    }

    @classmethod
    def _load_packages(cls) -> dict:
        try:
            from app.services.site_config_service import load_packages_config
            data = load_packages_config()
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
        return dict(cls.DEFAULT_PACKAGES)

    @property
    def PACKAGES(self):
        return self._load_packages()

    def __init__(self):
        # Ensure .env is loaded even if this service is imported before app.config.
        # Existing environment variables should win unless DOTENV_OVERRIDE is enabled.
        _override = (os.getenv("DOTENV_OVERRIDE") or "").strip().lower() in ("1", "true", "yes", "on")
        _api_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        load_dotenv(os.path.join(_api_base_dir, ".env"), override=_override)

        self.api_key = os.getenv("SEPAY_API_KEY", "").strip()
        self.webhook_api_key = self._pick_env("SEPAY_WEBHOOK_API_KEY", "SEPAY_API_KEY")
        self.base_url = os.getenv("SEPAY_BASE_URL", "https://my.sepay.vn").rstrip("/")
        self.history_endpoint = os.getenv("SEPAY_HISTORY_ENDPOINT", "/userapi/transactions/list")

        self.name_web = (os.getenv("NAME_WEB") or os.getenv("PAYMENT_NAME_WEB") or "AITRANS").strip().upper()
        self.transfer_keyword = os.getenv("PAYMENT_TRANSFER_KEYWORD", "NAPTOKEN").strip().upper()
        self.secret_xor_key = self._parse_xor_key(os.getenv("PAYMENT_XOR_KEY", "0x5EAFB"))
        self.expire_minutes = int(os.getenv("PAYMENT_EXPIRE_MINUTES", "60"))
        self.poll_tx_limit = int(os.getenv("PAYMENT_POLL_TX_LIMIT", "20"))
        self.poll_tx_pages = max(1, min(int(os.getenv("PAYMENT_POLL_TX_PAGES", "3")), 10))

        self.bank_code = self._pick_env(
            "PAYMENT_BANK_CODE",
            "SEPAY_BANK_CODE",
            "BANK_CODE",
            "RECEIVE_BANK_CODE",
        ).upper()
        self.bank_account = self._pick_env(
            "PAYMENT_BANK_ACCOUNT",
            "SEPAY_BANK_ACCOUNT",
            "BANK_ACCOUNT",
            "BANK_ACCOUNT_NUMBER",
            "SEPAY_ACCOUNT_NUMBER",
            "RECEIVE_BANK_ACCOUNT",
        )
        self.bank_account_name = self._pick_env(
            "PAYMENT_BANK_ACCOUNT_NAME",
            "SEPAY_BANK_ACCOUNT_NAME",
            "BANK_ACCOUNT_NAME",
            "RECEIVE_BANK_ACCOUNT_NAME",
        )
        self.sepay_qr_template_url = self._pick_env("SEPAY_QR_TEMPLATE_URL", "PAYMENT_QR_TEMPLATE_URL")

        if not self.bank_code:
            self.bank_code = "MB"

    @staticmethod
    def _pick_env(*keys):
        for key in keys:
            value = (os.getenv(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _parse_xor_key(raw_value):
        raw = str(raw_value or "").strip()
        if not raw:
            return 0x5EAFB
        if raw.lower().startswith("0x"):
            return int(raw, 16)
        return int(raw)

    @staticmethod
    def _to_float(value):
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).strip().replace(" ", "")
        if not cleaned:
            return 0.0

        # Handle common VN amount formats:
        # - 99,000 or 99.000 (thousands separators)
        # - 99000.50 / 99,000.50
        if "," in cleaned and "." in cleaned:
            # Decide decimal separator by the right-most symbol
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                cleaned = "".join(parts)

        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def get_package(self, package_id):
        key = str(package_id or "").strip().lower()
        return self.PACKAGES.get(key)

    def get_plan_by_amount(self, amount):
        amount_value = int(round(float(amount or 0)))
        for package in self.PACKAGES.values():
            if int(package["amount_vnd"]) == amount_value:
                return package["plan"]
        return None

    def encode_payment_id(self, payment_id):
        return format(int(payment_id) ^ self.secret_xor_key, "X")

    def decode_payment_id(self, hex_str):
        return int(str(hex_str), 16) ^ self.secret_xor_key

    def get_transfer_prefix(self):
        return f"{self.name_web}{self.transfer_keyword}"

    def build_transfer_content(self, hex_id):
        return f"{self.get_transfer_prefix()}{str(hex_id).upper()}"

    def get_expire_at(self, created_at):
        return created_at + timedelta(minutes=self.expire_minutes)

    def is_expired(self, created_at):
        return datetime.utcnow() >= self.get_expire_at(created_at)

    def get_qr_image_url(self, amount_vnd, transfer_content):
        amount = int(round(float(amount_vnd or 0)))
        if self.sepay_qr_template_url:
            template = self.sepay_qr_template_url

            placeholders = {
                "{amount}": str(amount),
                "{content}": quote(str(transfer_content or "")),
                "{bank}": quote(str(self.bank_code or "")),
                "{bank_code}": quote(str(self.bank_code or "")),
                "{acc}": quote(str(self.bank_account or "")),
                "{account}": quote(str(self.bank_account or "")),
                "{account_number}": quote(str(self.bank_account or "")),
                "{account_name}": quote(str(self.bank_account_name or "")),
            }

            for key, value in placeholders.items():
                template = template.replace(key, value)

            return template

        if not self.bank_account or not self.bank_code:
            return None
        params = {
            "amount": amount,
            "addInfo": transfer_content,
            "accountName": self.bank_account_name,
        }
        query = "&".join(
            f"{key}={requests.utils.quote(str(value))}" for key, value in params.items() if value
        )
        return f"https://img.vietqr.io/image/{self.bank_code}-{self.bank_account}-compact2.png?{query}"

    @staticmethod
    def _extract_transactions(payload):
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        candidate_keys = ("transactions", "data", "items", "result")
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for nested_key in candidate_keys:
                    nested = value.get(nested_key)
                    if isinstance(nested, list):
                        return nested
        return []

    def get_recent_transactions(self):
        if not self.api_key:
            logger.warning("[SePay] SEPAY_API_KEY is not set — cannot fetch transactions.")
            return []

        url = f"{self.base_url}{self.history_endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        collected = []
        seen_ids = set()

        for page in range(1, self.poll_tx_pages + 1):
            params = {
                "limit": self.poll_tx_limit,
                "page": page,
            }

            try:
                response = requests.get(url, headers=headers, params=params, timeout=15)
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.error("[SePay] Failed to fetch transactions (page %d): %s", page, exc)
                continue

            tx_list = self._extract_transactions(payload)
            logger.debug("[SePay] Page %d: got %d raw transactions.", page, len(tx_list))
            if not tx_list:
                break

            for tx in tx_list:
                if not isinstance(tx, dict):
                    continue
                tx_id = str(tx.get("id") or tx.get("transaction_id") or tx.get("reference") or "")
                if tx_id and tx_id in seen_ids:
                    continue
                if tx_id:
                    seen_ids.add(tx_id)
                collected.append(tx)

            if len(tx_list) < self.poll_tx_limit:
                break

        logger.info("[SePay] Total transactions fetched: %d", len(collected))
        return collected

    def extract_payment_hex(self, content):
        prefix = re.escape(self.get_transfer_prefix())
        # Allow separators between prefix and hex code because bank descriptions
        # can insert spaces/punctuation unpredictably.
        pattern = re.compile(rf"{prefix}[^A-Fa-f0-9]*([A-Fa-f0-9]+)", re.IGNORECASE)
        match = pattern.search(str(content or ""))
        if not match:
            return None
        return match.group(1).upper()

    def extract_payment_hex_from_tx(self, tx):
        if not isinstance(tx, dict):
            return None

        # SePay can auto-detect a payment code based on company config.
        # Prefer explicit `code` when present.
        code_value = tx.get("code")
        found = self.extract_payment_hex(code_value)
        if found:
            return found

        # SePay User API (userapi/transactions/list) uses 'transaction_content'.
        # Webhook payloads use 'content'. Check all variants.
        content = (
            tx.get("transaction_content")
            or tx.get("content")
            or tx.get("description")
            or tx.get("transfer_content")
            or tx.get("memo")
            or tx.get("remark")
        )
        return self.extract_payment_hex(content)

    @staticmethod
    def _pick_amount_in(tx):
        """Return the *incoming* amount from a SePay transaction dict.

        SePay User API:  amount_in / amount_out (strings, e.g. "99000" / "0")
        SePay Webhook:   transferAmount (number), transferType = "in"
        """
        # Prefer amount_in – it is 0 for outgoing txs
        raw_in = tx.get("amount_in")
        if raw_in is not None:
            try:
                v = float(str(raw_in).replace(",", "").strip() or "0")
            except ValueError:
                v = 0.0
            if v > 0:
                return v
            # amount_in == 0 → this is an outgoing tx; skip by returning 0
            return 0.0

        # Webhook: use transferAmount only when transferType == "in"
        transfer_type = str(tx.get("transferType") or tx.get("transfer_type") or "").strip().lower()
        if transfer_type and transfer_type != "in":
            return 0.0

        for key in ("transferAmount", "transfer_amount", "amount"):
            raw = tx.get(key)
            if raw is not None:
                try:
                    v = float(str(raw).replace(",", "").strip() or "0")
                    if v > 0:
                        return v
                except ValueError:
                    pass
        return 0.0

    def reconcile_payment(self, payment):
        target_hex = self.encode_payment_id(payment.id)
        logger.info(
            "[Reconcile] payment_id=%s target_hex=%s expected_amount=%s",
            payment.id, target_hex, payment.amount,
        )

        transactions = self.get_recent_transactions()
        if not transactions:
            logger.warning("[Reconcile] No transactions returned from SePay — check SEPAY_API_KEY and connectivity.")
            return False, None

        for tx in transactions:
            found_hex = self.extract_payment_hex_from_tx(tx)
            amount = self._pick_amount_in(tx)
            logger.debug(
                "[Reconcile] tx_id=%s found_hex=%s amount_in=%s content=%s",
                tx.get("id"), found_hex, amount,
                tx.get("transaction_content") or tx.get("content") or "",
            )
            if not found_hex:
                continue
            if found_hex != target_hex:
                logger.debug("[Reconcile] hex mismatch: found %s != target %s", found_hex, target_hex)
                continue

            if amount <= 0 or amount < float(payment.amount or 0):
                logger.warning(
                    "[Reconcile] Hex matched but amount too low: found %.0f < required %.0f",
                    amount, float(payment.amount or 0),
                )
                continue

            tx_id = tx.get("id") or tx.get("transaction_id") or tx.get("reference") or ""
            logger.info("[Reconcile] MATCHED payment_id=%s tx_id=%s amount=%.0f", payment.id, tx_id, amount)
            return True, str(tx_id)

        logger.info("[Reconcile] No matching transaction found for payment_id=%s", payment.id)
        return False, None

    def get_recent_transactions_raw(self):
        """Return raw SePay API payload (for debugging)."""
        if not self.api_key:
            return {"error": "SEPAY_API_KEY not configured"}

        url = f"{self.base_url}{self.history_endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.get(url, headers=headers, params={"limit": 5, "page": 1}, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            return {"error": str(exc)}