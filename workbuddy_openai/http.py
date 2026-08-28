"""HTTP helpers for the WorkBuddy SaaS host. Never prints bodies that may hold tokens."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

from .paths import DEFAULT_UA


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class HttpError(Exception):
    def __init__(self, status: int, body: str, headers: dict[str, str]):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body
        self.headers = headers

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except Exception:
            return None


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: Any = None,
    timeout: float = 30,
    stream: bool = False,
) -> tuple[int, dict[str, str], Any]:
    raw: bytes | None = None
    if body is not None:
        if isinstance(body, (bytes, bytearray)):
            raw = bytes(body)
        else:
            raw = json.dumps(body).encode("utf-8")
    hdrs = {"User-Agent": DEFAULT_UA, "Accept": "application/json", **(headers or {})}
    if raw is not None and "Content-Type" not in {k.title(): v for k, v in hdrs.items()}:
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=raw, headers=hdrs, method=method.upper())
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")
        raise HttpError(e.code, err_body, {k.lower(): v for k, v in e.headers.items()}) from None
    resp_headers = {k.lower(): v for k, v in resp.headers.items()}
    if stream:
        return resp.status, resp_headers, resp
    data = resp.read()
    text = data.decode("utf-8", "replace")
    try:
        parsed = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = text
    return resp.status, resp_headers, parsed
