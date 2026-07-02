"""Ensure CI/Azure runtime can import heavy document deps (pdf2docx, PyMuPDF, …)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def packages_dir() -> str:
    return os.path.join(repo_root(), "python_packages")


def ensure_packages_on_path() -> str:
    pkg = packages_dir()
    if os.path.isdir(pkg) and pkg not in sys.path:
        sys.path.insert(0, pkg)
    return pkg


def has_pdf2docx() -> bool:
    ensure_packages_on_path()
    return importlib.util.find_spec("pdf2docx") is not None


def bootstrap_runtime_dependencies(*, install_if_missing: bool = True) -> dict:
    """Load python_packages from deploy artifact; pip-install on Azure if still missing."""
    root = repo_root()
    pkg = ensure_packages_on_path()
    legacy = os.path.join(root, ".python_packages")
    if os.path.isdir(legacy) and legacy not in sys.path:
        sys.path.insert(0, legacy)

    status = {
        "packages_dir": pkg,
        "packages_dir_exists": os.path.isdir(pkg),
        "pdf2docx": has_pdf2docx(),
        "installed_now": False,
    }

    if status["pdf2docx"] or not install_if_missing:
        return status

    on_azure = bool(os.getenv("WEBSITE_SITE_NAME") or os.getenv("WEBSITES_PORT"))
    if not on_azure:
        return status

    req = os.path.join(root, "requirements.txt")
    if not os.path.isfile(req):
        return status

    os.makedirs(pkg, exist_ok=True)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            timeout=180,
        )
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                pkg,
                "-r",
                req,
            ],
            timeout=900,
        )
        status["installed_now"] = True
        ensure_packages_on_path()
        status["pdf2docx"] = has_pdf2docx()
    except Exception as exc:
        status["install_error"] = str(exc)

    return status
