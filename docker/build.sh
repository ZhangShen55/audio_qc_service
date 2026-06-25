#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-jy-algorithm-app-audio-qc}"
IMAGE_VERSION="${IMAGE_VERSION:-v1.0.0}"
FINAL_TAG="${IMAGE_NAME}:${IMAGE_VERSION}"
TEMP_TAG="${IMAGE_NAME}:build-${IMAGE_VERSION}-$(date +%Y%m%d%H%M%S)"
BUILD_DIR="${BUILD_DIR:-${ROOT_DIR}/docker/.build}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cpu}"
TORCH_VERSION="${TORCH_VERSION:-2.7.0+cpu}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-2.7.0}"
PYTHON_IMAGE="${PYTHON_IMAGE:-python:3.10-slim}"
PYARMOR_CONDA_ENV="${PYARMOR_CONDA_ENV:-audio_qc}"
PYARMOR_MODE="${PYARMOR_MODE:-basic}"
PYARMOR_ENABLE_RFT="${PYARMOR_ENABLE_RFT:-0}"
OBFUSCATION_SALT="${OBFUSCATION_SALT:-jy-audio-qc-v1.0.0}"

cleanup_on_error() {
  local status=$?
  if [[ "${status}" -ne 0 ]]; then
    "${ROOT_DIR}/docker/cleanup.sh" --tag "${TEMP_TAG}" --failed-only >/dev/null 2>&1 || true
    rm -rf "${BUILD_DIR}"
  fi
  exit "${status}"
}
trap cleanup_on_error EXIT

cd "${ROOT_DIR}"

docker build \
  -f docker/Dockerfile.obfuscated \
  --build-arg "PYTHON_IMAGE=${PYTHON_IMAGE}" \
  --build-arg "TORCH_INDEX_URL=${TORCH_INDEX_URL}" \
  --build-arg "TORCH_VERSION=${TORCH_VERSION}" \
  --build-arg "TORCHAUDIO_VERSION=${TORCHAUDIO_VERSION}" \
  --build-arg "PYARMOR_MODE=${PYARMOR_MODE}" \
  --build-arg "PYARMOR_ENABLE_RFT=${PYARMOR_ENABLE_RFT}" \
  --build-arg "OBFUSCATION_SALT=${OBFUSCATION_SALT}" \
  -t "${TEMP_TAG}" \
  "${ROOT_DIR}"

"${ROOT_DIR}/docker/verify.sh" "${TEMP_TAG}"

docker tag "${TEMP_TAG}" "${FINAL_TAG}"
docker image rm "${TEMP_TAG}" >/dev/null 2>&1 || true
"${ROOT_DIR}/docker/cleanup.sh" --keep-final
rm -rf "${BUILD_DIR}"

trap - EXIT
echo "Built and verified ${FINAL_TAG}"
