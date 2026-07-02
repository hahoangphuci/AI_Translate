"""Ensure CI/Azure runtime can import heavy document deps (pdf2docx, PyMuPDF, …)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def api_base_dir() -> str:
    return os.path.abspath(os.path.dirname(__file__))


def ensure_api_base_on_path() -> str:
    base = api_base_dir()
    if base not in sys.path:
        sys.path.insert(0, base)
    return base


def _candidate_packages_dirs() -> list[str]:
    seen: set[str] = set()
    dirs: list[str] = []

    def _add(path: str) -> None:
        path = os.path.abspath(path)
        if path in seen or not os.path.isdir(path):
            return
        seen.add(path)
        dirs.append(path)

    for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep):
        entry = entry.strip()
        if entry and os.path.basename(entry.rstrip("/\\")) == "python_packages":
            _add(entry)

    _add(os.path.join(repo_root(), "python_packages"))
    _add(os.path.join(repo_root(), ".python_packages"))
    return dirs


def resolve_packages_dir() -> str:
    """Primary python_packages directory (prefer PYTHONPATH / Azure wwwroot)."""
    dirs = _candidate_packages_dirs()
    return dirs[0] if dirs else os.path.join(repo_root(), "python_packages")


def packages_dir() -> str:
    return resolve_packages_dir()


def ensure_packages_on_path() -> str:
    ensure_api_base_on_path()
    primary = resolve_packages_dir()
    for pkg in reversed(_candidate_packages_dirs()):
        if pkg not in sys.path:
            sys.path.insert(0, pkg)
    return primary


def check_pdf2docx_converter() -> dict:
    """Probe pdf2docx with a real import (find_spec alone is not enough on Azure)."""
    ensure_packages_on_path()
    status: dict = {
        "spec": importlib.util.find_spec("pdf2docx") is not None,
        "fitz_ok": False,
        "docx_ok": False,
        "import_ok": False,
        "error": None,
        "fitz_error": None,
        "docx_error": None,
        "fitz_version": None,
        "pythonpath": os.environ.get("PYTHONPATH"),
        "packages_dirs": _candidate_packages_dirs(),
        "sys_path_head": sys.path[:8],
    }
    try:
        import fitz

        status["fitz_ok"] = True
        status["fitz_version"] = getattr(fitz, "VersionBind", None)
    except Exception as exc:
        status["fitz_error"] = f"{type(exc).__name__}: {exc}"

    try:
        import docx  # noqa: F401

        status["docx_ok"] = True
    except Exception as exc:
        status["docx_error"] = f"{type(exc).__name__}: {exc}"

    try:
        from pdf2docx import Converter  # noqa: F401

        status["import_ok"] = True
    except Exception as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"

    return status


def has_pdf2docx() -> bool:
    return check_pdf2docx_converter()["import_ok"]


def bootstrap_runtime_dependencies(*, install_if_missing: bool = True) -> dict:
    """Load python_packages from deploy artifact; pip-install on Azure if still missing."""
    root = repo_root()
    pkg = ensure_packages_on_path()
    probe = check_pdf2docx_converter()

    status = {
        "packages_dir": pkg,
        "packages_dir_exists": os.path.isdir(pkg),
        "pdf2docx": probe["import_ok"],
        "pdf2docx_spec": probe["spec"],
        "converter_import_ok": probe["import_ok"],
        "converter_error": probe.get("error"),
        "fitz_ok": probe.get("fitz_ok"),
        "fitz_error": probe.get("fitz_error"),
        "fitz_version": probe.get("fitz_version"),
        "installed_now": False,
    }

    if status["pdf2docx"] or not install_if_missing:
        return status

    on_azure = bool(os.getenv("WEBSITE_SITE_NAME") or os.getenv("WEBSITES_PORT"))
    if not on_azure:
        return status

    req = os.path.join(root, "api_base", "requirements.txt")
    if not os.path.isfile(req):
        req = os.path.join(root, "requirements.txt")
    if not os.path.isfile(req):
        status["install_error"] = "requirements.txt not found"
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
        probe = check_pdf2docx_converter()
        status["pdf2docx"] = probe["import_ok"]
        status["converter_import_ok"] = probe["import_ok"]
        status["converter_error"] = probe.get("error")
        status["fitz_ok"] = probe.get("fitz_ok")
        status["fitz_error"] = probe.get("fitz_error")
        status["fitz_version"] = probe.get("fitz_version")
    except Exception as exc:
        status["install_error"] = str(exc)

    return status
