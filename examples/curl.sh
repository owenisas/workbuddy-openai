#!/usr/bin/env bash
# Direct WorkBuddy API. Requires: python3 -m workbuddy_openai login
set -euo pipefail
ENV_FILE="${WORKBUDDY_OPENAI_HOME:-$HOME/.workbuddy-openai}/env"
# shellcheck source=/dev/null
set -a
. "$ENV_FILE"
set +a
BASE="${WORKBUDDY_BASE_URL:-https://www.workbuddy.ai/v2}"

curl -sS -N "$BASE/chat/completions" \
  -H "Authorization: Bearer $WORKBUDDY_ACCESS_TOKEN" \
  -H 'content-type: application/json' \
  -d '{"model":"default-model","stream":true,"messages":[{"role":"system","content":"You are a helpful assistant."},{"role":"user","content":"Say hi in one word."}]}'
