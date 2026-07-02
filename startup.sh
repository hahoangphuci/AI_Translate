#!/usr/bin/env bash
# Azure App Service startup — keep minimal; never apt-install here.
set +e

ROOT="/home/site/wwwroot"
if [[ -d "$ROOT" ]]; then
  cd "$ROOT"
fi

export PYTHONPATH="${ROOT}/python_packages:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
PORT="${WEBSITES_PORT:-8000}"

echo "[startup] cwd=$(pwd)"
echo "[startup] python=$(command -v python || echo missing)"
echo "[startup] port=${PORT}"
echo "[startup] PYTHONPATH=${PYTHONPATH}"

if [[ ! -d "${ROOT}/python_packages" ]]; then
  echo "[startup] ERROR: python_packages missing at ${ROOT}/python_packages"
fi

if [[ ! -f "${ROOT}/api_base/run_api.py" ]]; then
  echo "[startup] ERROR: api_base/run_api.py not found"
  exit 1
fi

cd "${ROOT}/api_base" || exit 1

if PYTHONPATH="${ROOT}/python_packages:${PYTHONPATH:-}" python -c "import gunicorn" 2>/dev/null; then
  echo "[startup] launching gunicorn"
  exec env PYTHONPATH="${ROOT}/python_packages:${PYTHONPATH:-}" \
    gunicorn --bind "0.0.0.0:${PORT}" --workers 1 --threads 8 --timeout 600 run_api:app
fi

echo "[startup] gunicorn unavailable — launching flask dev server"
exec env PYTHONPATH="${ROOT}/python_packages:${PYTHONPATH:-}" python run_api.py
