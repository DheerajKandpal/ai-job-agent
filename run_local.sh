#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${PROJECT_ROOT}/.venv"

if [[ ! -d "${VENV_PATH}" ]]; then
  echo "Missing virtual environment at ${VENV_PATH}. Run ./setup.sh first."
  exit 1
fi

if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
  echo "Missing .env at ${PROJECT_ROOT}/.env. Run ./setup.sh first."
  exit 1
fi

# shellcheck source=/dev/null
source "${VENV_PATH}/bin/activate"
set -a
# shellcheck source=/dev/null
source "${PROJECT_ROOT}/.env"
set +a

BACKEND_PORT="${PORT:-8000}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

cleanup() {
  echo
  echo "Stopping local services..."
  jobs -pr | xargs -r kill
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI on :${BACKEND_PORT}"
gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${BACKEND_PORT}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --access-logfile - \
  --error-logfile - &
BACKEND_PID=$!

echo "Starting Streamlit on :${STREAMLIT_PORT}"
streamlit run "${PROJECT_ROOT}/streamlit_app.py" \
  --server.address 0.0.0.0 \
  --server.port "${STREAMLIT_PORT}" \
  --server.headless true &
STREAMLIT_PID=$!

echo "FastAPI PID: ${BACKEND_PID}"
echo "Streamlit PID: ${STREAMLIT_PID}"
echo "Backend URL: http://127.0.0.1:${BACKEND_PORT}"
echo "Streamlit URL: http://127.0.0.1:${STREAMLIT_PORT}"
echo "Press Ctrl+C to stop both services."

wait -n "${BACKEND_PID}" "${STREAMLIT_PID}"
exit 1
