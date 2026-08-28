# workbuddy-openai

**Last updated: 2026-08-28**

Log in with **your** WorkBuddy / Tencent account, then point Hermes, OpenCode, Cursor, or curl at Tencent’s own OpenAI URL:

```
https://www.workbuddy.ai/v2
```

Python 3.10+. No pip packages. Unofficial; not a Tencent product.

**Repo:** https://github.com/owenisas/workbuddy-openai-gateway  
**Harness recipes:** [docs/USAGE.md](docs/USAGE.md)

## Quick start

```bash
git clone https://github.com/owenisas/workbuddy-openai-gateway.git
cd workbuddy-openai-gateway

python3 -m workbuddy_openai login                 # browser OAuth
# python3 -m workbuddy_openai login --import-desktop   # Mac, desktop app already signed in

python3 -m workbuddy_openai snippet hermes        # paste into Hermes config
python3 -m workbuddy_openai models                # live ids
```

Login writes (mode `0600`, never printed):

- `~/.workbuddy-openai/session.json`
- `~/.workbuddy-openai/env` — `WORKBUDDY_ACCESS_TOKEN` and `WORKBUDDY_BASE_URL`

Copy `WORKBUDDY_ACCESS_TOKEN` into the Hermes/OpenCode env. Then:

| | |
|---|---|
| Base URL | `https://www.workbuddy.ai/v2` |
| API key | `$WORKBUDDY_ACCESS_TOKEN` |
| Chat | `POST /chat/completions` (stream) |
| Model | whatever `models` listed — typically `default-model` |

```bash
python3 -m workbuddy_openai status
python3 -m workbuddy_openai refresh
python3 -m workbuddy_openai logout
```

## Hermes

Do not change `model.default` unless you want WorkBuddy as the session default.

```yaml
providers:
  workbuddy:
    name: WorkBuddy
    base_url: https://www.workbuddy.ai/v2
    api_key_env: WORKBUDDY_ACCESS_TOKEN
    api: openai-completions
    models:
      - default-model
      - fast-model
      - balanced-model
      - primary-model
      - deep-model
```

`/model workbuddy/default-model`

Full generated list: `python3 -m workbuddy_openai snippet hermes`. Example file: `examples/hermes-provider.yaml`.

## OpenCode / Cursor / curl

See [docs/USAGE.md](docs/USAGE.md) and `examples/`.

Upstream expects **streaming** completions and a **system** message first. Hermes and OpenCode already do both.

## Optional localhost shim

Only if a client cannot send a Bearer JWT to `www.workbuddy.ai`:

```bash
python3 -m workbuddy_openai serve    # http://127.0.0.1:8787/v1
```

Prefer the direct URL.

## Layout

```
workbuddy_openai/   login, session, optional serve
docs/USAGE.md
examples/
tests/
```

```bash
python3 -m unittest tests.test_upstream
```

## Env

| var | meaning |
|---|---|
| `WORKBUDDY_OPENAI_HOME` | Config dir (default `~/.workbuddy-openai`) |
| `WORKBUDDY_ACCESS_TOKEN` | JWT for direct API calls |
| `WORKBUDDY_BASE_URL` | `https://www.workbuddy.ai/v2` |

Do not commit `~/.workbuddy-openai/`.
