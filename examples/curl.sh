#!/usr/bin/env bash
# Requires: python3 -m workbuddy_openai serve
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8787/v1}"

echo "== models =="
curl -sS "$BASE/models"

echo
echo "== non-stream hy4 =="
curl -sS "$BASE/chat/completions" \
  -H 'content-type: application/json' \
  -d '{"model":"hy4-preview","messages":[{"role":"user","content":"Reply with the single word PONG."}]}'

echo
echo "== stream =="
curl -sS -N "$BASE/chat/completions" \
  -H 'content-type: application/json' \
  -d '{"model":"hy4-preview","stream":true,"messages":[{"role":"user","content":"Reply with the single word PONG."}]}'
