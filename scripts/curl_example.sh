#!/usr/bin/env bash
set -e

URL=${1:-http://127.0.0.1:8000/v1/audio/qc}
FILE=${2:-test.mp3}

curl -s -X POST "$URL" \
  -F "file=@${FILE}" | jq .
