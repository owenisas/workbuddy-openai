"""CLI: login / import-desktop / status / models / serve."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import session as sess
from .auth import import_desktop, login
from .paths import DEFAULT_BIND, DEFAULT_ENDPOINT, DEFAULT_PORT, first_desktop_session, session_path
from .server import serve
from .upstream import fetch_config, list_models


def _cmd_login(args: argparse.Namespace) -> int:
    if args.import_desktop or args.session_file:
        src = Path(args.session_file).expanduser() if args.session_file else first_desktop_session()
        data = import_desktop(src)
        print(json.dumps(sess.public_status(data), indent=2))
        return 0
    login(
        endpoint=args.endpoint,
        open_browser=not args.no_browser,
        timeout_s=args.timeout,
    )
    print(json.dumps(sess.public_status(sess.load()), indent=2))
    return 0


def _cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps(sess.public_status(sess.load()), indent=2))
    return 0 if sess.load() else 1


def _cmd_logout(_args: argparse.Namespace) -> int:
    sess.clear()
    print(f"removed {session_path()}")
    return 0


def _cmd_models(_args: argparse.Namespace) -> int:
    session = sess.load()
    if not session:
        print("not logged in", file=sys.stderr)
        return 1
    models = list_models(fetch_config(session))
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


def _cmd_serve(args: argparse.Namespace) -> int:
    if not sess.load():
        print("not logged in — run: python3 -m workbuddy_openai login", file=sys.stderr)
        return 1
    key = args.api_key or os.environ.get("WORKBUDDY_GATEWAY_KEY") or None
    serve(host=args.host, port=args.port, gateway_key=key)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="workbuddy-openai",
        description="Log in with your WorkBuddy/Tencent account and serve an OpenAI-compatible API.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    login_p = sub.add_parser("login", help="Browser OAuth from zero, or import the desktop app session")
    login_p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    login_p.add_argument("--no-browser", action="store_true", help="Print the URL only; do not open a browser")
    login_p.add_argument("--timeout", type=float, default=300)
    login_p.add_argument("--import-desktop", action="store_true", help="Copy the already-logged-in WorkBuddy desktop session")
    login_p.add_argument("--session-file", help="Explicit path to a workbuddy-desktop-ai.info file")
    login_p.set_defaults(func=_cmd_login)

    st = sub.add_parser("status", help="Show whether a session is saved (no token values)")
    st.set_defaults(func=_cmd_status)

    lo = sub.add_parser("logout", help="Delete the local session file")
    lo.set_defaults(func=_cmd_logout)

    md = sub.add_parser("models", help="List live models from /v3/config")
    md.set_defaults(func=_cmd_models)

    sv = sub.add_parser("serve", help="OpenAI-compatible gateway (default 127.0.0.1:8787)")
    sv.add_argument("--host", default=DEFAULT_BIND)
    sv.add_argument("--port", type=int, default=DEFAULT_PORT)
    sv.add_argument("--api-key", help="If set, require Authorization: Bearer <key>. Else WORKBUDDY_GATEWAY_KEY.")
    sv.set_defaults(func=_cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
