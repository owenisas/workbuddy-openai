# How to use

**Last updated: 2026-08-28**

Login locally, then call `https://www.workbuddy.ai/v2` as an OpenAI-compatible base URL. No localhost server required.

Clone: https://github.com/owenisas/workbuddy-openai

```bash
git clone https://github.com/owenisas/workbuddy-openai.git
cd workbuddy-openai
python3 -m workbuddy_openai login
python3 -m workbuddy_openai snippet hermes
```

| Client field | Value |
|---|---|
| Base URL | `https://www.workbuddy.ai/v2` |
| API key | `WORKBUDDY_ACCESS_TOKEN` from `~/.workbuddy-openai/env` |
| Chat | `POST /chat/completions` with `stream: true` |
| Models | `python3 -m workbuddy_openai models` |

Put the token in the harness env. Do not paste it into git.

---

## Hermes Agent

1. `python3 -m workbuddy_openai login`
2. Copy `WORKBUDDY_ACCESS_TOKEN` from `~/.workbuddy-openai/env` into the **active profile** `.env`.
3. Add the `providers.workbuddy` block from `python3 -m workbuddy_openai snippet hermes` (or `examples/hermes-provider.yaml`). Leave `model.default` alone unless you want this as the session default.
4. New Hermes session → `/model workbuddy/default-model`

Profile note: `pa` reads `~/.hermes/profiles/pa/config.yaml` + that profile’s `.env`, not the global files.

## OpenCode

Merge `examples/opencode.json` (or `python3 -m workbuddy_openai snippet opencode`). Set the API key from `WORKBUDDY_ACCESS_TOKEN`. Select `workbuddy/default-model`.

## Cursor / any OpenAI-compatible harness

- Base URL: `https://www.workbuddy.ai/v2`
- Key: contents of `WORKBUDDY_ACCESS_TOKEN`
- Model: `default-model`

If the UI appends `/v1` itself and you get `/v2/v1/...` 404s, use `https://www.workbuddy.ai` as the host and `/v2` as the path prefix, or the full `/v2` base if the UI does not append `/v1`.

Clients must **stream**. A non-stream `chat/completions` request is rejected by WorkBuddy.

## curl

```bash
set -a
# shellcheck source=/dev/null
. "$HOME/.workbuddy-openai/env"
set +a

curl -sS -N https://www.workbuddy.ai/v2/chat/completions \
  -H "Authorization: Bearer $WORKBUDDY_ACCESS_TOKEN" \
  -H 'content-type: application/json' \
  -d '{"model":"default-model","stream":true,"messages":[{"role":"system","content":"You are a helpful assistant."},{"role":"user","content":"Say hi in one word."}]}'
```

`examples/curl.sh` does the same.

## CLI

| command | what |
|---|---|
| `login` | Browser OAuth from zero |
| `login --no-browser` | Print URL only |
| `login --import-desktop` | Copy WorkBuddy desktop session |
| `status` | uid/nickname/expiry (no tokens) |
| `refresh` | Refresh the access token |
| `models` | Live catalog |
| `snippet hermes\|opencode\|env` | Config text, no token values |
| `logout` | Delete session + env file |
| `serve` | Optional localhost shim |

Env: `WORKBUDDY_OPENAI_HOME`, `WORKBUDDY_ACCESS_TOKEN`, `WORKBUDDY_BASE_URL`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `not logged in` | `python3 -m workbuddy_openai login` |
| Browser never finishes | Copy the printed URL. Polling lasts 5 minutes. |
| `Non-stream chat request is currently not supported` | Send `stream: true` |
| `first message is not system prompt` | First message `role` must be `system` |
| `401 invalid_token` on `copilot.tencent.com` | Use `www.workbuddy.ai` (overseas). |
| Empty completion + `finish=length` | Raise `max_tokens` (thinking counts). |
| 401 after a long time | `python3 -m workbuddy_openai refresh` |

`serve` is optional. Prefer `https://www.workbuddy.ai/v2`.
