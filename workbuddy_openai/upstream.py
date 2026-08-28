"""WorkBuddy upstream chat + product config."""

from __future__ import annotations

import json
import time
from typing import Any, Iterator

from . import session as sess
from .auth import refresh as refresh_session
from .http import HttpError, request
from .paths import DEFAULT_DOMAIN, DEFAULT_ENDPOINT, DEFAULT_UA

DEFAULT_SYSTEM = "You are a helpful assistant."
DEFAULT_MAX_TOKENS = 8192


def session_headers(session: dict[str, Any]) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {sess.access_token(session)}",
        "X-User-Id": sess.uid(session),
        "X-Domain": sess.domain(session, DEFAULT_DOMAIN),
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def endpoint_of(session: dict[str, Any]) -> str:
    return str(session.get("endpoint") or DEFAULT_ENDPOINT).rstrip("/")


def ensure_system(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": DEFAULT_SYSTEM}, *messages]


def fetch_config(session: dict[str, Any]) -> dict[str, Any]:
    url = f"{endpoint_of(session)}/v3/config"
    _status, _hdrs, body = request("GET", url, headers=session_headers(session), timeout=30)
    if not isinstance(body, dict) or body.get("code") not in (0, None):
        raise RuntimeError(f"/v3/config failed: {str(body)[:300]}")
    return body.get("data") or {}


def list_models(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    models = cfg.get("models") or []
    out = []
    for m in models:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        out.append(
            {
                "id": m["id"],
                "object": "model",
                "created": 0,
                "owned_by": "workbuddy",
                "name": m.get("name") or m["id"],
                "credits": m.get("credits"),
                "max_input_tokens": m.get("maxInputTokens"),
                "max_output_tokens": m.get("maxOutputTokens"),
                "supports_tools": bool(m.get("supportsToolCall")),
                "supports_images": bool(m.get("supportsImages")),
                "reasoning": bool(m.get("supportsReasoning") or m.get("onlyReasoning")),
            }
        )
    return out


def alias_map(cfg: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for m in cfg.get("models") or []:
        mid = str(m.get("id") or "")
        if not mid:
            continue
        mapping[mid.lower()] = mid
        name = str(m.get("name") or "").strip()
        if name:
            mapping[name.lower()] = mid
            mapping[name.lower().replace(" ", "-")] = mid
            mapping[name.lower().replace(" ", "")] = mid
    # Screenshot / common aliases
    mapping.setdefault("hy4", mapping.get("hy4-preview", "hy4-preview"))
    mapping.setdefault("hy4 preview", mapping.get("hy4-preview", "hy4-preview"))
    mapping.setdefault("fast", mapping.get("fast-model", "fast-model"))
    mapping.setdefault("balanced", mapping.get("balanced-model", "balanced-model"))
    mapping.setdefault("primary", mapping.get("primary-model", "primary-model"))
    mapping.setdefault("ultimate", mapping.get("deep-model", "deep-model"))
    mapping.setdefault("deep", mapping.get("deep-model", "deep-model"))
    mapping.setdefault("auto", mapping.get("default-model", "default-model"))
    return mapping


def resolve_model(model: str, cfg: dict[str, Any] | None) -> str:
    raw = (model or "").strip()
    if not raw:
        return "hy4-preview"
    if not cfg:
        return raw
    return alias_map(cfg).get(raw.lower(), raw)


def _upstream_body(openai_body: dict[str, Any], cfg: dict[str, Any] | None) -> dict[str, Any]:
    messages = ensure_system(list(openai_body.get("messages") or []))
    model = resolve_model(str(openai_body.get("model") or "hy4-preview"), cfg)
    out: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,  # WorkBuddy rejects non-stream (code 11101)
    }
    max_tokens = openai_body.get("max_tokens") or openai_body.get("max_completion_tokens")
    out["max_tokens"] = int(max_tokens) if max_tokens else DEFAULT_MAX_TOKENS
    for key in ("temperature", "top_p", "tools", "tool_choice", "stop", "user"):
        if key in openai_body and openai_body[key] is not None:
            out[key] = openai_body[key]
    return out


def chat_stream(
    session: dict[str, Any],
    openai_body: dict[str, Any],
    cfg: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Iterator[bytes]]:
    """Open an upstream SSE stream. Caller must close the response."""
    payload = _upstream_body(openai_body, cfg)
    url = f"{endpoint_of(session)}/v2/chat/completions"
    headers = {
        **session_headers(session),
        "Accept": "text/event-stream",
    }

    def open_stream(sess_obj: dict[str, Any]):
        hdrs = {**headers, **session_headers(sess_obj), "Accept": "text/event-stream"}
        return request("POST", url, headers=hdrs, body=payload, timeout=300, stream=True)

    try:
        status, hdrs, resp = open_stream(session)
    except HttpError as e:
        if e.status in (401, 403):
            session = refresh_session(session)
            status, hdrs, resp = open_stream(session)
        else:
            raise
    return session, _iter_sse(resp)


def _iter_sse(resp) -> Iterator[bytes]:
    try:
        while True:
            line = resp.readline()
            if not line:
                break
            yield line
    finally:
        try:
            resp.close()
        except Exception:
            pass


def parse_sse_objects(lines: list[str]) -> dict[str, Any]:
    contents: list[str] = []
    reasoning: list[str] = []
    finish = None
    usage = None
    model = None
    cid = None
    tool_acc: dict[int, dict[str, Any]] = {}
    for raw in lines:
        s = raw.strip()
        if not s.startswith("data:"):
            continue
        payload = s[5:].strip()
        if payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if obj.get("id"):
            cid = obj["id"]
        if obj.get("model"):
            model = obj["model"]
        if obj.get("usage"):
            usage = obj["usage"]
        for c in obj.get("choices") or []:
            if c.get("finish_reason"):
                finish = c["finish_reason"]
            delta = c.get("delta") or {}
            if delta.get("content"):
                contents.append(delta["content"])
            rc = delta.get("reasoning_content")
            if isinstance(rc, str) and rc:
                reasoning.append(rc)
            for tc in delta.get("tool_calls") or []:
                idx = int(tc.get("index") or 0)
                slot = tool_acc.setdefault(
                    idx,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                if tc.get("id"):
                    slot["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    slot["function"]["arguments"] += fn["arguments"]
    message: dict[str, Any] = {"role": "assistant", "content": "".join(contents) or None}
    if reasoning:
        message["reasoning_content"] = "".join(reasoning)
    tools = [tool_acc[i] for i in sorted(tool_acc)]
    if tools:
        message["tool_calls"] = tools
        message["content"] = None
        finish = finish or "tool_calls"
    return {
        "id": cid or f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or "hy4-preview",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish or "stop",
            }
        ],
        "usage": usage or {},
    }
