#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${PROJECT_ROOT}/.venv"

echo "==> Project root: ${PROJECT_ROOT}"

if [[ ! -d "${VENV_PATH}" ]]; then
  echo "==> Creating virtual environment at .venv"
  python3 -m venv "${VENV_PATH}"
else
  echo "==> Using existing virtual environment at .venv"
fi

echo "==> Activating virtual environment"
# shellcheck source=/dev/null
source "${VENV_PATH}/bin/activate"

echo "==> Installing dependencies"
python -m pip install --upgrade pip
pip install -r "${PROJECT_ROOT}/requirements.txt"
pip install streamlit

if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
  echo "==> Creating .env from .env.example"
  cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
  chmod 600 "${PROJECT_ROOT}/.env"
  echo "==> Created .env — edit it with real values before running."
else
  echo "==> .env already exists, leaving it unchanged"
fi

if [[ ! -f "${PROJECT_ROOT}/.env.streamlit" ]]; then
  echo "==> Creating .env.streamlit from .env.streamlit.example"
  cp "${PROJECT_ROOT}/.env.streamlit.example" "${PROJECT_ROOT}/.env.streamlit"
  chmod 600 "${PROJECT_ROOT}/.env.streamlit"
  echo "==> Created .env.streamlit — edit it with real values before running."
else
  echo "==> .env.streamlit already exists, leaving it unchanged"
fi

echo
echo "Setup complete."
echo "Next steps:"
echo "  1) Edit .env with real values:"
echo "     ${PROJECT_ROOT}/.env"
echo "  2) Edit .env.streamlit with real values:"
echo "     ${PROJECT_ROOT}/.env.streamlit"
echo "  3) Run the full local stack:"
echo "     ./run_local.sh"
