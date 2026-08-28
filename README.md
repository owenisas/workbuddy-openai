# workbuddy-openai-gateway

**Last updated: 2026-08-28**

Unofficial local gateway: **your** WorkBuddy / Tencent account → OpenAI-compatible `/v1/chat/completions` for Hermes, OpenCode, Cursor, Codex, or curl.

No pip packages required. Python 3.10+.

This is not a Tencent product. It talks to the same SaaS the official WorkBuddy desktop app uses (`www.workbuddy.ai`) with a session you create by logging in.

## Clone and run

```bash
git clone <this-repo> workbuddy-openai-gateway
cd workbuddy-openai-gateway

# 1. Sign in (opens a browser; use your WorkBuddy / Tencent account)
python3 -m workbuddy_openai login

# already have the WorkBuddy desktop app logged in on this Mac?
python3 -m workbuddy_openai login --import-desktop

# 2. Serve
python3 -m workbuddy_openai serve
# OpenAI-compatible gateway on http://127.0.0.1:8787/v1
```

Session file (mode `0600`): `~/.workbuddy-openai/session.json`. Tokens never go to stdout.

```bash
python3 -m workbuddy_openai status    # uid / nickname / expiry only
python3 -m workbuddy_openai models    # live catalog from /v3/config
python3 -m workbuddy_openai logout
```

## Point an agent at it

Base URL: `http://127.0.0.1:8787/v1`  
API key: any string (or set `WORKBUDDY_GATEWAY_KEY` / `--api-key` to require one)

### Hermes

Do **not** change your default model unless you want to. Add a provider:

```yaml
providers:
  workbuddy:
    name: WorkBuddy
    base_url: http://127.0.0.1:8787/v1
    api_key: workbuddy-local
    api: openai-completions
    models:
      - hy4-preview
      - hy3
      - gpt-5.6-luna
      - fast-model
      - balanced-model
      - primary-model
      - deep-model
```

Then `/model workbuddy/hy4-preview`. Copy `examples/hermes-provider.yaml`.

Keep `python3 -m workbuddy_openai serve` running. Hermes talks to localhost only.

### OpenCode

See `examples/opencode.json`. Custom provider `workbuddy` at `http://127.0.0.1:8787/v1`.

### curl

```bash
curl -s http://127.0.0.1:8787/v1/models | python3 -m json.tool

curl -s http://127.0.0.1:8787/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"hy4-preview","messages":[{"role":"user","content":"Say hi in one word."}]}'
```

The gateway accepts both `stream: true` (SSE) and `stream: false` (JSON). Upstream WorkBuddy is stream-only; non-stream is buffered here.

## What login does

WorkBuddy’s official flow (`cli-external-link`):

1. `POST /v2/plugin/auth/state?platform=workbuddy-ai` → `{state, authUrl}`
2. Open `https://www.workbuddy.ai/login?platform=workbuddy-ai&state=…`
3. Poll `GET /v2/plugin/auth/token?state=…` every 1s (`code 11217` = still waiting, 5 min timeout)
4. `GET /v2/plugin/login/account?state=…`
5. Save session. Refresh later with `POST /v2/plugin/auth/token/refresh` + `X-Refresh-Token`

Chat hop:

```
POST https://www.workbuddy.ai/v2/chat/completions
Authorization: Bearer <jwt>
X-User-Id: <uid>
X-Domain: www.workbuddy.ai
```

Constraints the gateway hides:

| Upstream | Gateway |
|---|---|
| First message must be `system` (`11128`) | Injects a default system message |
| `stream: false` rejected (`11101`) | Buffers SSE into a JSON completion |
| Reasoning models count thinking toward `max_tokens` | Default `max_tokens=8192` if the client omitted it |
| Model ids like `hy4-preview`, `fast-model` | Aliases: `hy4`, `fast`, `balanced`, `primary`, `ultimate`→`deep-model` |

Hy4 preview (when Tencent marks it free) bills `usage.credit = 0`. Paid rows still consume your WorkBuddy credit pack.

## Layout

```
workbuddy_openai/     stdlib package
  auth.py             OAuth from zero + desktop import + refresh
  session.py          ~/.workbuddy-openai/session.json
  upstream.py         /v3/config + /v2/chat/completions
  server.py           /v1/models + /v1/chat/completions (HTTP/1.0)
  cli.py
examples/             Hermes + OpenCode snippets
tests/
```

```bash
python3 -m unittest tests.test_upstream
```

## Env

| var | meaning |
|---|---|
| `WORKBUDDY_OPENAI_HOME` | Override config dir (default `~/.workbuddy-openai`) |
| `WORKBUDDY_GATEWAY_KEY` | Optional Bearer the gateway requires from clients |

Bind is `127.0.0.1` on purpose. Do not expose this port to the internet; it is your account.

## Not included

- Creating a Tencent account, accepting ToS, or spending credits for you
- China-site `copilot.tencent.com` login (this tree is the overseas `www.workbuddy.ai` brand; a CN JWT 401s there)
- Shipping Tencent’s Electron app
