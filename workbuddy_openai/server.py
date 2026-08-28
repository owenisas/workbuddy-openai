"""Local OpenAI-compatible HTTP server in front of WorkBuddy."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from . import session as sess
from .http import HttpError
from .paths import DEFAULT_BIND, DEFAULT_PORT
from .upstream import chat_stream, fetch_config, list_models, parse_sse_objects, resolve_model

_cfg_lock = threading.Lock()
_cfg_cache: dict[str, Any] | None = None
_cfg_at = 0.0
_CFG_TTL = 300.0
_session_lock = threading.Lock()


def _load_session() -> dict[str, Any]:
    data = sess.load()
    if not data:
        raise RuntimeError("not logged in — python3 -m workbuddy_openai login")
    return data


def _config(force: bool = False) -> dict[str, Any]:
    global _cfg_cache, _cfg_at
    now = time.time()
    with _cfg_lock:
        if not force and _cfg_cache is not None and now - _cfg_at < _CFG_TTL:
            return _cfg_cache
        cfg = fetch_config(_load_session())
        _cfg_cache = cfg
        _cfg_at = now
        return cfg


def _check_key(handler: BaseHTTPRequestHandler, required: str | None) -> bool:
    if not required:
        return True
    got = handler.headers.get("Authorization") or ""
    token = got.removeprefix("Bearer ").strip() if got.lower().startswith("bearer ") else got.strip()
    if token == required:
        return True
    handler.send_response(401)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.wfile.write(b'{"error":{"message":"invalid api key","type":"invalid_request_error"}}')
    return False


def _json(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    raw = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Connection", "close")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(raw)


def _rewrite_first_role(buf: bytes, seen_role: list[bool]) -> bytes:
    """AI SDK requires the first delta.role to be the literal string 'assistant'."""
    if seen_role[0]:
        return buf
    try:
        text = buf.decode("utf-8")
    except Exception:
        return buf
    if not text.startswith("data:"):
        return buf
    payload = text[5:].strip()
    if payload in ("", "[DONE]"):
        return buf
    try:
        obj = json.loads(payload)
    except Exception:
        return buf
    choices = obj.get("choices")
    if not choices:
        return buf
    delta = choices[0].setdefault("delta", {})
    if not delta.get("role"):
        delta["role"] = "assistant"
    seen_role[0] = True
    return ("data: " + json.dumps(obj, separators=(",", ":")) + "\n").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    gateway_key: str | None = ""

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        import sys

        sys.stderr.write("[workbuddy-openai] " + (format % args) + "\n")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/health", "/v1/health"):
            st = sess.public_status(sess.load())
            _json(self, 200, {"ok": True, **st})
            return
        if path in ("/v1/models", "/models"):
            if not _check_key(self, self.gateway_key or None):
                return
            try:
                models = list_models(_config())
            except Exception as e:
                _json(self, 502, {"error": {"message": str(e), "type": "upstream_error"}})
                return
            _json(self, 200, {"object": "list", "data": models})
            return
        _json(self, 404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path not in ("/v1/chat/completions", "/chat/completions"):
            _json(self, 404, {"error": {"message": "not found", "type": "invalid_request_error"}})
            return
        if not _check_key(self, self.gateway_key or None):
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            _json(self, 400, {"error": {"message": "invalid json", "type": "invalid_request_error"}})
            return
        if not isinstance(body, dict):
            _json(self, 400, {"error": {"message": "body must be an object", "type": "invalid_request_error"}})
            return
        want_stream = bool(body.get("stream"))
        try:
            session = _load_session()
            cfg = _config()
            body["model"] = resolve_model(str(body.get("model") or "hy4-preview"), cfg)
            with _session_lock:
                session, source = chat_stream(session, body, cfg)
        except HttpError as e:
            parsed = e.json()
            msg = None
            if isinstance(parsed, dict):
                msg = parsed.get("msg") or parsed.get("message")
            _json(
                self,
                502,
                {
                    "error": {
                        "message": msg or f"upstream HTTP {e.status}",
                        "type": "upstream_error",
                        "code": parsed.get("code") if isinstance(parsed, dict) else e.status,
                    }
                },
            )
            return
        except Exception as e:
            _json(self, 500, {"error": {"message": str(e), "type": "server_error"}})
            return

        if want_stream:
            self._proxy_sse(source)
        else:
            self._buffer_json(source)

    def _proxy_sse(self, source) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        seen_role = [False]
        try:
            for chunk in source:
                out = _rewrite_first_role(chunk, seen_role)
                self.wfile.write(out)
                self.wfile.flush()
        except BrokenPipeError:
            return

    def _buffer_json(self, source) -> None:
        lines: list[str] = []
        try:
            for chunk in source:
                lines.append(chunk.decode("utf-8", "replace"))
        except Exception as e:
            _json(self, 502, {"error": {"message": str(e), "type": "upstream_error"}})
            return
        assembled = parse_sse_objects(lines)
        _json(self, 200, assembled)


def serve(
    host: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    gateway_key: str | None = None,
) -> None:
    Handler.gateway_key = gateway_key or ""
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"OpenAI-compatible gateway on http://{host}:{port}/v1", flush=True)
    print(f"  GET  /v1/models", flush=True)
    print(f"  POST /v1/chat/completions", flush=True)
    print(f"  GET  /health", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
        httpd.server_close()
