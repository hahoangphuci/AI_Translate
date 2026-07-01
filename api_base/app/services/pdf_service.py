"""PDF translation via DOCX pipeline (analyze → PDF->DOCX → translate → DOCX->PDF)."""

from __future__ import annotations

from typing import Any, Callable, Optional


def process_pdf(
    service: Any,
    file_path: str,
    target_lang: str,
    progress_callback: Optional[Callable[..., None]] = None,
    *,
    ocr_images: Optional[bool] = False,
    ocr_langs: Optional[str] = None,
    ocr_mode: Optional[str] = None,
    bilingual_mode: Optional[str] = None,
    bilingual_delimiter: Optional[str] = None,
) -> str:
    from .document_v2.pdf_docx_pipeline.pipeline import run_pdf_docx_pipeline

    return run_pdf_docx_pipeline(
        service,
        file_path,
        target_lang,
        progress_callback,
        ocr_images=ocr_images,
        ocr_langs=ocr_langs,
        ocr_mode=ocr_mode,
        bilingual_mode=bilingual_mode,
        bilingual_delimiter=bilingual_delimiter,
    )
