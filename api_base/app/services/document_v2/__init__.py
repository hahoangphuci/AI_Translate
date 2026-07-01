"""Document helpers for layout-preserving translation.

- **PDF:** `pdf_docx_pipeline` (analyze -> PDF->DOCX -> translate -> DOCX->PDF).
- **DOCX:** handled by `docx_service` / `python-docx` (separate from this package).

Bundled **fonts** under this package supply Noto fallbacks for PDF rendering.
"""