#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-jy-algorithm-app-audio-qc:v1.0.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_NAME="${CONTAINER_NAME:-audio-qc-obfuscated-verify}"
PORT="${PORT:-18090}"
BASE_URL="http://127.0.0.1:${PORT}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

CONTAINER_NAME="${CONTAINER_NAME}" PORT="${PORT}" "${ROOT_DIR}/docker/run.sh" "${IMAGE_TAG}" >/dev/null

for _ in $(seq 1 90); do
  if curl -fsS "${BASE_URL}/audio/health" >/dev/null 2>&1; then
    break
  fi
  if ! docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
    echo "container exited before health check succeeded" >&2
    docker logs "${CONTAINER_NAME}" >&2 || true
    exit 1
  fi
  sleep 2
done

curl -fsS "${BASE_URL}/audio/health" >/dev/null

TEST_WAV="${TMP_DIR}/qc_verify.wav"
python3 - "${TEST_WAV}" <<'PY'
from __future__ import annotations

import math
import struct
import sys
import wave

path = sys.argv[1]
sample_rate = 16000
duration_seconds = 12
frequency = 440.0
amplitude = 0.2
with wave.open(path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    for i in range(sample_rate * duration_seconds):
        value = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
        wf.writeframes(struct.pack("<h", value))
PY

QC_RESPONSE="${TMP_DIR}/qc_response.json"
curl -fsS -X POST "${BASE_URL}/audio/qc" -F "audio_file=@${TEST_WAV}" > "${QC_RESPONSE}"
python3 - "${QC_RESPONSE}" <<'PY'
from __future__ import annotations

import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
if payload.get("status_code") != 200:
    raise SystemExit(f"audio QC status_code was not 200: {payload}")
data = payload.get("data")
if not isinstance(data, dict) or "vad" not in data:
    raise SystemExit(f"audio QC payload missing data.vad: {payload}")
PY

docker exec "${CONTAINER_NAME}" python - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

app_root = Path("/srv/app/app")
manifest = json.loads(Path("/srv/app/obfuscation-manifest.json").read_text(encoding="utf-8"))
bad = []
for rel in manifest.get("protected_modules", []):
    candidate = app_root / rel
    if candidate.exists() and not candidate.read_text(encoding="utf-8").startswith("# generated compatibility wrapper"):
        bad.append(rel)
if bad:
    raise SystemExit("protected original source files found: " + ", ".join(bad))
PY

echo "Verified ${IMAGE_TAG}"
