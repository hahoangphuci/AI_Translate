import hashlib
import hashlib
import os
import re
import unicodedata
import time
import random
import uuid
import io
import zipfile
import shutil
import docx
from collections import OrderedDict
from threading import Lock, local
from werkzeug.utils import secure_filename
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.shared import Inches, RGBColor

from .document_v2.fonts import get_font_dir as _bundled_get_font_dir, get_noto_sans_or_fallback


class ProviderRateLimitError(Exception):
    """Raised when the upstream AI provider indicates a hard rate limit (429 or insufficient credits)."""


class FileService:
    def __init__(self, translator=None, ocr_image_to_text=None, ocr_translate_overlay=None, ocr_image_to_bboxes=None):
        """translator: callable(text, source_lang, target_lang) -> translated_text

        ocr_image_to_text: optional callable(image_path, ocr_langs=None) -> text
        """
        from concurrent.futures import ThreadPoolExecutor

        self.upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'utils', 'upload_temp')
        self.download_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'utils', 'download')
        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs(self.download_folder, exist_ok=True)
        self.translator = translator
        self.ocr_image_to_text = ocr_image_to_text
        self.ocr_translate_overlay = ocr_translate_overlay
        self.ocr_image_to_bboxes = ocr_image_to_bboxes
        self.has_tesseract = False  # Will be set by TranslationService
        # Performance tuning
        try:
            from app import config as app_config
            self.concurrency = getattr(app_config.Config, 'TRANSLATION_CONCURRENCY', 4)
            self.retries = getattr(app_config.Config, 'TRANSLATION_RETRIES', 3)
            self.backoff = getattr(app_config.Config, 'TRANSLATION_BACKOFF', 1.5)
            self.rate_limit_wait_budget = getattr(app_config.Config, 'TRANSLATION_RATE_LIMIT_WAIT_MAX_SECONDS', 300)
        except Exception:
            self.concurrency = int(os.getenv('TRANSLATION_CONCURRENCY', '4'))
            self.retries = int(os.getenv('TRANSLATION_RETRIES', '3'))
            self.backoff = float(os.getenv('TRANSLATION_BACKOFF', '1.5'))
            self.rate_limit_wait_budget = int(os.getenv('TRANSLATION_RATE_LIMIT_WAIT_MAX_SECONDS', '300'))

        try:
            self.translation_cache_max_entries = max(0, int(os.getenv('TRANSLATION_CACHE_MAX_ENTRIES', '5000')))
        except Exception:
            self.translation_cache_max_entries = 5000
        try:
            self.translation_cache_max_chars = max(0, int(os.getenv('TRANSLATION_CACHE_MAX_CHARS', '6000')))
        except Exception:
            self.translation_cache_max_chars = 6000

        self._translation_cache = OrderedDict()
        self._translation_cache_lock = Lock()
        self._request_local = local()
        self._executor_cls = ThreadPoolExecutor

    def _set_translation_cache_scope(self, scope: str | None) -> None:
        scope = (str(scope or '').strip() or '-')
        self._request_local.translation_cache_scope = scope

    def _clear_translation_cache_scope(self) -> None:
        if hasattr(self._request_local, 'translation_cache_scope'):
            delattr(self._request_local, 'translation_cache_scope')

    def _make_translation_cache_key(self, text, target_lang, context=None):
        if text is None:
            return None
        src = str(text)
        if not src.strip():
            return None
        if self.translation_cache_max_chars > 0 and len(src) > self.translation_cache_max_chars:
            return None
        lang = (str(target_lang or '').strip().lower() or 'auto')
        ctx = (str(context or '').strip().lower() or '-')
        scope = '-'
        if ctx.startswith('document_'):
            scope = str(getattr(self._request_local, 'translation_cache_scope', '-') or '-')
        return (lang, ctx, scope, src)

    def _cache_get(self, key):
        if key is None or self.translation_cache_max_entries <= 0:
            return None
        with self._translation_cache_lock:
            value = self._translation_cache.get(key)
            if value is None:
                return None
            self._translation_cache.move_to_end(key)
            return value

    def _cache_set(self, key, value):
        if key is None or self.translation_cache_max_entries <= 0:
            return
        with self._translation_cache_lock:
            self._translation_cache[key] = value
            self._translation_cache.move_to_end(key)
            while len(self._translation_cache) > self.translation_cache_max_entries:
                self._translation_cache.popitem(last=False)

    @staticmethod
    def _retry_after_from_exception(exc):
        try:
            response = getattr(exc, 'response', None)
            if response is not None:
                raw = str(response.headers.get('Retry-After', '') or '').strip()
                if raw.isdigit():
                    return float(max(1, int(raw)))
        except Exception:
            pass

        try:
            msg = str(exc or '')
            m = re.search(r'retry[\s\-_]*after\s*[:=]?\s*(\d+)', msg, flags=re.IGNORECASE)
            if m:
                return float(max(1, int(m.group(1))))
        except Exception:
            pass
        return None

    @staticmethod
    def _status_code_from_exception(exc):
        try:
            response = getattr(exc, 'response', None)
            if response is not None and getattr(response, 'status_code', None) is not None:
                return int(response.status_code)
        except Exception:
            pass
        return None

    def _translate_with_retry(self, text, target_lang, *, context=None):
        """Translate a piece of text with retry/backoff on transient errors.

        IMPORTANT: If a provider rate-limit or "insufficient credits" error is encountered,
        fail fast by raising ProviderRateLimitError so the calling job can abort immediately
        instead of continuing and wasting quota/retries.
        """
        if not self.translator:
            raise RuntimeError('Translator not configured')

        cache_key = self._make_translation_cache_key(text, target_lang, context=context)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        last = None
        max_attempts = max(1, self.retries)
        accumulated_rate_limit_wait = 0.0
        for attempt in range(1, max_attempts + 1):
            try:
                try:
                    out = self.translator(text, 'auto', target_lang, context=context)
                except TypeError:
                    # Backward compatibility for translator callbacks that only accept 3 params.
                    out = self.translator(text, 'auto', target_lang)
                self._cache_set(cache_key, out)
                return out
            except Exception as e:
                last = e
                err = str(e).lower()
                status_code = self._status_code_from_exception(e)
                # Fail fast for provider rate limits or insufficient credits
                if status_code in (402, 429) or any(
                    k in err for k in ('429', 'too many requests', 'rate', 'insufficient', 'free-models', '402', 'credit', 'requires more credits')
                ):
                    try:
                        print(f"Provider rate limit or insufficient credits encountered: {e}")
                    except UnicodeEncodeError:
                        print("Provider rate limit encountered: ", repr(e))
                    raise ProviderRateLimitError(str(e))

                # Retry on transient network errors
                retryable = (
                    status_code in (408, 429, 500, 502, 503, 504)
                    or any(k in err for k in ('temporarily', 'timed out', 'timeout', 'connection', 'gateway', 'reset'))
                )
                if retryable and attempt < max_attempts:
                    retry_after = self._retry_after_from_exception(e)
                    if retry_after is not None:
                        sleep_time = retry_after
                    else:
                        sleep_time = min(30.0, float(self.backoff) * (2 ** max(0, attempt - 1)))
                        sleep_time += random.uniform(0.0, max(0.1, sleep_time * 0.25))

                    if status_code == 429:
                        accumulated_rate_limit_wait += sleep_time
                        if accumulated_rate_limit_wait > float(max(1, self.rate_limit_wait_budget)):
                            raise ProviderRateLimitError(
                                f"Rate limit wait exceeded budget ({self.rate_limit_wait_budget}s): {e}"
                            )

                    print(f"Translate retry {attempt}/{max_attempts} after {sleep_time:.2f}s due to: {e}")
                    time.sleep(sleep_time)
                    continue
                # Non-retryable errors: break
                break
        # Final attempt to raise helpful error
        raise last

    def _file_cache_scope_id(self, file_path: str) -> str:
        try:
            st = os.stat(file_path)
            with open(file_path, "rb") as fh:
                head = fh.read(65536)
            digest = hashlib.sha256(head).hexdigest()[:16]
            return f"{digest}-{st.st_size}-{int(st.st_mtime)}"
        except Exception:
            return os.path.basename(file_path)

    def process_document(self, file_path, target_lang, progress_callback=None, *, ocr_images=False, ocr_langs=None, ocr_mode=None, bilingual_mode=None, bilingual_delimiter=None, translation_provider=None):
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)

        mode_key = (str(bilingual_mode or 'none').strip().lower() or 'none')
        delimiter_key = self._normalize_bilingual_delimiter(bilingual_delimiter)
        provider_key = (str(translation_provider or '').strip().lower() or '-')
        file_key = self._file_cache_scope_id(file_path)
        self._set_translation_cache_scope(
            f"file={file_key};provider={provider_key};mode={mode_key};delimiter={delimiter_key};ext={ext.lower()}"
        )
        try:
            if ext.lower() == '.pdf':
                return self._process_pdf(
                    file_path,
                    target_lang,
                    progress_callback,
                    ocr_images=ocr_images,
                    ocr_langs=ocr_langs,
                    ocr_mode=ocr_mode,
                    bilingual_mode=bilingual_mode,
                    bilingual_delimiter=bilingual_delimiter,
                )
            elif ext.lower() == '.docx':
                return self._process_docx(file_path, target_lang, progress_callback, ocr_images=ocr_images, ocr_langs=ocr_langs, ocr_mode=ocr_mode, bilingual_mode=bilingual_mode, bilingual_delimiter=bilingual_delimiter)
            else:
                raise ValueError("Unsupported file type")
        finally:
            self._clear_translation_cache_scope()

    def _process_pdf(self, file_path, target_lang, progress_callback=None, *, ocr_images=False, ocr_langs=None, ocr_mode=None, bilingual_mode=None, bilingual_delimiter=None):
        from .pdf_service import process_pdf
        return process_pdf(
            self,
            file_path,
            target_lang,
            progress_callback,
            ocr_images=ocr_images,
            ocr_langs=ocr_langs,
            ocr_mode=ocr_mode,
            bilingual_mode=bilingual_mode,
            bilingual_delimiter=bilingual_delimiter,
        )

    @staticmethod
    def _normalize_bilingual_delimiter(delimiter):
        """Normalize a user-provided delimiter for inline bilingual output.

        Returns a short string (no surrounding spaces). Defaults to '|'.
        """
        d = (delimiter or '').strip()
        if not d:
            return '|'
        # Prevent pathological inputs from breaking layout.
        if len(d) > 10:
            d = d[:10]
        return d

    def _join_inline_bilingual(self, src, dst, delimiter):
        d = self._normalize_bilingual_delimiter(delimiter)
        s = (src or '').strip()
        t = (dst or '').strip()
        # If translation is empty, do not append a dangling delimiter.
        if not t:
            return src or ''
        if not s:
            return dst or ''
        while s.endswith(d):
            s = s[:-len(d)].rstrip()
        while t.startswith(d):
            t = t[len(d):].lstrip()
        return f"{src.rstrip()} {d} {t}"

    def _process_docx(self, file_path, target_lang, progress_callback=None, *, ocr_images=False, ocr_langs=None, ocr_mode=None, bilingual_mode=None, bilingual_delimiter=None, from_pdf=False):
        from .docx_service import process_docx
        return process_docx(
            self,
            file_path,
            target_lang,
            progress_callback,
            ocr_images=ocr_images,
            ocr_langs=ocr_langs,
            ocr_mode=ocr_mode,
            bilingual_mode=bilingual_mode,
            bilingual_delimiter=bilingual_delimiter,
            from_pdf=from_pdf,
        )

    def _sanitize_text(self, text: str) -> str:
        if not isinstance(text, str):
            try:
                text = str(text)
            except Exception:
                return ''
        # Normalize unicode and remove control characters that break XML/docx
        text = unicodedata.normalize('NFC', text)
        # Remove C0 control characters except tab/newline/carriage return
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
        # Collapse weird zero-width/formatting if any
        text = re.sub(r'[\u200B-\u200F\u2028\u2029]', ' ', text)
        return text

    def _translate_text(self, text, target_lang):
        # Use injected translator with retry/backoff
        if self.translator:
            out = self._translate_with_retry(text, target_lang)
            return self._sanitize_text(out)
        raise RuntimeError("Translator is not configured")
