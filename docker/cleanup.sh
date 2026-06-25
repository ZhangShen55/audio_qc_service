#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-jy-algorithm-app-audio-qc}"
IMAGE_VERSION="${IMAGE_VERSION:-v1.0.0}"
FINAL_TAG="${IMAGE_NAME}:${IMAGE_VERSION}"
EXTRA_TAG=""
KEEP_FINAL=0
FAILED_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      EXTRA_TAG="${2:?--tag 缺少参数值}"
      shift 2
      ;;
    --keep-final)
      KEEP_FINAL=1
      shift
      ;;
    --failed-only)
      FAILED_ONLY=1
      shift
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 2
      ;;
  esac
done

docker rm -f audio-qc-obfuscated audio-qc-obfuscated-verify >/dev/null 2>&1 || true

if [[ -n "${EXTRA_TAG}" ]]; then
  docker image rm "${EXTRA_TAG}" >/dev/null 2>&1 || true
fi

if [[ "${FAILED_ONLY}" == "1" ]]; then
  exit 0
fi

if [[ "${KEEP_FINAL}" == "1" ]]; then
  while read -r tag; do
    [[ -z "${tag}" ]] && continue
    [[ "${tag}" == "${FINAL_TAG}" ]] && continue
    [[ "${tag}" == "${IMAGE_NAME}:<none>" ]] && continue
    docker image rm "${tag}" >/dev/null 2>&1 || true
  done < <(docker images "${IMAGE_NAME}" --format '{{.Repository}}:{{.Tag}}')
fi
