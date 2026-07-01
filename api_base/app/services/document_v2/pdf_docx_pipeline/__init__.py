"""PDF -> DOCX translation pipeline (analyze -> convert -> translate -> export)."""

from .pipeline import run_pdf_docx_pipeline

__all__ = ["run_pdf_docx_pipeline"]
