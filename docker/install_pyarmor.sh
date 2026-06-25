#!/usr/bin/env bash
set -euo pipefail

CONDA_ENV="${CONDA_ENV:-audio_qc}"
PYARMOR_PACKAGE="${PYARMOR_PACKAGE:-pyarmor}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda command not found. Install Miniconda/Anaconda or activate a shell with conda available." >&2
  exit 2
fi

if ! conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV}"; then
  echo "conda environment '${CONDA_ENV}' was not found." >&2
  exit 2
fi

conda run -n "${CONDA_ENV}" python -m pip install -U "${PYARMOR_PACKAGE}"

echo "PyArmor package installed in conda env '${CONDA_ENV}'."
echo "If you have a PyArmor Pro registration file, register it with:"
echo "  conda run -n ${CONDA_ENV} pyarmor reg /path/to/pyarmor-regfile.zip"
echo "Then verify with:"
echo "  conda run -n ${CONDA_ENV} pyarmor --version"
