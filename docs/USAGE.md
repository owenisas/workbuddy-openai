# How to use

**Last updated: 2026-08-28**

Local OpenAI-compatible API in front of **your** WorkBuddy / Tencent login. Keep `python3 -m workbuddy_openai serve` running while any agent uses it.

Clone: https://github.com/owenisas/workbuddy-openai-gateway

```bash
git clone https://github.com/owenisas/workbuddy-openai-gateway.git
cd workbuddy-openai-gateway
python3 -m workbuddy_openai login          # browser OAuth from zero
# python3 -m workbuddy_openai login --import-desktop   # Mac, app already signed in
python3 -m workbuddy_openai serve          # http://127.0.0.1:8787/v1
```

| Client field | Value |
|---|---|
| Base URL | `http://127.0.0.1:8787/v1` |
| API key | `workbuddy-local` (anything; lock with `--api-key` if you want) |
| Chat | `POST /v1/chat/completions` |
| Models | `GET /v1/models` |

Free-when-promoted model id: `hy4-preview` (alias `hy4`). List live ids: `python3 -m workbuddy_openai models`.

---

## 1. Hermes Agent

1. Start the gateway.
2. Add the block in `examples/hermes-provider.yaml` under `providers:` in the **active profile** config. Do not change `model.default` unless you want WorkBuddy as the session default.
3. Restart Hermes (or open a new session) so the provider is picked up.
4. `/model workbuddy/hy4-preview`

Profile note: if you run the `pa` profile, keys/providers live in that profile’s `config.yaml`, not the global one.

## 2. OpenCode

Merge `examples/opencode.json` into `~/.config/opencode/opencode.json` (or the project `opencode.json`). `modalities.input: [text, image]` is required for vision; `attachment: true` alone is not enough.

Select model `workbuddy/hy4-preview`.

## 3. Cursor / any OpenAI-compatible harness

Provider type: OpenAI compatible.

- Base URL: `http://127.0.0.1:8787/v1`
- Key: `workbuddy-local`
- Model: `hy4-preview`

Some UIs want the base URL **without** `/v1` and append it themselves. If `/v1/v1/chat/completions` 404s, drop the trailing `/v1`.

## 4. curl / Python

```bash
curl -s http://127.0.0.1:8787/v1/models | python3 -m json.tool

curl -s http://127.0.0.1:8787/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"hy4-preview","messages":[{"role":"user","content":"Say hi in one word."}]}'
```

Streaming:

```bash
curl -N http://127.0.0.1:8787/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"hy4-preview","stream":true,"messages":[{"role":"user","content":"Say hi in one word."}]}'
```

Python (`openai` SDK optional):

```python
from openai import OpenAI
c = OpenAI(base_url="http://127.0.0.1:8787/v1", api_key="workbuddy-local")
print(c.chat.completions.create(
    model="hy4-preview",
    messages=[{"role": "user", "content": "Say hi in one word."}],
).choices[0].message.content)
```

Script: `examples/curl.sh`.

---

## CLI

| command | what |
|---|---|
| `python3 -m workbuddy_openai login` | Browser OAuth from zero |
| `python3 -m workbuddy_openai login --no-browser` | Print URL only |
| `python3 -m workbuddy_openai login --import-desktop` | Copy WorkBuddy desktop session |
| `python3 -m workbuddy_openai status` | Logged-in uid/nickname/expiry (no tokens) |
| `python3 -m workbuddy_openai models` | Live model catalog |
| `python3 -m workbuddy_openai serve [--port 8787] [--api-key …]` | Gateway |
| `python3 -m workbuddy_openai logout` | Delete `~/.workbuddy-openai/session.json` |

Env: `WORKBUDDY_OPENAI_HOME` (config dir), `WORKBUDDY_GATEWAY_KEY` (optional client Bearer).

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `not logged in` | Run `login` in the same machine/user. Session is `~/.workbuddy-openai/session.json`. |
| Browser never finishes | Copy the printed URL. Polling lasts 5 minutes (`11217` = still waiting). |
| `11128` / empty replies | Gateway should inject `system`; update if you forked an old copy. |
| Hy4 returns blank + `finish=length` | Thinking ate `max_tokens`. Raise it (gateway default is 8192). |
| `401 invalid_token` against `copilot.tencent.com` | Overseas account. This gateway uses `www.workbuddy.ai`. |
| Agent hangs after one SSE turn | Need HTTP/1.0 or `Connection: close` — this server already uses HTTP/1.0. |
| Credits drop on Fast/Primary | Those are paid rows. Hy4/Hy3 are `x0.00` only while Tencent’s promo says so. |
| Port in use | `python3 -m workbuddy_openai serve --port 8790` and change the client base URL. |

Bind is `127.0.0.1` on purpose. Do not expose the port; it is your account.
