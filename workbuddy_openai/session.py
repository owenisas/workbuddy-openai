"""On-disk session. Mode 0600. Never log token values."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from .paths import DEFAULT_ENDPOINT, config_dir, env_path, session_path


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".session.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load() -> dict[str, Any] | None:
    p = session_path()
    if not p.is_file():
        return None
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def save(session: dict[str, Any]) -> Path:
    config_dir().mkdir(parents=True, exist_ok=True)
    _atomic_write(session_path(), session)
    _write_env(session)
    return session_path()


def _write_env(session: dict[str, Any]) -> None:
    tok = (session.get("auth") or {}).get("accessToken") or ""
    base = str(session.get("endpoint") or DEFAULT_ENDPOINT).rstrip("/") + "/v2"
    path = env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"WORKBUDDY_ACCESS_TOKEN={tok}\nWORKBUDDY_BASE_URL={base}\n"
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def clear() -> None:
    for p in (session_path(), env_path()):
        if p.is_file():
            p.unlink()


def import_file(src: Path) -> dict[str, Any]:
    with src.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "auth" not in data:
        raise ValueError(f"not a WorkBuddy session file: {src}")
    if not (data.get("auth") or {}).get("accessToken"):
        raise ValueError("session file has no accessToken")
    save(data)
    return data


def public_status(session: dict[str, Any] | None) -> dict[str, Any]:
    if not session:
        return {"logged_in": False, "path": str(session_path())}
    account = session.get("account") or {}
    auth = session.get("auth") or {}
    exp = auth.get("expiresAt")
    now = int(time.time() * 1000)
    return {
        "logged_in": True,
        "path": str(session_path()),
        "env_path": str(env_path()),
        "base_url": str(session.get("endpoint") or DEFAULT_ENDPOINT).rstrip("/") + "/v2",
        "uid": account.get("uid"),
        "nickname": account.get("nickname"),
        "type": account.get("type"),
        "domain": auth.get("domain"),
        "token_type": auth.get("tokenType"),
        "expires_at_ms": exp,
        "expired": bool(exp and exp < now),
        "has_refresh": bool(auth.get("refreshToken")),
    }


def access_token(session: dict[str, Any]) -> str:
    tok = (session.get("auth") or {}).get("accessToken")
    if not tok:
        raise RuntimeError("session has no accessToken — run: python3 -m workbuddy_openai login")
    return tok


def uid(session: dict[str, Any]) -> str:
    return str((session.get("account") or {}).get("uid") or "")


def domain(session: dict[str, Any], fallback: str) -> str:
    return str((session.get("auth") or {}).get("domain") or fallback)
