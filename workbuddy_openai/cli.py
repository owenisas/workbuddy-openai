"""CLI: login, then point Hermes/OpenCode at https://www.workbuddy.ai/v2."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import session as sess
from .auth import import_desktop, login, refresh
from .paths import (
    DEFAULT_BIND,
    DEFAULT_ENDPOINT,
    DEFAULT_PORT,
    env_path,
    first_desktop_session,
    session_path,
)
from .server import serve
from .upstream import fetch_config, list_models


def _require_session() -> dict:
    data = sess.load()
    if not data:
        print("not logged in — python3 -m workbuddy_openai login", file=sys.stderr)
        raise SystemExit(1)
    return data


def _print_status(data: dict | None) -> None:
    print(json.dumps(sess.public_status(data), indent=2))


def _cmd_login(args: argparse.Namespace) -> int:
    if args.import_desktop or args.session_file:
        src = Path(args.session_file).expanduser() if args.session_file else first_desktop_session()
        data = import_desktop(src)
    else:
        login(
            endpoint=args.endpoint,
            open_browser=not args.no_browser,
            timeout_s=args.timeout,
        )
        data = sess.load()
    _print_status(data)
    print(f"env file (mode 600): {env_path()}", file=sys.stderr)
    print("next: python3 -m workbuddy_openai snippet hermes", file=sys.stderr)
    return 0


def _cmd_status(_args: argparse.Namespace) -> int:
    data = sess.load()
    _print_status(data)
    return 0 if data else 1


def _cmd_logout(_args: argparse.Namespace) -> int:
    sess.clear()
    print(f"removed {session_path()} and {env_path()}")
    return 0


def _cmd_refresh(_args: argparse.Namespace) -> int:
    data = refresh(_require_session())
    _print_status(data)
    return 0


def _cmd_models(_args: argparse.Namespace) -> int:
    models = list_models(fetch_config(_require_session()))
    for m in models:
        extra = []
        if m.get("credits"):
            extra.append(str(m["credits"]))
        if m.get("reasoning"):
            extra.append("reasoning")
        if m.get("supports_tools"):
            extra.append("tools")
        suffix = f"  ({', '.join(extra)})" if extra else ""
        print(f"{m['id']:28s}  {m.get('name')}{suffix}")
    return 0


def _model_ids() -> list[str]:
    try:
        return [m["id"] for m in list_models(fetch_config(_require_session()))]
    except Exception:
        return [
            "default-model",
            "fast-model",
            "balanced-model",
            "primary-model",
            "deep-model",
        ]


def _cmd_snippet(args: argparse.Namespace) -> int:
    data = _require_session()
    base = sess.public_status(data).get("base_url") or (DEFAULT_ENDPOINT.rstrip("/") + "/v2")
    ids = _model_ids()
    kind = args.target
    if kind == "hermes":
        models = "\n".join(f"      - {i}" for i in ids)
        print(
            f"""# add under providers: in the active Hermes profile config
# put WORKBUDDY_ACCESS_TOKEN in that profile's .env (copy from {env_path()})
providers:
  workbuddy:
    name: WorkBuddy
    base_url: {base}
    api_key_env: WORKBUDDY_ACCESS_TOKEN
    api: openai-completions
    models:
{models}"""
        )
    elif kind == "opencode":
        entries = []
        for i in ids:
            entries.append(f'        "{i}": {{ "name": "{i}" }}')
        inner = ",\n".join(entries)
        print(
            f"""{{
  "provider": {{
    "workbuddy": {{
      "npm": "@ai-sdk/openai-compatible",
      "name": "WorkBuddy",
      "options": {{
        "baseURL": "{base}",
        "apiKey": "{{env:WORKBUDDY_ACCESS_TOKEN}}"
      }},
      "models": {{
{inner}
      }}
    }}
  }}
}}"""
        )
    else:
        print(f"base_url={base}")
        print(f"api_key_env=WORKBUDDY_ACCESS_TOKEN")
        print(f"env_file={env_path()}")
        print("models=" + ",".join(ids))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    _require_session()
    key = args.api_key or os.environ.get("WORKBUDDY_GATEWAY_KEY") or None
    serve(host=args.host, port=args.port, gateway_key=key)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="workbuddy-openai",
        description="Log in to WorkBuddy, then use https://www.workbuddy.ai/v2 as an OpenAI base URL.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    login_p = sub.add_parser("login", help="Browser OAuth from zero, or import the desktop app session")
    login_p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    login_p.add_argument("--no-browser", action="store_true", help="Print the URL only; do not open a browser")
    login_p.add_argument("--timeout", type=float, default=300)
    login_p.add_argument("--import-desktop", action="store_true", help="Copy the already-logged-in WorkBuddy desktop session")
    login_p.add_argument("--session-file", help="Explicit path to a workbuddy-desktop-ai.info file")
    login_p.set_defaults(func=_cmd_login)

    st = sub.add_parser("status", help="Logged-in uid/nickname/expiry (no tokens)")
    st.set_defaults(func=_cmd_status)

    lo = sub.add_parser("logout", help="Delete the local session and env file")
    lo.set_defaults(func=_cmd_logout)

    rf = sub.add_parser("refresh", help="Refresh the access token")
    rf.set_defaults(func=_cmd_refresh)

    md = sub.add_parser("models", help="List live models from /v3/config")
    md.set_defaults(func=_cmd_models)

    sn = sub.add_parser("snippet", help="Print a Hermes/OpenCode/env snippet (no token values)")
    sn.add_argument("target", choices=["hermes", "opencode", "env"])
    sn.set_defaults(func=_cmd_snippet)

    sv = sub.add_parser("serve", help="Optional localhost shim if a client cannot call www.workbuddy.ai/v2")
    sv.add_argument("--host", default=DEFAULT_BIND)
    sv.add_argument("--port", type=int, default=DEFAULT_PORT)
    sv.add_argument("--api-key", help="If set, require Authorization: Bearer <key>")
    sv.set_defaults(func=_cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
