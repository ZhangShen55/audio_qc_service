#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-${IMAGE_TAG:-jy-algorithm-app-audio-qc:v1.0.0}}"
CONTAINER_NAME="${CONTAINER_NAME:-audio-qc-obfuscated}"
PORT="${PORT:-8090}"
GPU="${GPU:-0}"

docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

args=(run -d --name "${CONTAINER_NAME}" -p "${PORT}:8090")
if [[ "${GPU}" == "1" ]]; then
  args+=(--gpus all)
fi
args+=("${IMAGE_TAG}")

docker "${args[@]}"
echo "容器 ${CONTAINER_NAME} 已从镜像 ${IMAGE_TAG} 启动，访问地址：http://127.0.0.1:${PORT}"
