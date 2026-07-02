import deepl
import os
import threading
import uuid
import time
import re
import shutil
import unicodedata
from dotenv import load_dotenv
from app.services.file_service import FileService, ProviderRateLimitError
from app.services.document_v2.fonts import get_noto_sans_or_fallback as _get_noto_font
import requests
import urllib.parse

GoogleTranslator = None
GOOGLETRANS_LANGUAGES = {}

# Load .env từ thư mục backend (app/services -> app -> backend)
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# IMPORTANT: In Docker, environment variables should win (DATABASE_URL, API keys, etc).
# Set DOTENV_OVERRIDE=1 only if you explicitly want backend/.env to override existing env vars.
_override = (os.getenv('DOTENV_OVERRIDE') or '').strip().lower() in ('1', 'true', 'yes', 'on')
load_dotenv(os.path.join(_backend_dir, '.env'), override=_override)

# Bản đồ mã ISO 639-1 sang mã ngôn ngữ đích của DeepL (chỉ các ngôn ngữ DeepL hỗ trợ)
# Nguồn: https://developers.deepl.com/docs/resources/supported-languages
DEEPL_TARGET_MAP = {
    'ar': 'AR', 'bg': 'BG', 'cs': 'CS', 'da': 'DA', 'de': 'DE', 'el': 'EL',
    'en': 'EN-US', 'en-us': 'EN-US', 'en-gb': 'EN-GB',
    'es': 'ES', 'et': 'ET', 'fi': 'FI', 'fr': 'FR',
    'he': 'HE', 'iw': 'HE',  # iw là mã cũ của Hebrew
    'hu': 'HU', 'id': 'ID', 'it': 'IT', 'ja': 'JA', 'ko': 'KO',
    'lt': 'LT', 'lv': 'LV', 'nb': 'NB', 'no': 'NB',  # Norwegian -> Bokmål
    'nl': 'NL', 'pl': 'PL',
    'pt': 'PT-BR', 'pt-br': 'PT-BR', 'pt-pt': 'PT-PT',
    'ro': 'RO', 'ru': 'RU', 'sk': 'SK', 'sl': 'SL', 'sv': 'SV',
    'th': 'TH', 'tr': 'TR', 'uk': 'UK', 'vi': 'VI',
    'zh': 'ZH', 'zh-cn': 'ZH', 'zh-hans': 'ZH', 'zh-tw': 'ZH-HANT', 'zh-hant': 'ZH-HANT',
}

# Tên ngôn ngữ cho prompt OpenAI (các ngôn ngữ DeepL không hỗ trợ dùng OpenAI)
# Giúp model hiểu rõ hơn so với chỉ dùng mã (vd: "Thai" thay vì "th")
CODE_TO_NAME = {
    'af': 'Afrikaans', 'sq': 'Albanian', 'am': 'Amharic', 'ar': 'Arabic',
    'hy': 'Armenian', 'az': 'Azerbaijani', 'eu': 'Basque', 'be': 'Belarusian',
    'bn': 'Bengali', 'bs': 'Bosnian', 'bg': 'Bulgarian', 'ca': 'Catalan',
    'zh': 'Chinese (Simplified)', 'zh-cn': 'Chinese (Simplified)', 'zh-hans': 'Chinese (Simplified)',
    'zh-tw': 'Chinese (Traditional)', 'zh-hant': 'Chinese (Traditional)',
    'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish', 'nl': 'Dutch',
    'en': 'English', 'et': 'Estonian', 'fi': 'Finnish', 'fr': 'French',
    'de': 'German', 'el': 'Greek', 'he': 'Hebrew', 'iw': 'Hebrew',
    'hi': 'Hindi', 'hu': 'Hungarian', 'id': 'Indonesian', 'it': 'Italian',
    'ja': 'Japanese', 'ko': 'Korean', 'lv': 'Latvian', 'lt': 'Lithuanian',
    'ms': 'Malay', 'no': 'Norwegian', 'nb': 'Norwegian Bokmål',
    'fa': 'Persian', 'pl': 'Polish', 'pt': 'Portuguese', 'ro': 'Romanian',
    'ru': 'Russian', 'sr': 'Serbian', 'sk': 'Slovak', 'sl': 'Slovenian',
    'es': 'Spanish', 'sw': 'Swahili', 'sv': 'Swedish', 'th': 'Thai',
    'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu', 'vi': 'Vietnamese',
    'gu': 'Gujarati', 'kn': 'Kannada', 'ml': 'Malayalam',
    'mr': 'Marathi', 'ta': 'Tamil', 'te': 'Telugu', 'pa': 'Punjabi', 'ne': 'Nepali',
    'my': 'Myanmar (Burmese)', 'km': 'Khmer', 'lo': 'Lao', 'tl': 'Filipino',
    'ny': 'Nyanja (Chichewa)',
}


def _normalize_lang_token(text: str) -> str:
    s = (text or '').strip().lower()
    if not s:
        return ''
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


_GOOGLE_EXTRA_LANG_CODES = {'ny'}
_GOOGLE_EXTRA_NAME_TO_CODE = {
    'nyanja': 'ny',
    'chichewa': 'ny',
}


_GOOGLE_LANG_CODES = set((GOOGLETRANS_LANGUAGES or {}).keys())
_GOOGLE_NAME_TO_CODE = {}
for _code, _name in (GOOGLETRANS_LANGUAGES or {}).items():
    _k = _normalize_lang_token(_name)
    if _k:
        _GOOGLE_NAME_TO_CODE[_k] = _code

for _code, _name in CODE_TO_NAME.items():
    _root = _code.split('-')[0].lower()
    _GOOGLE_LANG_CODES.add(_root)
    _k = _normalize_lang_token(_name)
    if _k and _k not in _GOOGLE_NAME_TO_CODE:
        _GOOGLE_NAME_TO_CODE[_k] = _root

_GOOGLE_LANG_CODES.update({'zh-cn', 'zh-tw'})
_GOOGLE_LANG_CODES.update(_GOOGLE_EXTRA_LANG_CODES)
for _k, _v in _GOOGLE_EXTRA_NAME_TO_CODE.items():
    _nk = _normalize_lang_token(_k)
    if _nk and _nk not in _GOOGLE_NAME_TO_CODE:
        _GOOGLE_NAME_TO_CODE[_nk] = _v

class TranslationService:
    def __init__(self):
        def _sanitize_key(val):
            if not val:
                return None
            v = val.strip()
            # Strip wrapping quotes if user put OPENAI_API_KEY="..." in .env
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1].strip()
            # Treat obvious placeholders or very-short values as absent
            if v.lower().startswith('your-') or v.lower() in ('changeme', 'replace-me', '') or len(v) < 20:
                return None
            return v

        openai_key = _sanitize_key(os.getenv('OPENAI_API_KEY'))
        deepl_key = _sanitize_key(os.getenv('DEEPL_API_KEY'))
        openrouter_key = _sanitize_key(os.getenv('OPENROUTER_API_KEY'))
        gemini_key = _sanitize_key(os.getenv('GEMINI_API_KEY'))
        # HTTP timeout (seconds) to avoid hanging forever when provider stalls
        try:
            http_timeout = float(os.getenv('AI_HTTP_TIMEOUT', '60'))
        except Exception:
            http_timeout = 60.0
        # Debug: show which keys are present (do not print values). placeholders are ignored.
        print(
            f"TranslationService keys - DEEPL: {bool(deepl_key)}, OPENAI: {bool(openai_key)}, "
            f"OPENROUTER: {bool(openrouter_key)}, GEMINI: {bool(gemini_key)}"
        )
        self.deepl_translator = deepl.Translator(deepl_key) if deepl_key else None
        self._googletrans_local = threading.local()
        self._request_local = threading.local()
        self._googletrans_import_error_logged = False
        self._gemini_api_key = gemini_key
        self._gemini_model = (os.getenv('GEMINI_MODEL') or 'gemini-2.5-flash').strip() or 'gemini-2.5-flash'

        # Load OpenAI SDK lazily to avoid expensive import during module load.
        openai_sdk = None
        if openai_key or openrouter_key:
            try:
                import openai as openai_sdk  # type: ignore
            except Exception as e:
                print(f"OpenAI SDK import failed: {e}")

        # Initialize AI client with provider preference.
        provider = (os.getenv('AI_PROVIDER') or 'openrouter').strip().lower()
        self.ai_provider = provider
        self._using_openrouter = False
        self.openai_client = None

        def _openrouter_client():
            if not openai_sdk:
                return None
            extra = {}
            ref = os.getenv('AI_HEADER_HTTP_REFERER') or os.getenv('HTTP_REFERER')
            if ref:
                extra["default_headers"] = {"Referer": ref.strip()}
            self._using_openrouter = True
            return openai_sdk.OpenAI(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=http_timeout,
                **extra
            )

        if provider in ('openai', 'openai_api'):
            if openai_key and openai_sdk:
                self.openai_client = openai_sdk.OpenAI(api_key=openai_key, timeout=http_timeout)
            elif openrouter_key:
                self.openai_client = _openrouter_client()
        elif provider == 'openrouter':
            if openrouter_key:
                self.openai_client = _openrouter_client()
            elif openai_key and openai_sdk:
                self.openai_client = openai_sdk.OpenAI(api_key=openai_key, timeout=http_timeout)
        else:
            # Auto fallback: prefer OpenAI key, then OpenRouter.
            if openai_key and openai_sdk:
                self.openai_client = openai_sdk.OpenAI(api_key=openai_key, timeout=http_timeout)
            elif openrouter_key:
                self.openai_client = _openrouter_client()
            
        # Pass translator callback into FileService so document processing can call
        # Provide FileService both translation and OCR hooks (used for DOCX embedded images)
        self.file_service = FileService(
            translator=self.translate_text,
            ocr_image_to_text=self.ocr_image_to_text,
            ocr_translate_overlay=self.ocr_translate_overlay,
            ocr_image_to_bboxes=self.ocr_image_to_bboxes,
        )
        self.file_service.has_tesseract = self._is_tesseract_available()
        # Simple in-memory job store for background document processing
        self.jobs = {}  # job_id -> {status, progress, message, download_path, error}
        # Cache for system prompt (loaded once)
        self._system_prompt_cache = None
        # Cache for lightweight language checks used by skip-translation guards.
        self._lang_detect_cache = {}

    @staticmethod
    def _normalize_translation_provider(provider: str) -> str:
        raw = (provider or '').strip().lower()
        if not raw:
            return ''
        compact = re.sub(r"[\s_\-.]+", "", raw)
        if compact in ('google', 'gg', 'ggtranslate', 'googletranslate'):
            return 'google'
        if compact in ('deepl',):
            return 'deepl'
        if compact in ('gemini', 'gemini2flash', 'gemini20flash', 'gemini20'):
            return 'gemini'
        return ''

    def set_request_translation_provider(self, provider: str) -> str:
        normalized = self._normalize_translation_provider(provider)
        if normalized:
            self._request_local.translation_provider = normalized
        else:
            self.clear_request_translation_provider()
        return normalized

    def clear_request_translation_provider(self) -> None:
        if hasattr(self._request_local, 'translation_provider'):
            delattr(self._request_local, 'translation_provider')

    def _get_effective_translation_provider(self, provider: str = None) -> str:
        normalized = self._normalize_translation_provider(provider)
        if normalized:
            return normalized

        request_provider = self._normalize_translation_provider(
            getattr(self._request_local, 'translation_provider', None)
        )
        if request_provider:
            return request_provider

        default_provider = self._normalize_translation_provider(
            os.getenv('TRANSLATION_PROVIDER_DEFAULT')
        )
        return default_provider or 'google'

    def _get_gemini_direct_model(self) -> str:
        model = (self._gemini_model or 'gemini-2.5-flash').strip() or 'gemini-2.5-flash'
        # Direct Gemini API expects model id without provider prefix.
        if '/' in model:
            model = model.split('/')[-1].strip()
        return model or 'gemini-2.5-flash'

    def _get_gemini_openrouter_model(self) -> str:
        model = (self._gemini_model or 'gemini-2.5-flash').strip() or 'gemini-2.5-flash'
        if '/' not in model:
            return f'google/{model}'
        return model
    
    def _load_system_prompt(self):
        """Load comprehensive translation system prompt from TRANSLATION_SYSTEM_PROMPT.md file."""
        if self._system_prompt_cache:
            return self._system_prompt_cache
        
        try:
            # Try to load from backend directory
            prompt_path = os.path.join(_backend_dir, 'TRANSLATION_SYSTEM_PROMPT.md')
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self._system_prompt_cache = content
                return content
        except Exception as e:
            print(f"Failed to load TRANSLATION_SYSTEM_PROMPT.md: {e}")
        
        # Return None so fallback to inline prompt
        return None

    def _looks_like_instruction_echo(self, source_text, candidate_text):
        """Detect invalid model outputs that look like prompt/instruction leakage."""
        out = (candidate_text or '').strip()
        if not out:
            return True

        low = out.lower()
        src_low = (source_text or '').lower()
        markers = (
            'you are a professional translator',
            'critical rules',
            'qa checklist',
            'preserve_layout',
            'line_by_line',
            'translation target',
            'dịch từ',
            '## ',
        )
        if any(m in low for m in markers) and not any(m in src_low for m in markers):
            return True

        src_len = len((source_text or '').strip())
        out_len = len(out)
        # Short source should not produce a very long output block.
        if src_len > 0 and src_len <= 180 and out_len > max(450, src_len * 4):
            return True

        # Keep line structure stable for document translation chunks.
        if out.count('\n') > (source_text or '').count('\n') + 6:
            return True

        return False
    
    def _get_system_prompt(self, target_name, source_name=None, *, context=None):
        """Get system prompt combining loaded file + dynamic language info."""
        if context == 'document_pdf':
            prompt = (
                f"You are a professional document translator. Translate this PDF text into {target_name}.\n"
                "Translate the FULL sentence or phrase with natural meaning — NEVER word-by-word.\n"
                "Preserve the exact meaning; do not guess, embellish, summarize, or add new ideas.\n"
                "Strict layout mode: keep the reply as a single paragraph block unless the source "
                "clearly contains intentional line breaks.\n"
                "Preserve proper names as names, not literal meanings "
                "(e.g. Việt Nam = Vietnam, Nam Cần Thơ, not Vietnam Male / South Can Tho).\n"
                "Vietnamese compounds must keep idiomatic meaning "
                "(e.g. đất nước = country, thắng cảnh = scenic spot, nổi tiếng = famous, "
                "lòng hiếu khách = hospitality).\n"
                "In Vietnamese form labels, translate \"Mẫu\" as \"Form\" (not \"Model\").\n"
                "Preserve complete date meaning; do not omit day, month, or year.\n"
                "Use concise wording when possible; preserve numbers, emails, URLs, identifiers, and symbols verbatim.\n"
                "Do not add explanations, markdown, or labels.\n"
                "Return only the translated text."
            )
            if source_name:
                prompt += f"\nSource language hint: {source_name}."
            return prompt

        if context == 'document_docx_batch':
            prompt = (
                f"You are a professional document translator. "
                f"Translate each text block to {target_name} faithfully and accurately.\n\n"
                f"INPUT: Multiple text blocks separated by <<<S>>>\n\n"
                f"CRITICAL RULES:\n"
                f"1. Output the SAME number of blocks in the SAME order, separated by <<<S>>>\n"
                f"2. Translate full phrases and sentences with natural meaning — NEVER word-by-word\n"
                f"3. Preserve the exact meaning. Do not guess, embellish, summarize, or add new ideas\n"
                f"4. Use correct academic/technical terminology; if a term is ambiguous, choose the most literal safe translation\n"
                f"5. Preserve formatting: spacing, punctuation, newlines within blocks\n"
                f"6. Keep VERBATIM: numbers, codes, URLs, camelCase/snake_case identifiers, "
                f"email addresses, formulas, file paths\n"
                f"7. Preserve proper names as names, not literal meanings (e.g. Việt Nam = Vietnam, Nam Cần Thơ, not South Can Tho / Vietnam Male)\n"
                f"8. Vietnamese compounds must keep idiomatic meaning (e.g. đất nước = country, thắng cảnh = scenic spot, nổi tiếng = famous, lòng hiếu khách = hospitality)\n"
                f"9. In Vietnamese form labels, translate \"Mẫu\" as \"Form\" (not \"Model\")\n"
                f"10. Preserve complete date meaning; do not omit day, month, or year\n"
                f"11. Keep dot/underscore/dash runs (....., _____, -----) unchanged\n"
                f"12. Keep opaque placeholder tokens (\\uE000...\\uE001) unchanged — do not translate them\n"
                f"13. If a block is already in {target_name}, output it unchanged\n"
                f"14. Do NOT add explanations, labels, markdown, or extra text\n"
                f"15. Do NOT merge or split blocks — each <<<S>>> input block = one <<<S>>> output block\n\n"
                f"QUALITY CHECK: Each output block must preserve the original meaning exactly, "
                f"even when the source is a short table cell or heading fragment.\n\n"
                f"OUTPUT: Translated blocks separated by <<<S>>>"
            )
            if source_name:
                prompt += f"\nSource language: {source_name}."
            return prompt

        if context == 'document_docx_line':
            prompt = (
                f"You are a professional document translator. Translate this text into {target_name}.\n"
                f"Translate the FULL sentence or phrase with natural meaning — NEVER word-by-word.\n"
                f"Preserve the exact meaning; do not guess, embellish, summarize, or add new ideas.\n"
                f"For short table cells/headings, use the most literal safe translation.\n"
                f"Preserve proper names as names, not literal meanings (e.g. Việt Nam = Vietnam, Nam Cần Thơ, not Vietnam Male / South Can Tho).\n"
                f"Vietnamese compounds must keep idiomatic meaning (e.g. đất nước = country, thắng cảnh = scenic spot, nổi tiếng = famous, lòng hiếu khách = hospitality).\n"
                f"In Vietnamese form labels, translate \"Mẫu\" as \"Form\" (not \"Model\").\n"
                f"Preserve complete date meaning; do not omit day, month, or year.\n"
                f"Keep line breaks/spacing and punctuation structure stable.\n"
                f"Preserve numbers, URLs, emails, IDs, code-like tokens, and placeholders verbatim.\n"
                f"Keep opaque boundary tokens (\\uE000...\\uE001) unchanged — do not translate or remove them.\n"
                f"Do not add explanations/labels/markdown.\n"
                f"Return only translated text."
            )
            if source_name:
                prompt += f"\nSource language: {source_name}."
            return prompt

        use_external = (os.getenv('AI_USE_EXTERNAL_SYSTEM_PROMPT') or '').strip().lower() in ('1', 'true', 'yes', 'on')
        if use_external:
            prompt_file = self._load_system_prompt()
            if prompt_file:
                # Keep only the instruction section to avoid long prompt echo in small chunks.
                prompt = prompt_file.split('## Ví Dụ', 1)[0].strip()
                if len(prompt) > 3200:
                    prompt = prompt[:3200]
                if source_name:
                    prompt += f"\n\nTranslate from {source_name} to {target_name}."
                else:
                    prompt += f"\n\nTranslate to {target_name}."
                prompt += " Return only translated text."
                return prompt

        # Default: concise, deterministic prompt for chunk translation.
        prompt = (
            f"You are a professional translator. Translate to {target_name}.\n"
            f"Translate full phrases and sentences with natural meaning — NEVER word-by-word.\n"
            f"Preserve the exact meaning; do not guess, embellish, summarize, or add new ideas.\n"
            f"Vietnamese compounds must keep idiomatic meaning "
            f"(e.g. đất nước = country, thắng cảnh = scenic spot, nổi tiếng = famous).\n"
            f"Preserve proper names as names, not literal meanings "
            f"(e.g. Việt Nam = Vietnam, not Vietnam Male).\n"
            f"Preserve paragraph structure, spacing, punctuation, and formatting.\n"
            f"Keep numbers, codes, URLs, camelCase unchanged.\n"
            f"Return ONLY translated text."
        )
        if source_name:
            prompt += f"\nSource: {source_name}."
        return prompt

    @staticmethod
    def _target_is_vietnamese(target_code: str) -> bool:
        t = (target_code or "").strip().lower()
        return t in ("vi", "vi-vn", "vietnamese", "vn", "viet")

    @staticmethod
    def _lang_root(code: str) -> str:
        c = (code or "").strip().lower()
        if not c:
            return ""
        if c in ("zh-hans", "zh-hant"):
            return c
        return c.split("-")[0]

    def _to_google_lang_code(self, lang_value: str, *, fallback: str = 'auto') -> str:
        self._ensure_googletrans_support(load_client=True)
        raw = (lang_value or '').strip().lower()
        if not raw:
            return fallback

        raw = raw.replace('_', '-')
        if raw in ('auto', 'detect', 'detected'):
            return 'auto' if fallback == 'auto' else fallback

        if raw in ('zh', 'zh-cn', 'zh-sg', 'zh-hans'):
            return 'zh-cn'
        if raw in ('zh-tw', 'zh-hk', 'zh-mo', 'zh-hant'):
            return 'zh-tw'

        if raw in _GOOGLE_LANG_CODES:
            return raw

        if '-' in raw:
            root = raw.split('-')[0]
            if root in _GOOGLE_LANG_CODES:
                return 'zh-cn' if root == 'zh' else root

        name_key = _normalize_lang_token(raw)
        if name_key in _GOOGLE_NAME_TO_CODE:
            return _GOOGLE_NAME_TO_CODE[name_key]

        return fallback

    def _ensure_googletrans_support(self, *, load_client: bool) -> None:
        global GoogleTranslator
        global GOOGLETRANS_LANGUAGES
        global _GOOGLE_LANG_CODES
        global _GOOGLE_NAME_TO_CODE

        if GoogleTranslator is not None:
            return

        try:
            from googletrans import Translator as _GoogleTranslator
            try:
                from googletrans import LANGUAGES as _langs
            except Exception:
                _langs = {}
        except Exception as e:
            if load_client:
                if not self._googletrans_import_error_logged:
                    self._googletrans_import_error_logged = True
                    try:
                        print(f"googletrans client unavailable, falling back to Google web endpoint: {e}")
                    except Exception:
                        pass
            return

        GoogleTranslator = _GoogleTranslator
        GOOGLETRANS_LANGUAGES = dict(_langs or {})

        _GOOGLE_LANG_CODES = set((GOOGLETRANS_LANGUAGES or {}).keys())
        _GOOGLE_NAME_TO_CODE = {}
        for _code, _name in (GOOGLETRANS_LANGUAGES or {}).items():
            _k = _normalize_lang_token(_name)
            if _k:
                _GOOGLE_NAME_TO_CODE[_k] = _code

        for _code, _name in CODE_TO_NAME.items():
            _root = _code.split('-')[0].lower()
            if _root in _GOOGLE_LANG_CODES:
                _k = _normalize_lang_token(_name)
                if _k and _k not in _GOOGLE_NAME_TO_CODE:
                    _GOOGLE_NAME_TO_CODE[_k] = _root

        _GOOGLE_LANG_CODES.update(_GOOGLE_EXTRA_LANG_CODES)
        for _k, _v in _GOOGLE_EXTRA_NAME_TO_CODE.items():
            _nk = _normalize_lang_token(_k)
            if _nk and _nk not in _GOOGLE_NAME_TO_CODE:
                _GOOGLE_NAME_TO_CODE[_nk] = _v

    def _get_googletrans_client(self):
        self._ensure_googletrans_support(load_client=True)
        if GoogleTranslator is None:
            return None
        client = getattr(self._googletrans_local, 'client', None)
        if client is None:
            client = GoogleTranslator()
            self._googletrans_local.client = client
        return client

    def _google_web_translate(self, text: str, src_code: str, dst_code: str) -> str:
        url = 'https://translate.googleapis.com/translate_a/single'
        params = {
            'client': 'gtx',
            'sl': src_code or 'auto',
            'tl': dst_code,
            'dt': 't',
            'q': text,
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        parts = []
        if isinstance(data, list) and data:
            maybe = data[0]
            if isinstance(maybe, list):
                parts = maybe

        out = ''
        for seg in parts:
            if isinstance(seg, list) and seg:
                piece = seg[0]
                if piece is not None:
                    out += str(piece)

        return out.strip()

    @staticmethod
    def _looks_vietnamese_text(text: str) -> bool:
        s = (text or "").strip().lower()
        if not s:
            return False
        return bool(re.search(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", s))

    @staticmethod
    def _looks_vietnamese_like_text(text: str) -> bool:
        s = (text or "").strip().lower()
        if not s:
            return False
        if TranslationService._looks_vietnamese_text(s):
            return True
        if not re.search(r"[a-z]", s):
            return False

        try:
            norm = unicodedata.normalize('NFD', s)
            norm = ''.join(ch for ch in norm if unicodedata.category(ch) != 'Mn')
        except Exception:
            norm = s
        norm = norm.replace('đ', 'd')
        norm = re.sub(r"[^a-z0-9\s]", " ", norm)
        norm = re.sub(r"\s+", " ", norm).strip()
        if not norm:
            return False

        phrase_hits = 0
        phrase_patterns = (
            r"\bnghien cuu\b",
            r"\bhe thong\b",
            r"\bdu lieu\b",
            r"\brang buoc\b",
            r"\btrung binh\b",
            r"\bdai hoc\b",
            r"\btruong\b",
            r"\bkhoa\b",
            r"\bmo ta\b",
            r"\bho ten\b",
            r"\bdia chi\b",
            r"\bsinh vien\b",
            r"\bgiang vien\b",
            r"\btieng viet\b",
            r"\bbao toan\b",
            r"\bdinh dang\b",
            r"\bthuong mai dien tu\b",
            r"\bco hoi\b",
            r"\bthach thuc\b",
            r"\bphat trien\b",
            r"\btom tat\b",
            r"\bbai viet\b",
            r"\bthi truong\b",
            r"\bgiao dich\b",
        )
        for pat in phrase_patterns:
            if re.search(pat, norm):
                phrase_hits += 1

        if phrase_hits >= 1:
            return True

        tokens = [tok for tok in norm.split(' ') if len(tok) >= 3]
        if len(tokens) < 2:
            return False
        single_hits = 0
        viet_tokens = {
            'nghien', 'cuu', 'thong', 'lieu', 'rang', 'buoc',
            'truong', 'khoa', 'sinh', 'vien', 'giang', 'lop',
            'mssv', 'mo', 'ta', 'dia', 'chi', 'dinh', 'dang',
            'bao', 'toan', 'viet', 'nam', 'can', 'tho',
            'thap', 'cao', 'de', 'kho', 'trung', 'binh', 'linh', 'hoat',
            'thuong', 'mai', 'dien', 'tu', 'hoi', 'thach', 'thuc',
            'phat', 'trien', 'tom', 'tat', 'bai', 'thi', 'truong',
            'giao', 'dich', 'hoi', 'nhap', 'chinh', 'sach'
        }
        for tok in tokens:
            if tok in viet_tokens:
                single_hits += 1
        return single_hits >= 2

    @staticmethod
    def _normalize_ascii_phrase(text: str) -> str:
        s = (text or '').strip().lower()
        if not s:
            return ''
        try:
            norm = unicodedata.normalize('NFD', s)
            norm = ''.join(ch for ch in norm if unicodedata.category(ch) != 'Mn')
        except Exception:
            norm = s
        norm = norm.replace('đ', 'd')
        norm = re.sub(r'[^a-z0-9\s]', ' ', norm)
        norm = re.sub(r'\s+', ' ', norm).strip()
        return norm

    def _glossary_fallback_vi_to_en(self, source_text: str, target_code: str) -> str:
        if self._lang_root(target_code) != 'en':
            return ''

        src = (source_text or '').strip()
        if not src or len(src) > 120:
            return ''

        key = self._normalize_ascii_phrase(src)
        if not key:
            return ''

        # Focused glossary for common DOCX table/header terms that are frequently left unchanged.
        glossary = {
            'phuong phap': 'Method',
            'chi phi': 'Cost',
            'chat luong': 'Quality',
            'do phuc tap': 'Complexity',
            'kha nang cap nhat': 'Update capabilities',
            'de': 'Easy',
            'kho': 'Difficult',
            'trung binh': 'Average',
            'cao': 'High',
            'thap': 'Low',
            'linh hoat': 'Flexible',
            'dat nuoc': 'country',
            'thang canh': 'scenic spot',
            'noi tieng': 'famous',
            'long hieu khach': 'hospitality',
            'viet nam': 'Vietnam',
        }

        return glossary.get(key, '')

    def _should_retry_google_unchanged(self, source_text: str, translated_text: str, target_code: str, *, context=None) -> bool:
        src = (source_text or "").strip()
        out = (translated_text or "").strip()
        if not src or not out:
            return False
        if src != out:
            return False
        if self._is_email_or_url_only(src):
            return False

        target_root = self._lang_root(target_code)
        if not target_root:
            return False

        # Most frequent miss in this project: Vietnamese source stays unchanged when target is non-Vietnamese.
        if target_root != 'vi' and self._looks_vietnamese_like_text(src):
            return True

        # Reverse direction: English-ish text remains unchanged when target is Vietnamese.
        if target_root == 'vi' and (not self._looks_vietnamese_text(src)) and re.search(r"[A-Za-z]", src):
            return True

        # For document contexts, also retry unchanged long-ish lines that contain letters.
        ctx = (str(context or '').strip().lower())
        if ctx.startswith('document_') and len(src) >= 8 and re.search(r"[A-Za-zÀ-ỹ]", src):
            return True

        return False

    def _guess_google_forced_source(self, source_text: str, target_code: str) -> str:
        src = (source_text or '').strip()
        if not src:
            return ''

        target_root = self._lang_root(target_code)
        if not target_root:
            return ''

        if self._looks_vietnamese_like_text(src) and target_root != 'vi':
            return 'vi'

        if target_root == 'vi' and (not self._looks_vietnamese_text(src)) and re.search(r"[A-Za-z]", src):
            return 'en'

        return ''

    @staticmethod
    def _is_email_or_url_only(text: str) -> bool:
        s = (text or "").strip()
        if not s:
            return True
        email_full = re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", s)
        url_full = re.fullmatch(r"(?:https?://\S+|www\.\S+)", s, flags=re.IGNORECASE)
        if email_full or url_full:
            return True

        # Allow punctuation wrappers around raw email/url tokens.
        cleaned = re.sub(r"[\s,;:()\[\]<>\"']+", " ", s).strip()
        if not cleaned:
            return True
        tokens = [t for t in cleaned.split(" ") if t]
        if not tokens:
            return True
        for tok in tokens:
            if not (
                re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", tok)
                or re.fullmatch(r"(?:https?://\S+|www\.\S+)", tok, flags=re.IGNORECASE)
            ):
                return False
        return True

    def _is_already_target_language(self, text: str, target_code: str) -> bool:
        s = (text or "").strip()
        if not s:
            return True

        target_root = self._lang_root(target_code)
        if not target_root:
            return False

        # Cheap deterministic guards first.
        if target_root == "vi" and self._looks_vietnamese_text(s):
            return True
        if target_root == "en" and self._looks_already_english_text(s):
            return True

        # IMPORTANT: For text translation we default to non-AI checks only,
        # so this guard never spends OpenRouter/OpenAI tokens.
        use_ai_detect = (os.getenv('TEXT_LANG_DETECT_USE_AI') or '').strip().lower() in ('1', 'true', 'yes', 'on')
        if not use_ai_detect:
            return False

        letter_count = len(re.findall(r"[A-Za-zÀ-ỹ]", s))
        if letter_count < 4 or len(s) > 320:
            return False

        key = f"{target_root}::{s[:320]}"
        if key in self._lang_detect_cache:
            return bool(self._lang_detect_cache[key])

        try:
            det = self.detect_language(s)
            det_root = self._lang_root(str(det.get("language_code", "")))
            conf = float(det.get("confidence", 0.0) or 0.0)
            is_target = bool(det_root and det_root == target_root and conf >= 0.84)
            self._lang_detect_cache[key] = is_target
            return is_target
        except Exception:
            # Detection is best-effort; never block translation on detector errors.
            return False

    def _looks_already_english_text(self, text: str) -> bool:
        """Conservative detector for document fragments already in English."""
        s = (text or "").strip()
        if not s:
            return False

        # Bibliography/reference lines are often already English. Re-translating
        # them changes titles, author names, journal names, and breaks citations.
        if re.search(r"^\s*(?:\[\d+\]|\d{1,3}[.)])\s+", s):
            if re.search(
                r"\b(?:doi|journal|proceedings|conference|university|press|google|llc|index|report|"
                r"development|consumer|trust|e-?commerce|vietnamese|vietnam)\b",
                s,
                flags=re.IGNORECASE,
            ):
                return True

        if self._looks_vietnamese_text(s):
            return False

        # Short all-caps English headings.
        if re.fullmatch(r"[A-Z0-9][A-Z0-9\s&/(),.:;\-]{2,80}", s):
            english_heading_words = {
                "references", "abstract", "introduction", "conclusion", "method",
                "methods", "results", "discussion", "appendix", "table", "figure",
                "chapter", "section", "contents",
            }
            words = {w.lower() for w in re.findall(r"[A-Z]{3,}", s)}
            if words & english_heading_words:
                return True

        letters = re.findall(r"[A-Za-z]", s)
        if len(letters) < 4:
            return False

        ascii_words = re.findall(r"[A-Za-z]{2,}", s)
        if not ascii_words:
            return False

        english_stopwords = {
            "the", "and", "of", "in", "to", "for", "with", "on", "by", "from",
            "as", "is", "are", "was", "were", "that", "this", "these", "those",
            "using", "used", "affecting", "consumer", "trust", "development",
            "report", "index", "journal", "digital", "economy",
        }
        norm_words = [w.lower() for w in ascii_words]
        stop_hits = sum(1 for w in norm_words if w in english_stopwords)
        if stop_hits >= 2:
            return True

        # Mostly ASCII with no Vietnamese-like ASCII phrase: likely an English
        # name/title/code fragment, so leave it untouched for EN target.
        ascii_ratio = len(re.findall(r"[\x00-\x7F]", s)) / max(1, len(s))
        if ascii_ratio >= 0.96 and not self._looks_vietnamese_like_text(s):
            if len(norm_words) >= 3:
                return True

        return False

    def _should_skip_translation_request(self, text: str, source_lang: str, target_code: str) -> bool:
        s = "" if text is None else str(text)
        core = s.strip()
        if not core:
            return True

        src_root = self._lang_root(source_lang)
        tgt_root = self._lang_root(target_code)
        if src_root and tgt_root and src_root == tgt_root and src_root != "auto":
            return True

        if core.lower() in ("email", "e-mail", "url", "http", "https", "www"):
            return True

        if self._is_email_or_url_only(core):
            return True

        return self._is_already_target_language(core, target_code)

    def _openai_translate(self, text, source_lang, target_lang, target_code, *, context=None, model_override=None):
        """Dịch bằng OpenAI/OpenRouter. Dùng cho mọi ngôn ngữ (kể cả DeepL không hỗ trợ)."""
        if not self.openai_client:
            return None
        target_name = CODE_TO_NAME.get(target_code, target_lang)
        source_name = CODE_TO_NAME.get(source_lang.lower(), source_lang) if source_lang and source_lang != 'auto' else None
        
        # Use comprehensive system prompt
        system_prompt = self._get_system_prompt(target_name, source_name, context=context)
        default_model = 'google/gemini-2.5-flash' if self._using_openrouter else 'gpt-4o-mini'
        model = (model_override or os.getenv('AI_MODEL', default_model) or default_model).strip() or default_model
        rescue_prompt = (
            f"Translate this text to {target_name}. Return only the translation. "
            f"Keep line breaks and spacing exactly. No explanations."
        )
        try:
            try:
                max_tokens = int(os.getenv('AI_MAX_TOKENS', '900'))
            except Exception:
                max_tokens = 900
            if context == 'document_docx_batch':
                try:
                    floor = int(os.getenv('AI_MAX_TOKENS_DOCX_BATCH', '4096'))
                except Exception:
                    floor = 4096
                max_tokens = max(max_tokens, max(512, floor))
            if context == 'document_docx_line':
                try:
                    floor = int(os.getenv(
                        'AI_MAX_TOKENS_DOCX_LINE',
                        os.getenv('AI_MAX_TOKENS_DOCX_BATCH', '2048'),
                    ))
                except Exception:
                    floor = 2048
                max_tokens = max(max_tokens, max(512, floor))
            if context == 'document_pdf':
                try:
                    floor = int(os.getenv('AI_MAX_TOKENS_PDF', os.getenv('AI_MAX_TOKENS_PDF_IR', '2048')))
                except Exception:
                    floor = 2048
                max_tokens = max(max_tokens, max(256, floor))
            if max_tokens < 64:
                max_tokens = 64
            _tok_cap = 8192 if context == 'document_docx_batch' else (4096 if context == 'document_pdf' else 2048)
            if max_tokens > _tok_cap:
                max_tokens = _tok_cap

            attempt_tokens = [max_tokens]
            last_error = None

            for prompt in (system_prompt, rescue_prompt):
                for tok in attempt_tokens:
                    try:
                        response = self.openai_client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": prompt},
                                {"role": "user", "content": text}
                            ],
                            max_tokens=tok,
                            temperature=0
                        )
                        content = (response.choices[0].message.content or "").strip()
                        if self._looks_like_instruction_echo(text, content):
                            print("Discarded suspicious AI output (prompt/instruction echo). Retrying...")
                            continue
                        return content
                    except Exception as inner_e:
                        last_error = inner_e
                        msg = str(inner_e)
                        m = re.search(r"can only afford\s+(\d+)", msg, flags=re.IGNORECASE)
                        if m:
                            affordable = int(m.group(1))
                            fallback_tok = max(64, min(affordable - 32, tok - 64))
                            if fallback_tok >= 64 and fallback_tok < tok and fallback_tok not in attempt_tokens:
                                attempt_tokens.append(fallback_tok)
                                continue
                        break

            if last_error:
                raise last_error
            raise RuntimeError("AI translation failed: output rejected as invalid/suspicious")
        except Exception as e:
            # Surface API errors with their message so the caller can detect credit or rate issues
            raise RuntimeError(f"AI translation failed: {e}") from e

    # ── Language detection ───────────────────────────────────────────────

    def detect_language(self, text: str) -> dict:
        """Detect language of *text* via the AI provider.

        Returns ``{"language_code", "language_name", "confidence", "mixed"}``.
        """
        if not text or not text.strip():
            return {"language_code": "und", "language_name": "Undetermined", "confidence": 0.0, "mixed": False}

        if not self.openai_client:
            raise RuntimeError("AI provider not configured")

        system_prompt = (
            "Detect the language of the following text.\n\n"
            "Return ONLY a JSON object:\n"
            "{\n"
            '  "language_code": "en",\n'
            '  "language_name": "English",\n'
            '  "confidence": 0.99,\n'
            '  "mixed": false\n'
            "}\n\n"
            "Rules:\n"
            "- Use ISO 639-1 codes (en, vi, zh, ja, ko, fr, de, es, etc.)\n"
            '- If text contains multiple languages, set "mixed": true and report the dominant language\n'
            "- If text is too short to detect reliably, set confidence below 0.7\n"
            "- Do NOT add any explanation"
        )

        sample = text.strip()[:1500]
        default_model = 'google/gemini-2.5-flash' if self._using_openrouter else 'gpt-4o-mini'
        model = os.getenv('AI_MODEL', default_model)

        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": sample},
                ],
                max_tokens=128,
                temperature=0,
            )
            out = (response.choices[0].message.content or "").strip()
        except Exception as e:
            raise RuntimeError(f"Language detection failed: {e}") from e

        import json as _json
        # Strip markdown code fences
        if out.startswith("```"):
            import re as _re
            out = _re.sub(r"^```(?:json)?\s*", "", out)
            out = _re.sub(r"\s*```$", "", out)

        try:
            result = _json.loads(out)
        except _json.JSONDecodeError:
            import re as _re
            m = _re.search(r"\{[^}]+\}", out)
            if m:
                result = _json.loads(m.group(0))
            else:
                return {"language_code": "und", "language_name": "Undetermined", "confidence": 0.0, "mixed": False}

        return {
            "language_code": str(result.get("language_code", "und")).strip().lower(),
            "language_name": str(result.get("language_name", "Undetermined")).strip(),
            "confidence": float(result.get("confidence", 0.0)),
            "mixed": bool(result.get("mixed", False)),
        }

    def _to_deepl_target_lang(self, target_lang: str) -> str:
        # Accept both plain codes (en, en-US) and labels like "English (en)".
        normalized = self._to_google_lang_code(target_lang, fallback='')
        raw = (normalized or target_lang or '').strip().lower().replace('_', '-')
        if not raw:
            return ''
        if raw in DEEPL_TARGET_MAP:
            return DEEPL_TARGET_MAP[raw]
        root = raw.split('-')[0]
        return DEEPL_TARGET_MAP.get(root, '')

    def _to_deepl_source_lang(self, source_lang: str):
        normalized = self._to_google_lang_code(source_lang, fallback='auto')
        raw = (normalized or source_lang or '').strip().lower().replace('_', '-')
        if not raw or raw in ('auto', 'detect'):
            return None
        if raw in ('zh', 'zh-cn', 'zh-sg', 'zh-hans', 'zh-tw', 'zh-hk', 'zh-mo', 'zh-hant'):
            return 'ZH'

        mapped = DEEPL_TARGET_MAP.get(raw) or DEEPL_TARGET_MAP.get(raw.split('-')[0])
        if not mapped:
            return None
        # Source codes should not use regional variants for DeepL API.
        return mapped.split('-')[0]

    def _deepl_translate(self, text, source_lang, target_lang):
        if not self.deepl_translator:
            raise RuntimeError("DeepL API key is not configured")

        target_code = self._to_deepl_target_lang(target_lang)
        if not target_code:
            raise ValueError(f"Unsupported target language for DeepL: {target_lang}")

        kwargs = {'target_lang': target_code}
        source_code = self._to_deepl_source_lang(source_lang)
        if source_code:
            kwargs['source_lang'] = source_code

        try:
            result = self.deepl_translator.translate_text(str(text), **kwargs)
            out = str(getattr(result, 'text', result) or '').strip()
            if not out:
                raise RuntimeError("DeepL returned empty result")
            return out
        except Exception as e:
            raise RuntimeError(f"DeepL translation failed: {e}") from e

    def _gemini_rest_translate(self, text, source_lang, target_lang, *, context=None):
        api_key = (self._gemini_api_key or '').strip()
        if not api_key:
            raise RuntimeError("Gemini API key is not configured")

        model = self._get_gemini_direct_model()
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        target_code = self._to_google_lang_code(target_lang, fallback=(target_lang or '').strip().lower())
        target_name = CODE_TO_NAME.get(target_code, target_lang)
        source_code = self._to_google_lang_code(source_lang, fallback=(source_lang or '').strip().lower())
        source_name = CODE_TO_NAME.get(source_code, source_lang) if source_code and source_code != 'auto' else None

        system_prompt = self._get_system_prompt(target_name, source_name, context=context)
        prompt = f"{system_prompt}\n\nText:\n{text}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "topP": 0.95,
            },
        }

        try:
            resp = requests.post(
                endpoint,
                params={"key": api_key},
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get('candidates') or []
            if not candidates:
                raise RuntimeError("No candidates returned by Gemini")

            parts = (((candidates[0] or {}).get('content') or {}).get('parts') or [])
            out = ''.join(str((p or {}).get('text') or '') for p in parts).strip()
            if not out:
                raise RuntimeError("Gemini returned empty result")
            if self._looks_like_instruction_echo(text, out):
                raise RuntimeError("Gemini output rejected as invalid/suspicious")
            return out
        except Exception as e:
            raise RuntimeError(f"Gemini translation failed: {e}") from e

    def _gemini_translate(self, text, source_lang, target_lang, target_code, *, context=None):
        # Prefer OpenRouter (google/gemini-2.5-flash) when configured; direct Gemini API is fallback.
        direct_error = None
        openrouter_error = None
        openrouter_model = self._get_gemini_openrouter_model()

        if self.openai_client and self._using_openrouter:
            try:
                out = self._openai_translate(
                    text,
                    source_lang,
                    target_lang,
                    target_code,
                    context=context,
                    model_override=openrouter_model,
                )
                if out:
                    return out
            except Exception as e:
                openrouter_error = e
                try:
                    print(f"Gemini via OpenRouter failed, trying direct Gemini fallback: {e}")
                except Exception:
                    pass

        if self._gemini_api_key:
            try:
                return self._gemini_rest_translate(text, source_lang, target_lang, context=context)
            except Exception as e:
                direct_error = e
                try:
                    print(f"Gemini direct API failed: {e}")
                except Exception:
                    pass

        if openrouter_error is not None and direct_error is not None:
            raise RuntimeError(
                f"Gemini translation failed via OpenRouter ({openrouter_error}) and direct Gemini API ({direct_error})"
            ) from direct_error
        if openrouter_error is not None:
            raise RuntimeError(f"Gemini translation failed via OpenRouter ({openrouter_error})") from openrouter_error
        if direct_error is not None:
            raise RuntimeError(f"Gemini translation failed via direct Gemini API ({direct_error})") from direct_error

        # No Gemini route available at all.
        raise RuntimeError("Gemini translation is not configured (missing OPENROUTER_API_KEY / GEMINI_API_KEY)")

    def translate_text(self, text, source_lang, target_lang, context=None, provider=None):
        if target_lang is None or not str(target_lang).strip():
            raise ValueError("target_lang is required")
        if text is None:
            return ""
        target_lang = str(target_lang).strip()
        source = (str(source_lang).strip() if source_lang is not None else 'auto') or 'auto'
        t = self._to_google_lang_code(target_lang, fallback=target_lang.lower())
        s = self._to_google_lang_code(source, fallback=source.lower())

        # Skip translation requests for already-target-language text and
        # non-translatable units (email/url-only). This avoids unnecessary
        # API calls and prevents redundant bilingual insertions.
        if self._should_skip_translation_request(text, s, t):
            return str(text)

        provider_name = self._get_effective_translation_provider(provider)
        document_context = str(context or '').strip().lower().startswith('document_')
        allow_document_google_fallback = (
            str(os.getenv('DOCUMENT_TRANSLATION_ALLOW_GOOGLE_FALLBACK', '0')).strip().lower()
            in ('1', 'true', 'yes', 'on')
        )
        provider_error = None
        if provider_name == 'deepl':
            try:
                return self._deepl_translate(text, source_lang, target_lang)
            except Exception as e:
                provider_error = e
                if document_context and not allow_document_google_fallback:
                    raise RuntimeError(
                        f"DeepL failed and Google fallback is disabled for document quality: {e}"
                    ) from e
                try:
                    print(f"DeepL failed, falling back to Google Translate: {e}")
                except Exception:
                    pass
        if provider_name == 'gemini':
            try:
                return self._gemini_translate(text, source_lang, target_lang, t, context=context)
            except Exception as e:
                provider_error = e
                # Secondary fallback for Gemini failures: try DeepL when possible.
                try:
                    if self.deepl_translator is not None:
                        return self._deepl_translate(text, source_lang, target_lang)
                except Exception as deepl_e:
                    try:
                        print(f"Gemini fallback to DeepL also failed, using Google Translate fallback: {deepl_e}")
                    except Exception:
                        pass
                try:
                    print(f"Gemini failed, falling back to Google Translate: {e}")
                except Exception:
                    pass
                if document_context and not allow_document_google_fallback:
                    raise RuntimeError(
                        f"Gemini failed and Google fallback is disabled for document quality: {e}"
                    ) from e

        src_code = self._to_google_lang_code(source, fallback='auto')
        dst_code = self._to_google_lang_code(target_lang, fallback='')
        if not dst_code:
            raise ValueError(f"Unsupported target language for Google Translate: {target_lang}")

        def _retry_with_forced_source_if_needed(current_out: str) -> str:
            out_now = str(current_out or '').strip()
            if not out_now:
                return out_now
            if not self._should_retry_google_unchanged(str(text), out_now, dst_code, context=context):
                return out_now

            forced_src = self._guess_google_forced_source(str(text), dst_code)
            if not forced_src:
                return out_now
            if forced_src == src_code:
                return out_now

            try:
                client2 = self._get_googletrans_client()
                if client2 is not None:
                    forced_result = client2.translate(str(text), src=forced_src, dest=dst_code)
                    forced_out = str(getattr(forced_result, 'text', '') or '').strip()
                    if forced_out:
                        return forced_out
            except Exception as e:
                try:
                    print(f"googletrans forced-source retry failed, using web fallback: {e}")
                except Exception:
                    pass

            try:
                forced_web_out = self._google_web_translate(str(text), forced_src, dst_code)
                if forced_web_out:
                    return forced_web_out
            except Exception:
                pass

            # Final deterministic fallback for very short VI table/header labels.
            glossary_out = self._glossary_fallback_vi_to_en(str(text), dst_code)
            if glossary_out:
                return glossary_out

            return out_now

        try:
            client = self._get_googletrans_client()
            if client is not None:
                try:
                    result = client.translate(str(text), src=src_code, dest=dst_code)
                    out = str(getattr(result, 'text', '') or '').strip()
                    if out:
                        return _retry_with_forced_source_if_needed(out)
                except Exception as e:
                    try:
                        print(f"googletrans client translate failed, using web fallback: {e}")
                    except Exception:
                        pass

            out = self._google_web_translate(str(text), src_code, dst_code)
            if out:
                return _retry_with_forced_source_if_needed(out)
            raise RuntimeError("Google Translate returned empty result")
        except Exception as e:
            if provider_error is not None:
                raise RuntimeError(
                    f"{provider_name.title()} failed ({provider_error}); Google fallback failed: {e}"
                ) from e
            raise RuntimeError(f"Google Translate failed: {e}")

    def translate_html(self, html, source_lang, target_lang, provider=None):
        """Translate an HTML string while preserving tags. We translate text nodes only."""
        try:
            from bs4 import BeautifulSoup
            from bs4.element import NavigableString
        except Exception as e:
            raise RuntimeError("BeautifulSoup is required for HTML translation. Install 'beautifulsoup4'.") from e

        soup = BeautifulSoup(html, "html.parser")
        # Collect text nodes to translate
        text_nodes = []
        for element in soup.find_all(string=True):
            parent_name = element.parent.name if element.parent else ''
            # Skip non-visible or script/style/code/pre content
            if parent_name in ('script', 'style', 'code', 'pre', 'noscript'):
                continue
            text = str(element).strip()
            if text:
                text_nodes.append(element)

        # Translate each text node individually (simple; can be optimized by batching)
        # IMPORTANT: preserve leading/trailing whitespace exactly to keep original formatting.
        for node in text_nodes:
            original = str(node)
            try:
                # Keep surrounding whitespace exactly as-is (including newlines)
                leading_ws = original[: len(original) - len(original.lstrip())]
                trailing_ws = original[len(original.rstrip()):]
                core = original[len(leading_ws): len(original) - len(trailing_ws)]

                # If core is empty after trimming, skip translation
                if not core or not core.strip():
                    continue

                translated_core = self.translate_text(core, source_lang, target_lang, provider=provider)
                # Do NOT collapse whitespace. Only trim accidental outer spaces/newlines.
                translated_core = (translated_core or "").strip()

                # Replace the node content with translated text (preserving tags)
                node.replace_with(f"{leading_ws}{translated_core}{trailing_ws}")
            except Exception as e:
                # On failure, keep original text to avoid corrupting HTML
                print(f"HTML node translation failed, keeping original: {e}")
                continue

        return str(soup)

    # ── AI Vision OCR (no Tesseract needed) ──────────────────────────────

    def _ai_vision_ocr(self, image_path):
        """Extract text from an image using the AI Vision model (GPT-4o / OpenRouter vision model).

        This does NOT require Tesseract — it sends the image to the configured AI provider.
        Set AI_VISION_MODEL in .env to pick a vision-capable model (default: auto-detect).
        """
        if not self.openai_client:
            raise RuntimeError("AI provider not configured: set OPENAI_API_KEY or OPENROUTER_API_KEY in backend/.env")

        import base64
        try:
            from PIL import Image as _PILImage
        except Exception:
            _PILImage = None

        vision_model = (os.getenv('AI_VISION_MODEL') or '').strip()
        if not vision_model:
            # Fallback: use main model if it's known to support vision, else pick a sensible default
            main_model = os.getenv('AI_MODEL', '')
            _KNOWN_VISION = ('gpt-4o', 'gpt-4-turbo', 'gpt-4-vision', 'gemini', 'claude-3',
                             'claude-4', 'llama-4', 'qwen2.5-vl', 'qwen-2.5-vl',
                             'pixtral', 'internvl', 'mistral-small', 'gemma-3')
            if any(kw in main_model.lower() for kw in _KNOWN_VISION):
                vision_model = main_model
            else:
                vision_model = 'google/gemini-2.5-flash'

        # Read & encode image as base64 data-URI
        with open(image_path, 'rb') as f:
            raw = f.read()

        # Detect MIME
        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp', '.tif': 'image/tiff', '.tiff': 'image/tiff'}
        mime = mime_map.get(ext, 'image/png')

        # Resize very large images to save tokens/bandwidth
        try:
            if _PILImage:
                img = _PILImage.open(image_path)
                w, h = img.size
                if max(w, h) > 2048:
                    ratio = 2048.0 / max(w, h)
                    img = img.resize((int(w * ratio), int(h * ratio)), resample=_PILImage.BICUBIC)
                    import io as _io
                    buf = _io.BytesIO()
                    fmt = 'JPEG' if ext in ('.jpg', '.jpeg') else 'PNG'
                    if fmt == 'JPEG' and img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    img.save(buf, format=fmt, quality=85)
                    raw = buf.getvalue()
                    mime = 'image/jpeg' if fmt == 'JPEG' else 'image/png'
        except Exception:
            pass

        b64 = base64.b64encode(raw).decode('ascii')
        data_uri = f"data:{mime};base64,{b64}"

        try:
            response = self.openai_client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": "You are an OCR assistant. Extract ALL visible text from the image exactly as it appears. Return only the extracted text, nothing else. Preserve line breaks."},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": "Extract all text from this image."},
                    ]},
                ],
                max_tokens=2048,
                temperature=0,
            )
            content = response.choices[0].message.content
            return (content or "").strip()
        except Exception as e:
            raise RuntimeError(f"AI Vision OCR failed: {e}") from e

    def _ai_vision_ocr_and_translate(self, image_path, target_lang):
        """OCR + translate an image in a single AI Vision call (efficient, no Tesseract).

        Also classifies the image type to recommend the best output mode:
        - 'text': image is a document/scan/reading passage → extract as plain text
        - 'image': image is a poster/banner/design/photo with text → overlay translation on image
        - 'both': image has mixed characteristics → return both text output and image overlay

        Returns: (ocr_text, translated_text, recommended_mode)
        """
        if not self.openai_client:
            raise RuntimeError("AI provider not configured")

        import base64
        try:
            from PIL import Image as _PILImage
        except Exception:
            _PILImage = None

        vision_model = (os.getenv('AI_VISION_MODEL') or '').strip()
        if not vision_model:
            main_model = os.getenv('AI_MODEL', '')
            _KNOWN_VISION = ('gpt-4o', 'gpt-4-turbo', 'gpt-4-vision', 'gemini', 'claude-3',
                             'claude-4', 'llama-4', 'qwen2.5-vl', 'qwen-2.5-vl',
                             'pixtral', 'internvl', 'mistral-small', 'gemma-3')
            if any(kw in main_model.lower() for kw in _KNOWN_VISION):
                vision_model = main_model
            else:
                vision_model = 'google/gemini-2.5-flash'

        with open(image_path, 'rb') as f:
            raw = f.read()

        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp'}
        mime = mime_map.get(ext, 'image/png')

        try:
            if _PILImage:
                img = _PILImage.open(image_path)
                w, h = img.size
                if max(w, h) > 2048:
                    ratio = 2048.0 / max(w, h)
                    img = img.resize((int(w * ratio), int(h * ratio)), resample=_PILImage.BICUBIC)
                    import io as _io
                    buf = _io.BytesIO()
                    fmt = 'JPEG' if ext in ('.jpg', '.jpeg') else 'PNG'
                    if fmt == 'JPEG' and img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    img.save(buf, format=fmt, quality=85)
                    raw = buf.getvalue()
                    mime = 'image/jpeg' if fmt == 'JPEG' else 'image/png'
        except Exception:
            pass

        b64 = base64.b64encode(raw).decode('ascii')
        data_uri = f"data:{mime};base64,{b64}"

        target_name = CODE_TO_NAME.get(target_lang.lower(), target_lang) if target_lang else target_lang

        try:
            response = self.openai_client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": (
                        f"You are an image classifier, OCR, and translation assistant.\n\n"
                        f"STEP 1 - CLASSIFY the image into exactly one of three categories:\n"
                        f"  'text' = The image is primarily a TEXT DOCUMENT. Examples:\n"
                        f"    - A scanned document, article, book page, essay, letter\n"
                        f"    - A screenshot of text, chat messages, code\n"
                        f"    - A reading passage written on any background (even on a photo)\n"
                        f"    - Any image where the MAIN PURPOSE is to convey text/paragraphs to read\n"
                        f"  'image' = The image is primarily a VISUAL DESIGN with some text. Examples:\n"
                        f"    - A poster, banner, advertisement, flyer\n"
                        f"    - An infographic, diagram, chart with labels\n"
                        f"    - A photo with captions or watermarks\n"
                        f"    - A logo, title card, social media graphic\n"
                        f"    - Any image where the MAIN PURPOSE is visual/graphical and text is decorative\n\n"
                        f"  'both' = MIXED content where both outputs are useful. Examples:\n"
                        f"    - A visual design that also contains long readable paragraphs\n"
                        f"    - A mixed document where you should keep design and still provide editable text\n"
                        f"    - Cases where classification between text/image is ambiguous\n\n"
                        f"STEP 2 - Extract ALL visible text exactly as it appears.\n"
                        f"STEP 3 - Translate the extracted text to {target_name}.\n\n"
                        f"Return in this EXACT format (markers must be on their own lines):\n"
                        f"IMAGE_TYPE_START\n<text or image or both>\nIMAGE_TYPE_END\n"
                        f"OCR_TEXT_START\n<extracted original text>\nOCR_TEXT_END\n"
                        f"TRANSLATED_START\n<translated text>\nTRANSLATED_END"
                    )},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": f"Classify this image, extract all text, and translate to {target_name}."},
                    ]},
                ],
                max_tokens=3000,
                temperature=0,
            )
            content = (response.choices[0].message.content or "").strip()

            # Parse structured output
            ocr_text = ""
            translated_text = ""
            recommended_mode = "text"  # safe default
            import re as _re

            # Parse image type classification
            type_match = _re.search(r'IMAGE_TYPE_START\s*\n\s*(text|image|both)\s*\n\s*IMAGE_TYPE_END', content, _re.IGNORECASE)
            if type_match:
                recommended_mode = type_match.group(1).strip().lower()
                if recommended_mode not in ('text', 'image', 'both'):
                    recommended_mode = 'text'

            ocr_match = _re.search(r'OCR_TEXT_START\s*\n(.*?)\nOCR_TEXT_END', content, _re.DOTALL)
            trans_match = _re.search(r'TRANSLATED_START\s*\n(.*?)\nTRANSLATED_END', content, _re.DOTALL)
            if ocr_match:
                ocr_text = ocr_match.group(1).strip()
            if trans_match:
                translated_text = trans_match.group(1).strip()

            # Fallback: if markers weren't followed, try to split by common patterns
            if not ocr_text and not translated_text:
                # Maybe model returned plain text — treat entire response as translated
                ocr_text = content
                try:
                    translated_text = self.translate_text(content, 'auto', target_lang)
                except Exception:
                    translated_text = content

            print(f"[AI Vision] Image classified as '{recommended_mode}': {os.path.basename(image_path)}")
            return (ocr_text, translated_text, recommended_mode)
        except Exception as e:
            raise RuntimeError(f"AI Vision OCR+translate failed: {e}") from e

    def _ai_vision_ocr_bboxes(self, image_path, ocr_langs=None):
        """OCR an image and return line-level bounding boxes using the AI Vision model.

        Output format (Python):
            [{'text': '...', 'bbox': [x0, y0, x1, y1]}, ...]

        Where bbox coordinates are NORMALIZED floats in [0..1] relative to the image size.
        This makes the result robust even if the provider resizes the image internally.
        """
        if not self.openai_client:
            raise RuntimeError("AI provider not configured")

        import base64
        import json
        import re as _re

        vision_model = (os.getenv('AI_VISION_MODEL') or '').strip()
        if not vision_model:
            main_model = os.getenv('AI_MODEL', '')
            _KNOWN_VISION = (
                'gpt-4o', 'gpt-4-turbo', 'gpt-4-vision', 'gemini', 'claude-3',
                'claude-4', 'llama-4', 'qwen2.5-vl', 'qwen-2.5-vl',
                'pixtral', 'internvl', 'mistral-small', 'gemma-3'
            )
            if any(kw in main_model.lower() for kw in _KNOWN_VISION):
                vision_model = main_model
            else:
                vision_model = 'google/gemini-2.5-flash'

        with open(image_path, 'rb') as f:
            raw = f.read()

        ext = os.path.splitext(image_path)[1].lower()
        mime_map = {
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp'
        }
        mime = mime_map.get(ext, 'image/png')
        b64 = base64.b64encode(raw).decode('ascii')
        data_uri = f"data:{mime};base64,{b64}"

        langs_hint = (ocr_langs or os.getenv('OCR_LANGS_DEFAULT') or '').strip()
        if langs_hint:
            langs_hint = f"OCR languages hint: {langs_hint}. "

        system_prompt = (
            "You are an OCR system that returns line-level bounding boxes. "
            "Extract ALL visible text lines from the image and return JSON only. "
            "For each line, return: text and bbox. "
            "bbox MUST be normalized floats [x0,y0,x1,y1] in range [0,1], "
            "where (0,0) is the top-left of the image and (1,1) is the bottom-right. "
            "Return tight boxes that cover the rendered glyphs for that line. "
            "Do not include empty lines. Do not include any commentary or markdown. "
            f"{langs_hint}"
            "Return this exact JSON structure: {\"lines\": [{\"text\": \"...\", \"bbox\": [0,0,0,0]}]}"
        )

        try:
            response = self.openai_client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": "Extract text lines with normalized bounding boxes."},
                    ]},
                ],
                max_tokens=3000,
                temperature=0,
            )
            content = (response.choices[0].message.content or '').strip()

            # Extract JSON payload even if wrapped.
            m = _re.search(r'\{.*\}', content, _re.DOTALL)
            if not m:
                raise ValueError("No JSON object found in vision OCR bbox response")
            payload = json.loads(m.group(0))
            lines = payload.get('lines') if isinstance(payload, dict) else None
            if not isinstance(lines, list):
                raise ValueError("Invalid JSON: missing 'lines' array")

            out = []
            for ln in lines:
                if not isinstance(ln, dict):
                    continue
                text = (ln.get('text') or '').strip()
                bb = ln.get('bbox')
                if not text or not isinstance(bb, list) or len(bb) != 4:
                    continue
                try:
                    x0, y0, x1, y1 = [float(v) for v in bb]
                except Exception:
                    continue
                out.append({"text": text, "bbox": [x0, y0, x1, y1]})
            return out
        except Exception as e:
            raise RuntimeError(f"AI Vision OCR bbox failed: {e}") from e

    def ocr_image_to_bboxes(self, image_path, ocr_langs=None):
        """Public hook for FileService: OCR image -> line bboxes (API-based)."""
        return self._ai_vision_ocr_bboxes(image_path, ocr_langs=ocr_langs)

    # ── Tesseract check helper ───────────────────────────────────────────

    def _resolve_tesseract_cmd(self):
        """Resolve an executable path for Tesseract without importing pytesseract.

        This keeps Flask startup fast/stable on Windows where importing
        pytesseract may pull heavy deps (pandas/numpy) and slow down boot.
        """
        env_cmd = (os.getenv('TESSERACT_CMD') or '').strip().strip('"')

        candidates = []
        if env_cmd:
            candidates.append(env_cmd)

        found_on_path = shutil.which('tesseract')
        if found_on_path:
            candidates.append(found_on_path)

        if os.name == 'nt':
            candidates.extend([
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Tesseract-OCR\tesseract.exe",
            ])

        for cand in candidates:
            if not cand:
                continue
            c = str(cand).strip().strip('"')
            if not c:
                continue
            if os.path.isabs(c) or c.lower().endswith('.exe'):
                if os.path.exists(c):
                    return c
            else:
                resolved = shutil.which(c)
                if resolved:
                    return resolved
        return None

    def _is_tesseract_available(self):
        """Return True if Tesseract OCR executable is installed and reachable."""
        return bool(self._resolve_tesseract_cmd())

    # ── Public OCR methods (auto-fallback: Tesseract → AI Vision) ────────

    def ocr_image_to_text(self, image_path, ocr_langs=None):
        """Extract text from an image.

        Strategy:
        1. Try Tesseract OCR if installed (fast, free, offline).
        2. If Tesseract is not available, fall back to AI Vision model
           (uses the configured OpenAI/OpenRouter API — no install needed).
        """
        # ── Attempt Tesseract first ──
        if self._is_tesseract_available():
            try:
                return self._tesseract_ocr(image_path, ocr_langs)
            except Exception as e:
                print(f"Tesseract OCR failed, falling back to AI Vision: {e}")

        # ── Fallback: AI Vision ──
        if self.openai_client:
            print("Using AI Vision for OCR (Tesseract not available)")
            return self._ai_vision_ocr(image_path)

        raise RuntimeError(
            "OCR unavailable: Tesseract is not installed AND no AI provider configured. "
            "Either install Tesseract OCR, or set OPENAI_API_KEY / OPENROUTER_API_KEY in backend/.env."
        )

    def _tesseract_ocr(self, image_path, ocr_langs=None):
        """Extract text from an image using Tesseract OCR (original implementation)."""
        try:
            from PIL import Image
        except Exception as e:
            raise RuntimeError("Pillow is required for OCR. Install 'Pillow'.") from e

        try:
            import pytesseract
        except Exception as e:
            raise RuntimeError("pytesseract is required for OCR. Install 'pytesseract'.") from e

        resolved_cmd = self._resolve_tesseract_cmd()
        if resolved_cmd:
            pytesseract.pytesseract.tesseract_cmd = resolved_cmd
        else:
            raise RuntimeError(
                "OCR failed: tesseract is not installed or it's not in your PATH. "
                "Install Tesseract OCR, then either add it to PATH or set TESSERACT_CMD in backend/.env. "
                "Windows example: TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
            )

        langs = (ocr_langs or os.getenv('OCR_LANGS_DEFAULT') or 'eng').strip()
        if not langs:
            langs = 'eng'

        try:
            img = Image.open(image_path)
            # Normalize to a mode that OCR handles well
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            text = pytesseract.image_to_string(img, lang=langs)
            return text or ""
        except Exception as e:
            raise RuntimeError(f"OCR failed: {e}") from e

    def ocr_translate_overlay(self, image_path, source_lang, target_lang, ocr_langs=None, return_blocks: bool = False):
        """OCR an image, translate detected text, and render translated text back onto the image.

        Returns: (ocr_text, translated_text, png_bytes, recommended_mode)
              recommended_mode: 'text' or 'image' or 'both'.

                Strategy:
                - Prefer API Vision line-bboxes (when available) to render translated text back
                    into the original image while preserving layout.
                - Otherwise, if Tesseract is available: use bounding-box overlay.
                - If neither is available: fall back to AI Vision banner overlay.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception as e:
            raise RuntimeError("Pillow is required for OCR. Install 'Pillow'.") from e

        target_code = (str(target_lang or '').strip().lower() or 'auto')
        target_base = target_code.split('-')[0]
        # For RTL targets, force AI-vision banner overlay to avoid broken glyph shaping
        # and unstable per-box placement from Tesseract line rendering.
        if target_base in ('ar', 'fa', 'ur', 'he', 'iw'):
            res = self._ai_vision_overlay_fallback(image_path, source_lang, target_lang)
            if return_blocks:
                ocr_text, translated_text, png_bytes, recommended_mode = res
                return (ocr_text, translated_text, png_bytes, recommended_mode, [], 'B')
            return res

        # Prefer API-based bbox OCR for overlay (more portable than Tesseract).
        prefer_api_bbox = str(os.getenv('OCR_OVERLAY_USE_API', '1')).strip().lower() in ('1', 'true', 'yes', 'on')

        img = Image.open(image_path)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        original_rgba = img.convert('RGBA')
        base_img = original_rgba.copy()

        w_img, h_img = base_img.size

        # ---------------- API bbox OCR path (preferred) ----------------
        line_items = None
        if prefer_api_bbox and self.openai_client:
            try:
                bboxes = self._ai_vision_ocr_bboxes(image_path, ocr_langs=ocr_langs)
            except Exception as e:
                bboxes = None
                print(f"[OCR Overlay] API bbox OCR failed, falling back: {e}")

            if bboxes:
                items = []
                for it in bboxes:
                    try:
                        text = (it.get('text') or '').strip()
                        bb = it.get('bbox')
                        if not text or not bb or len(bb) != 4:
                            continue
                        x0, y0, x1, y1 = [float(v) for v in bb]
                        # Clamp
                        x0 = max(0.0, min(1.0, x0))
                        y0 = max(0.0, min(1.0, y0))
                        x1 = max(0.0, min(1.0, x1))
                        y1 = max(0.0, min(1.0, y1))
                        if x1 <= x0 or y1 <= y0:
                            continue

                        l = int(x0 * w_img)
                        t = int(y0 * h_img)
                        r = int(x1 * w_img)
                        b = int(y1 * h_img)

                        # Basic sanity filter
                        bw = max(1, r - l)
                        bh = max(1, b - t)
                        if bh > int(h_img * 0.25):
                            continue
                        if len(text) > 260:
                            continue

                        items.append({
                            'text': text,
                            'left': max(0, l),
                            'top': max(0, t),
                            'right': min(w_img, r),
                            'bottom': min(h_img, b),
                            'mean_conf': 100.0,
                        })
                    except Exception:
                        continue

                # Sort top-to-bottom then left-to-right
                if items:
                    line_items = sorted(items, key=lambda x: (x['top'], x['left']))

        # ---------------- Tesseract bbox OCR path (fallback) ----------------
        if line_items is None:
            # ── Check if Tesseract is available ──
            if not self._is_tesseract_available():
                # Use AI Vision banner fallback
                res = self._ai_vision_overlay_fallback(image_path, source_lang, target_lang)
                if return_blocks:
                    ocr_text, translated_text, png_bytes, recommended_mode = res
                    return (ocr_text, translated_text, png_bytes, recommended_mode, [], 'B')
                return res

            try:
                import pytesseract
                from pytesseract import Output
            except Exception:
                res = self._ai_vision_overlay_fallback(image_path, source_lang, target_lang)
                if return_blocks:
                    ocr_text, translated_text, png_bytes, recommended_mode = res
                    return (ocr_text, translated_text, png_bytes, recommended_mode, [], 'B')
                return res

            # Reuse existing resolver logic by calling _tesseract_ocr once to validate tesseract availability.
            # This also sets pytesseract.pytesseract.tesseract_cmd if needed.
            try:
                _ = self._tesseract_ocr(image_path, ocr_langs=ocr_langs)
            except Exception:
                res = self._ai_vision_overlay_fallback(image_path, source_lang, target_lang)
                if return_blocks:
                    ocr_text, translated_text, png_bytes, recommended_mode = res
                    return (ocr_text, translated_text, png_bytes, recommended_mode, [], 'B')
                return res

            langs = (ocr_langs or os.getenv('OCR_LANGS_DEFAULT') or 'eng').strip() or 'eng'

        if line_items is None:
            # OCR pass: use multi-PSM + upscale to catch small/header text,
            # but keep Tesseract's own line grouping to avoid merging many lines into one.
            def _run_ocr_lines(psm, pil_rgb, scale):
                config = f"--oem 3 --psm {int(psm)} -c preserve_interword_spaces=1"
                d = pytesseract.image_to_data(
                    pil_rgb,
                    lang=langs,
                    config=config,
                    output_type=Output.DICT,
                )
                n_ = len(d.get('text', []) or [])
                lines = {}
                for i in range(n_):
                    word = (d['text'][i] or '').strip()
                    if not word:
                        continue
                    try:
                        conf = float(d.get('conf', [])[i]) if d.get('conf') else -1
                    except Exception:
                        conf = -1

                    left = int(d.get('left', [0])[i] or 0)
                    top = int(d.get('top', [0])[i] or 0)
                    width = int(d.get('width', [0])[i] or 0)
                    height = int(d.get('height', [0])[i] or 0)
                    right = left + width
                    bottom = top + height

                    if scale and scale != 1.0:
                        left = int(left / scale)
                        top = int(top / scale)
                        right = int(right / scale)
                        bottom = int(bottom / scale)

                    key = (
                        int(d.get('block_num', [0])[i] or 0),
                        int(d.get('par_num', [0])[i] or 0),
                        int(d.get('line_num', [0])[i] or 0),
                    )
                    entry = lines.get(key)
                    if not entry:
                        lines[key] = {
                            'tokens': [(word, conf)],
                            'left': left,
                            'top': top,
                            'right': right,
                            'bottom': bottom,
                        }
                    else:
                        entry['tokens'].append((word, conf))
                        entry['left'] = min(entry['left'], left)
                        entry['top'] = min(entry['top'], top)
                        entry['right'] = max(entry['right'], right)
                        entry['bottom'] = max(entry['bottom'], bottom)

                out_lines = []
                for _, entry in lines.items():
                    tokens = entry.get('tokens') or []
                    # Prefer higher-confidence tokens for translation text, but keep bbox regardless.
                    hi = [w for (w, c) in tokens if c == -1 or c >= 30]
                    mid = [w for (w, c) in tokens if c == -1 or c >= 15]
                    words_for_text = hi or mid
                    text_line = ' '.join(words_for_text).strip()
                    if not text_line:
                        continue
                    confs = [c for (_, c) in tokens if c != -1]
                    mean_conf = (sum(confs) / len(confs)) if confs else 100.0
                    out_lines.append({
                        'text': text_line,
                        'left': int(entry['left']),
                        'top': int(entry['top']),
                        'right': int(entry['right']),
                        'bottom': int(entry['bottom']),
                        'mean_conf': float(mean_conf),
                    })
                return out_lines

            # Upscale for OCR if the image is not huge (helps catch small text)
            ocr_rgb = original_rgba.convert('RGB')
            w0, h0 = ocr_rgb.size
            scale = 1.0
            try:
                if max(w0, h0) < 1600:
                    scale = 2.0
                    ocr_rgb = ocr_rgb.resize((int(w0 * scale), int(h0 * scale)), resample=Image.BICUBIC)
            except Exception:
                scale = 1.0

            candidates = []
            for psm in (6, 11):
                try:
                    candidates.extend(_run_ocr_lines(psm, ocr_rgb, scale))
                except Exception:
                    continue

            # Deduplicate overlapping lines between PSM passes (keep higher mean_conf)
            def _iou(a, b):
                ax1, ay1, ax2, ay2 = a
                bx1, by1, bx2, by2 = b
                ix1 = max(ax1, bx1)
                iy1 = max(ay1, by1)
                ix2 = min(ax2, bx2)
                iy2 = min(ay2, by2)
                iw = max(0, ix2 - ix1)
                ih = max(0, iy2 - iy1)
                inter = iw * ih
                if inter <= 0:
                    return 0.0
                area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
                area_b = max(1, (bx2 - bx1) * (by2 - by1))
                return inter / float(area_a + area_b - inter)

            filtered = []
            candidates.sort(key=lambda x: (-(x.get('mean_conf') or 0.0), x['top'], x['left']))
            for it in candidates:
                l, t, r, b = it['left'], it['top'], it['right'], it['bottom']
                # Quality gates: avoid "giant merged blocks" that will destroy the image.
                bw = max(1, r - l)
                bh = max(1, b - t)
                if bh > int(h_img * 0.22):
                    continue
                if len(it.get('text', '')) > 220:
                    continue
                text_trim = (it.get('text', '') or '').strip()
                # Ignore tiny noisy OCR fragments (e.g., random single letters on banners)
                if len(text_trim) <= 2 and not re.search(r'[0-9%$€£¥]', text_trim):
                    continue
                if len(text_trim) <= 4 and (it.get('mean_conf') or 0.0) < 45.0:
                    continue
                if (it.get('mean_conf') or 0.0) < 18.0 and len(it.get('text', '')) > 18:
                    continue

                bbox = (l, t, r, b)
                dup = False
                for keep in filtered:
                    kb = (keep['left'], keep['top'], keep['right'], keep['bottom'])
                    if _iou(bbox, kb) >= 0.72:
                        dup = True
                        break
                if not dup:
                    filtered.append(it)

            # Sort top-to-bottom, then left-to-right
            line_items = sorted(filtered, key=lambda x: (x['top'], x['left']))

        def _pick_font(font_size):
            font_path = (os.getenv('OCR_FONT_PATH') or '').strip() or None
            candidates = []
            if font_path:
                candidates.append(font_path)
            # Bundled NotoSans (works on any server)
            noto = _get_noto_font(is_bold=True)
            if noto:
                candidates.append(noto)
            noto_reg = _get_noto_font()
            if noto_reg:
                candidates.append(noto_reg)
            # System fallbacks (dev convenience)
            if os.name == 'nt':
                candidates.extend([
                    r"C:\Windows\Fonts\arialbd.ttf",
                    r"C:\Windows\Fonts\arial.ttf",
                ])
            candidates.extend([
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            ])
            for p in candidates:
                try:
                    if p and os.path.exists(p):
                        return ImageFont.truetype(p, font_size)
                except Exception:
                    continue
            return ImageFont.load_default()

        def _measure(draw, font, text):
            try:
                box = draw.textbbox((0, 0), text, font=font)
                return (box[2] - box[0], box[3] - box[1])
            except Exception:
                try:
                    return draw.textsize(text, font=font)
                except Exception:
                    return (len(text) * font.size, font.size)

        def _fit_font(draw, text, max_w, max_h):
            size = max(10, int(max_h * 0.85))
            for s in range(size, 9, -2):
                font = _pick_font(s)
                w, h = _measure(draw, font, text)
                if w <= max_w and h <= max_h:
                    return font
            return _pick_font(10)

        draw = ImageDraw.Draw(base_img)
        ocr_lines = []
        translated_lines = []
        blocks = []

        leader_re = re.compile(r"(\.{5,}|_{4,}|-{4,})")

        def _translate_preserve_form_leaders(text_line: str) -> str:
            raw = (text_line or '')
            if not raw.strip():
                return raw
            # If the whole line is just leaders/punct/whitespace, keep as-is.
            if leader_re.fullmatch(raw.strip()):
                return raw
            if not leader_re.search(raw):
                return self.translate_text(raw, source_lang, target_lang)

            parts = leader_re.split(raw)
            out_parts = []
            for i, part in enumerate(parts):
                if i % 2 == 1:
                    out_parts.append(part)
                    continue

                seg = part or ''
                if not seg.strip():
                    out_parts.append(seg)
                    continue
                # Skip translating segments that have no letters/numbers (avoid punctuation-only noise)
                if not re.search(r"[\w\u00C0-\u1EF9]", seg, flags=re.UNICODE):
                    out_parts.append(seg)
                    continue
                try:
                    out_parts.append(self.translate_text(seg, source_lang, target_lang))
                except Exception:
                    out_parts.append(seg)
            return ''.join(out_parts)

        def _clamp(v, lo, hi):
            return max(lo, min(hi, v))

        def _sample_bg_color(img_rgba, l, t, r, b):
            """Sample background color around a text box.

            We sample a few pixels just outside the OCR box corners to approximate
            the surrounding background. This avoids painting white blocks on dark
            backgrounds.
            """
            try:
                w, h = img_rgba.size
                # sample points just outside the box
                pts = [
                    (_clamp(l - 2, 0, w - 1), _clamp(t - 2, 0, h - 1)),
                    (_clamp(r + 2, 0, w - 1), _clamp(t - 2, 0, h - 1)),
                    (_clamp(l - 2, 0, w - 1), _clamp(b + 2, 0, h - 1)),
                    (_clamp(r + 2, 0, w - 1), _clamp(b + 2, 0, h - 1)),
                ]
                cols = []
                for x, y in pts:
                    px = img_rgba.getpixel((x, y))
                    if isinstance(px, int):
                        cols.append((px, px, px))
                    else:
                        cols.append((int(px[0]), int(px[1]), int(px[2])))
                if not cols:
                    return (255, 255, 255)
                rr = sum(c[0] for c in cols) // len(cols)
                gg = sum(c[1] for c in cols) // len(cols)
                bb = sum(c[2] for c in cols) // len(cols)
                return (rr, gg, bb)
            except Exception:
                return (255, 255, 255)

        def _pick_text_colors(bg_rgb):
            # Choose text/stroke colors based on background luminance
            try:
                lum = (0.2126 * bg_rgb[0] + 0.7152 * bg_rgb[1] + 0.0722 * bg_rgb[2])
            except Exception:
                lum = 255
            if lum < 128:
                # dark bg -> light text with dark stroke
                return ((255, 255, 255, 255), (0, 0, 0, 255))
            # light bg -> dark text with light stroke
            return ((0, 0, 0, 255), (255, 255, 255, 255))
        def _wrap_text_to_width(draw_obj, font_obj, text, max_w):
            # Greedy wrap by spaces; if a single word is too long, keep it as-is.
            words = (text or '').split()
            if not words:
                return ['']
            lines_out = []
            cur = words[0]
            for w in words[1:]:
                cand = cur + ' ' + w
                cw, _ = _measure(draw_obj, font_obj, cand)
                if cw <= max_w:
                    cur = cand
                else:
                    lines_out.append(cur)
                    cur = w
            lines_out.append(cur)
            return lines_out

        def _fit_font_wrapped(draw_obj, text, max_w, max_h):
            # Find largest font where wrapped text fits within (max_w,max_h)
            size = max(10, int(max_h * 0.85))
            for s in range(size, 9, -2):
                font = _pick_font(s)
                lines_ = _wrap_text_to_width(draw_obj, font, text, max_w)
                # Measure total height
                widths = []
                heights = []
                for ln in lines_:
                    w, h = _measure(draw_obj, font, ln)
                    widths.append(w)
                    heights.append(h)
                total_h = (sum(heights) + max(0, (len(heights) - 1) * int(s * 0.18)))
                max_line_w = max(widths) if widths else 0
                if max_line_w <= max_w and total_h <= max_h:
                    return font, lines_, total_h
            font = _pick_font(10)
            lines_ = _wrap_text_to_width(draw_obj, font, text, max_w)
            # best-effort height
            heights = [_measure(draw_obj, font, ln)[1] for ln in lines_]
            total_h = (sum(heights) + max(0, (len(heights) - 1) * int(font.size * 0.18)))
            return font, lines_, total_h

        # 1) Remove original text as naturally as possible.
        # Prefer OpenCV inpainting (keeps background texture), fallback to soft rectangle fill.
        use_inpaint = False
        inpainted_rgb = None
        try:
            import numpy as np  # type: ignore
            import cv2  # type: ignore

            if line_items:
                w_img, h_img = base_img.size
                mask = np.zeros((h_img, w_img), dtype=np.uint8)
                # Larger pad helps avoid leaving edge artifacts (especially for the first/header line)
                for item in line_items:
                    ih = max(1, int(item['bottom']) - int(item['top']))
                    pad = max(8, int(ih * 0.35))
                    l = max(0, int(item['left']) - pad)
                    t = max(0, int(item['top']) - pad)
                    r = min(w_img, int(item['right']) + pad)
                    b = min(h_img, int(item['bottom']) + pad)
                    if r > l and b > t:
                        mask[t:b, l:r] = 255

                # Dilate mask slightly to cover anti-aliased edges
                try:
                    kernel = np.ones((3, 3), np.uint8)
                    mask = cv2.dilate(mask, kernel, iterations=1)
                except Exception:
                    pass

                # Convert to BGR for OpenCV
                rgb = np.array(original_rgba.convert('RGB'))
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                # Inpaint to fill text regions from surrounding pixels
                inpainted = cv2.inpaint(bgr, mask, 4, cv2.INPAINT_TELEA)
                inpainted_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)
                use_inpaint = True
        except Exception:
            use_inpaint = False

        if use_inpaint and inpainted_rgb is not None:
            try:
                base_img = Image.fromarray(inpainted_rgb).convert('RGBA')
                draw = ImageDraw.Draw(base_img)
            except Exception:
                base_img = original_rgba.copy()
                draw = ImageDraw.Draw(base_img)

        for item in line_items:
            src_text = item['text']
            # Translate per line to keep layout stable
            try:
                dst_text = _translate_preserve_form_leaders(src_text)
            except Exception:
                dst_text = src_text

            ocr_lines.append(src_text)
            translated_lines.append(dst_text)

            l = max(0, item['left'])
            t = max(0, item['top'])
            r = min(base_img.size[0], item['right'])
            b = min(base_img.size[1], item['bottom'])

            if return_blocks:
                try:
                    x0 = float(l) / float(w_img)
                    y0 = float(t) / float(h_img)
                    x1 = float(r) / float(w_img)
                    y1 = float(b) / float(h_img)
                except Exception:
                    x0 = y0 = 0.0
                    x1 = y1 = 0.0
                blocks.append({
                    'original_text': src_text,
                    'translated_text': dst_text,
                    'position': {
                        'bbox_norm': [x0, y0, x1, y1],
                        'bbox_px': [int(l), int(t), int(r), int(b)],
                    }
                })
            box_w = max(1, r - l)
            box_h = max(1, b - t)

            # 2) If OpenCV isn't available, fallback: softly cover region with sampled bg
            if not use_inpaint:
                pad = 6
                rect = (
                    max(0, l - pad),
                    max(0, t - pad),
                    min(base_img.size[0], r + pad),
                    min(base_img.size[1], b + pad),
                )
                bg = _sample_bg_color(base_img, l, t, r, b)
                draw.rectangle(rect, fill=(bg[0], bg[1], bg[2], 245))

            bg = _sample_bg_color(base_img, l, t, r, b)
            fill, stroke = _pick_text_colors(bg)

            # 3) Fit + wrap translated text to the detected box
            font, lines_wrapped, total_h = _fit_font_wrapped(draw, dst_text, max_w=box_w, max_h=box_h)
            line_gap = int(max(1, font.size * 0.18))
            y = t + max(0, int((box_h - total_h) / 2))
            for ln in lines_wrapped:
                try:
                    draw.text((l, y), ln, fill=fill, font=font, stroke_width=2, stroke_fill=stroke)
                except TypeError:
                    draw.text((l, y), ln, fill=fill, font=font)
                y += _measure(draw, font, ln)[1] + line_gap

        out = base_img.convert('RGB')
        import io
        buf = io.BytesIO()
        out.save(buf, format='PNG')
        png_bytes = buf.getvalue()
        ocr_full_text = "\n".join(ocr_lines).strip()
        non_empty_lines = [ln for ln in ocr_full_text.splitlines() if (ln or '').strip()]
        char_count = len(ocr_full_text)
        # Heuristic mode recommendation for Tesseract path (no AI classifier here)
        # NOTE: auto should prefer a single mode per image (text or image),
        # not "both" on the same image.
        try:
            img_area = max(1, base_img.size[0] * base_img.size[1])
            text_area = 0
            for item in line_items:
                text_area += max(1, (int(item['right']) - int(item['left'])) * (int(item['bottom']) - int(item['top'])))
            coverage = min(1.0, float(text_area) / float(img_area))
        except Exception:
            coverage = 0.0

        words_per_line = []
        for ln in non_empty_lines:
            try:
                words_per_line.append(len(re.findall(r'\w+', ln, flags=re.UNICODE)))
            except Exception:
                words_per_line.append(len((ln or '').split()))
        avg_words_per_line = (sum(words_per_line) / len(words_per_line)) if words_per_line else 0.0

        if not ocr_full_text:
            recommended_mode = 'text'
        elif coverage >= 0.42 and (char_count >= 120 or avg_words_per_line >= 5.0):
            recommended_mode = 'text'
        elif coverage <= 0.28:
            recommended_mode = 'image'
        else:
            # Ambiguous/mixed image blocks (photo + text) -> keep visual design
            recommended_mode = 'image'

        # Classify image type for downstream JSON/UI.
        # A: mostly text blocks, return text
        # B: poster/banner-ish, preserve layout
        # C: table/form-ish, preserve layout
        image_type = 'B'
        try:
            if recommended_mode == 'text':
                image_type = 'A'
            else:
                form_score = 0
                for ln in non_empty_lines:
                    s = (ln or '').strip()
                    if not s:
                        continue
                    if leader_re.search(s):
                        form_score += 2
                    if re.search(r"_{3,}", s):
                        form_score += 2
                    if re.search(r"\b(name|date|address|phone|email|dob|id)\b", s, flags=re.IGNORECASE):
                        form_score += 1
                    if re.search(r"\b(h\u1ecd t\u00ean|ng\u00e0y|\u0111\u1ecba ch\u1ec9|s\u1ed1 \u0111i\u1ec7n tho\u1ea1i|email|cmnd|cccd)\b", s, flags=re.IGNORECASE):
                        form_score += 1
                if form_score >= 5 and len(non_empty_lines) >= 4:
                    image_type = 'C'
                else:
                    image_type = 'B'
        except Exception:
            image_type = 'B'

        if return_blocks:
            return (ocr_full_text, "\n".join(translated_lines).strip(), png_bytes, recommended_mode, blocks, image_type)
        return (ocr_full_text, "\n".join(translated_lines).strip(), png_bytes, recommended_mode)

    def _ai_vision_overlay_fallback(self, image_path, source_lang, target_lang):
        """Fallback OCR+translate+overlay using AI Vision (no Tesseract).

        Since we don't have bounding boxes, we render translated text as a
        clean semi-transparent banner overlay at the bottom of the original image.
        Returns: (ocr_text, translated_text, png_bytes, recommended_mode)
        """
        from PIL import Image, ImageDraw, ImageFont
        import io as _io

        # Do OCR + translate + classify in one AI call
        ocr_text, translated_text, recommended_mode = self._ai_vision_ocr_and_translate(image_path, target_lang)

        if not ocr_text and not translated_text:
            with open(image_path, 'rb') as f:
                raw = f.read()
            return ("", "", raw, recommended_mode)

        # Load original image and keep same dimensions
        img = Image.open(image_path).convert('RGBA')
        w, h = img.size

        # ── Font selection (supports Vietnamese/CJK) ──
        def _pick_font(size):
            # Bundled NotoSans first, then system fallbacks
            candidates = []
            noto_bold = _get_noto_font(is_bold=True)
            if noto_bold:
                candidates.append(noto_bold)
            noto_reg = _get_noto_font()
            if noto_reg:
                candidates.append(noto_reg)
            if os.name == 'nt':
                candidates.extend([
                    r"C:\Windows\Fonts\arialbd.ttf",
                    r"C:\Windows\Fonts\arial.ttf",
                ])
            candidates.extend([
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ])
            for p in candidates:
                try:
                    if p and os.path.exists(p):
                        return ImageFont.truetype(p, size)
                except Exception:
                    continue
            try:
                return ImageFont.load_default()
            except Exception:
                return ImageFont.load_default()

        # ── Adaptive font size based on image dimensions ──
        # Larger images get larger fonts; minimum 14px, maximum 28px
        font_size = max(14, min(28, int(min(w, h) / 18)))
        font = _pick_font(font_size)
        padding_x = max(12, int(w * 0.03))
        padding_y = max(8, int(h * 0.015))
        max_text_w = w - 2 * padding_x

        # ── Text wrapping ──
        overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        def _measure_text(txt, fnt):
            try:
                bx = draw.textbbox((0, 0), txt, font=fnt)
                return bx[2] - bx[0], bx[3] - bx[1]
            except Exception:
                return int(len(txt) * font_size * 0.55), font_size

        def _wrap_text(text, fnt, max_w):
            """Word-wrap with fallback to character-level wrap for long words."""
            result_lines = []
            for paragraph in (text or '').split('\n'):
                if not paragraph.strip():
                    result_lines.append('')
                    continue
                words = paragraph.split()
                if not words:
                    result_lines.append('')
                    continue
                cur = ''
                for wd in words:
                    test = (cur + ' ' + wd).strip() if cur else wd
                    tw, _ = _measure_text(test, fnt)
                    if tw <= max_w:
                        cur = test
                    else:
                        if cur:
                            result_lines.append(cur)
                        # If a single word is wider than max, do char-level break
                        ww, _ = _measure_text(wd, fnt)
                        if ww > max_w:
                            temp = ''
                            for ch in wd:
                                cw, _ = _measure_text(temp + ch, fnt)
                                if cw > max_w and temp:
                                    result_lines.append(temp)
                                    temp = ch
                                else:
                                    temp += ch
                            cur = temp
                        else:
                            cur = wd
                if cur:
                    result_lines.append(cur)
            return result_lines if result_lines else ['']

        wrapped = _wrap_text(translated_text, font, max_text_w)
        line_h = int(font_size * 1.4)

        # ── Calculate banner height ──
        banner_h = len(wrapped) * line_h + 2 * padding_y
        max_banner = int(h * 0.50)  # max 50% of image
        if banner_h > max_banner:
            banner_h = max_banner
            # Truncate lines to fit
            max_lines = max(1, (banner_h - 2 * padding_y) // line_h)
            if len(wrapped) > max_lines:
                wrapped = wrapped[:max_lines - 1] + [wrapped[max_lines - 1] + '...']

        # ── Draw clean banner at bottom ──
        banner_top = h - banner_h
        # Gradient-like effect: two rectangles for depth
        draw.rectangle([(0, banner_top - 4), (w, banner_top)], fill=(0, 0, 0, 60))
        draw.rectangle([(0, banner_top), (w, h)], fill=(0, 0, 0, 190))

        # ── Draw text lines ──
        y = banner_top + padding_y
        for ln in wrapped:
            if y + line_h > h - 4:
                break
            # Subtle text shadow for readability
            try:
                draw.text((padding_x + 1, y + 1), ln, fill=(0, 0, 0, 150), font=font)
                draw.text((padding_x, y), ln, fill=(255, 255, 255, 245), font=font)
            except Exception:
                draw.text((padding_x, y), ln, fill=(255, 255, 255, 245))
            y += line_h

        # ── Composite ──
        result = Image.alpha_composite(img, overlay).convert('RGB')
        buf = _io.BytesIO()
        result.save(buf, format='PNG', quality=95)
        png_bytes = buf.getvalue()
        return (ocr_text.strip(), translated_text.strip(), png_bytes, recommended_mode)

    def _check_provider_available(self):
        """Lightweight preflight check to see if the configured AI provider is available.

        Returns (True, None) if OK, otherwise (False, message) if rate-limited or clearly unavailable.
        Only blocks on CLEAR rate-limit / payment errors. Other errors are allowed through
        since the actual translation call may still succeed.
        """
        if not self.openai_client:
            # Text translation no longer depends on AI provider.
            return (True, None)
        try:
            # Call models.list to surface rate-limit errors quickly
            _ = self.openai_client.models.list()
            return (True, None)
        except Exception as e:
            err = str(e).lower()
            if '429' in err or '402' in err or 'rate' in err or 'insufficient' in err or 'free-models' in err or 'credit' in err:
                # Rate-limited or insufficient credits — abort early so background job fails fast
                print(f"AI provider preflight check indicates rate limit/insufficient credits: {e}.")
                return (False, str(e))
            # Non-rate errors: DON'T block — models.list() can fail on some providers
            # but actual chat completions may still work fine.
            print(f"AI provider preflight warning (proceeding anyway): {e}")
            return (True, None)
    def translate_document_background(self, file_path, target_lang, user_id=None, *, ocr_images=False, ocr_langs=None, ocr_mode=None, bilingual_mode=None, bilingual_delimiter=None, translation_provider=None):
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            'status': 'pending',
            'progress': 0,
            'message': 'Queued',
            'download_path': None,
            'error': None,
            'user_id': user_id
        }
        # AI preflight is only advisory now (used for OCR/image paths).
        if ocr_images and self.openai_client:
            available, message = self._check_provider_available()
            if not available:
                self.jobs[job_id]['message'] = 'Starting (AI OCR may be limited)'
                self.jobs[job_id]['error'] = str(message)

        def _worker(job_id, file_path, target_lang, ocr_images, ocr_langs, ocr_mode, bilingual_mode, bilingual_delimiter, translation_provider):
            com_uninit = None
            try:
                try:
                    from deps_bootstrap import ensure_packages_on_path
                    ensure_packages_on_path()
                except Exception:
                    pass

                self.set_request_translation_provider(translation_provider)

                if os.name == 'nt':
                    try:
                        import pythoncom  # type: ignore
                        pythoncom.CoInitialize()
                        com_uninit = pythoncom.CoUninitialize
                    except Exception:
                        try:
                            import ctypes
                            _ole32 = ctypes.windll.ole32
                            _hr = int(_ole32.CoInitializeEx(None, 2))
                            if _hr in (0, 1):
                                com_uninit = _ole32.CoUninitialize
                        except Exception:
                            pass

                self.jobs[job_id]['status'] = 'in_progress'
                self.jobs[job_id]['progress'] = 5
                self.jobs[job_id]['message'] = 'Starting'

                ocr_done_message = None
                ocr_skip_message = None

                def progress_cb(percent, msg=''):
                    try:
                        p = float(percent)
                    except Exception:
                        p = 0.0

                    # Accept both progress scales:
                    # - 0..1 (fraction)
                    # - 0..100 (percent)
                    if 0.0 <= p <= 1.0:
                        p = p * 100.0

                    pct = max(0, min(100, int(p)))

                    try:
                        s_msg = str(msg or '')
                    except Exception:
                        s_msg = ''

                    # Avoid showing 100% while multi-page PDF render is still in progress.
                    m_page = re.search(r"PDF:\s*page\s*(\d+)\s*/\s*(\d+)", s_msg, flags=re.IGNORECASE)
                    if m_page:
                        cur = max(1, int(m_page.group(1)))
                        total = max(1, int(m_page.group(2)))
                        page_pct = 5 + int(((cur - 1) / total) * 85)
                        if cur < total:
                            pct = min(99, page_pct)

                    self.jobs[job_id]['progress'] = pct
                    self.jobs[job_id]['message'] = msg

                    nonlocal ocr_done_message, ocr_skip_message
                    try:
                        s = str(msg or '')
                    except Exception:
                        s = ''
                    if s.startswith('DOCX OCR'):
                        ocr_done_message = s
                    if s.startswith('Skipping DOCX image OCR'):
                        ocr_skip_message = s

                # Document translation is handled by FileService (DOCX/XLSX/TXT/PDF).
                output_path = self.file_service.process_document(
                    file_path,
                    target_lang,
                    progress_callback=progress_cb,
                    ocr_images=bool(ocr_images),
                    ocr_langs=ocr_langs,
                    ocr_mode=ocr_mode,
                    bilingual_mode=bilingual_mode,
                    bilingual_delimiter=bilingual_delimiter,
                    translation_provider=translation_provider,
                )

                # Validate and normalize output to utils/download so the /downloads route can serve it.
                if not output_path or not str(output_path).strip():
                    raise RuntimeError("Document pipeline returned empty output path")

                output_path = str(output_path)
                if not os.path.exists(output_path):
                    raise RuntimeError(f"Output file was not created: {output_path}")

                backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                downloads_dir = os.path.join(backend_dir, 'utils', 'download')
                os.makedirs(downloads_dir, exist_ok=True)

                # If the pipeline produced a file outside downloads, copy it in so downloading works.
                try:
                    out_abs = os.path.abspath(output_path)
                    dl_abs = os.path.abspath(downloads_dir)
                    in_downloads = os.path.commonpath([out_abs, dl_abs]) == dl_abs
                except Exception:
                    in_downloads = False

                if not in_downloads:
                    base_name = os.path.basename(output_path)
                    dest_path = os.path.join(downloads_dir, base_name)
                    if os.path.exists(dest_path):
                        root, ext = os.path.splitext(base_name)
                        dest_path = os.path.join(downloads_dir, f"{root}_{uuid.uuid4().hex[:8]}{ext}")
                    shutil.copy2(output_path, dest_path)
                    output_path = dest_path

                self.jobs[job_id]['download_path'] = output_path

                # Sidecar OCR text export is no longer generated (text inserted into DOCX directly).

                # Persist OCR summary for status endpoint / debugging
                if ocr_images:
                    if ocr_done_message:
                        self.jobs[job_id]['ocr_summary'] = ocr_done_message
                    if ocr_skip_message:
                        self.jobs[job_id]['ocr_skipped'] = ocr_skip_message

                # Detect fallback: if output extension != original extension -> it's a fallback
                try:
                    orig_ext = os.path.splitext(file_path)[1].lower()
                    out_ext = os.path.splitext(output_path)[1].lower()
                    if out_ext and orig_ext and out_ext != orig_ext:
                        self.jobs[job_id]['fallback'] = True
                        self.jobs[job_id]['fallback_reason'] = f"Output changed from {orig_ext} to {out_ext}"
                        # Keep OCR summary visible if available
                        if ocr_images and self.jobs[job_id].get('ocr_summary'):
                            self.jobs[job_id]['message'] = f"Completed with fallback — {self.jobs[job_id]['ocr_summary']}"
                        elif ocr_images and self.jobs[job_id].get('ocr_skipped'):
                            self.jobs[job_id]['message'] = f"Completed with fallback — {self.jobs[job_id]['ocr_skipped']}"
                        else:
                            self.jobs[job_id]['message'] = 'Completed with fallback'
                    else:
                        self.jobs[job_id]['fallback'] = False
                        if ocr_images and self.jobs[job_id].get('ocr_summary'):
                            self.jobs[job_id]['message'] = f"Completed — {self.jobs[job_id]['ocr_summary']}"
                        elif ocr_images and self.jobs[job_id].get('ocr_skipped'):
                            self.jobs[job_id]['message'] = f"Completed — {self.jobs[job_id]['ocr_skipped']}"
                        else:
                            self.jobs[job_id]['message'] = 'Completed'
                except Exception:
                    self.jobs[job_id]['fallback'] = False
                    if ocr_images and self.jobs[job_id].get('ocr_summary'):
                        self.jobs[job_id]['message'] = f"Completed — {self.jobs[job_id]['ocr_summary']}"
                    elif ocr_images and self.jobs[job_id].get('ocr_skipped'):
                        self.jobs[job_id]['message'] = f"Completed — {self.jobs[job_id]['ocr_skipped']}"
                    else:
                        self.jobs[job_id]['message'] = 'Completed'

                self.jobs[job_id]['progress'] = 100
                self.jobs[job_id]['status'] = 'completed'
            except (ProviderRateLimitError,) as e:
                self.jobs[job_id]['status'] = 'failed'
                self.jobs[job_id]['error'] = str(e)
                err_low = str(e).lower()
                if '402' in err_low or 'insufficient' in err_low or 'credit' in err_low:
                    self.jobs[job_id]['message'] = 'Failed - Insufficient credits'
                elif '429' in err_low or 'rate' in err_low or 'too many requests' in err_low:
                    self.jobs[job_id]['message'] = 'Failed - Rate limited'
                else:
                    self.jobs[job_id]['message'] = 'Failed - AI provider unavailable'
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[DOCUMENT TRANSLATION ERROR] job={job_id}: {e}")
                self.jobs[job_id]['status'] = 'failed'
                self.jobs[job_id]['error'] = str(e)
                self.jobs[job_id]['message'] = 'Failed'
            finally:
                self.clear_request_translation_provider()
                if com_uninit is not None:
                    try:
                        com_uninit()
                    except Exception:
                        pass

        thread = threading.Thread(
            target=_worker,
            args=(job_id, file_path, target_lang, ocr_images, ocr_langs, ocr_mode, bilingual_mode, bilingual_delimiter, translation_provider),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job(self, job_id):
        return self.jobs.get(job_id)