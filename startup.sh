#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/site/wwwroot"
if [[ -d "$ROOT" ]]; then
  cd "$ROOT"
fi

# Azure Linux: DOCX -> PDF needs LibreOffice (docx2pdf requires Microsoft Word).
if [[ -n "${WEBSITE_SITE_NAME:-}" ]] && ! command -v soffice >/dev/null 2>&1; then
  echo "[startup] Installing LibreOffice headless for DOCX -> PDF export..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq || true
  apt-get install -y -qq --no-install-recommends \
    libreoffice-writer-nogui \
    libreoffice-core-nogui \
    fonts-dejavu-core \
    fonts-liberation \
    || echo "[startup] WARN: LibreOffice install failed — PDF export may fall back to DOCX"
fi

if command -v soffice >/dev/null 2>&1; then
  export LIBREOFFICE_PATH="$(command -v soffice)"
  echo "[startup] LibreOffice: ${LIBREOFFICE_PATH}"
fi

export PYTHONPATH="${ROOT}/python_packages:${PYTHONPATH:-}"
exec python api_base/run_api.py
