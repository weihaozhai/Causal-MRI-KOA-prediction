#!/bin/bash
set -e
cd "$(dirname "$0")"
OAI_RUNTIME="${OAI_PYTHON:-python3}"
if ! command -v "$OAI_RUNTIME" >/dev/null 2>&1; then
  echo "Python not found. Activate your Python environment or set OAI_PYTHON."
  exit 1
fi
if ! "$OAI_RUNTIME" -c 'import numpy, SimpleITK, PIL' >/dev/null 2>&1; then
  "$OAI_RUNTIME" -m pip install -r requirements.txt
fi
exec "$OAI_RUNTIME" -u app.py
