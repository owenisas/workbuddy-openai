"""WorkBuddy browser OAuth (cli-external-link) from zero.

Flow (from WorkBuddy 5.4.2 ExternalLinkAuthenticationProvider):
  1. POST /v2/plugin/auth/state?platform=workbuddy-ai  → {state, authUrl}
  2. Open authUrl in the user's browser (Tencent / WorkBuddy login)
  3. Poll GET  /v2/plugin/auth/token?state=… every 1s (code 11217 = still waiting)
  4. GET  /v2/plugin/login/account?state=… with the new Bearer
  5. Persist ~/.workbuddy-openai/session.json (mode 0600)
  6. Refresh later via POST /v2/plugin/auth/token/refresh + X-Refresh-Token
"""

from __future__ import annotations

import sys
import time
import webbrowser
from typing import Any, Callable

from . import session as sess
from .http import HttpError, request
from .paths import DEFAULT_DOMAIN, DEFAULT_ENDPOINT, DEFAULT_PLATFORM, DEFAULT_PREFIX, first_desktop_session

RETRY_TOKEN = 11217
RETRY_ACCOUNT = 12151
POLL_INTERVAL_S = 1.0
LOGIN_TIMEOUT_S = 300.0


def _plugin(endpoint: str, prefix: str, path: str) -> str:
    return f"{endpoint.rstrip('/')}/v2{prefix}{path}"


def anonymous_headers(domain: str) -> dict[str, str]:
    return {
        "X-Domain": domain,
        "X-No-Authorization": "true",
        "X-No-User-Id": "true",
        "X-No-Enterprise-Id": "true",
        "X-No-Department-Info": "true",
    }


def start_login(
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    platform: str = DEFAULT_PLATFORM,
    prefix: str = DEFAULT_PREFIX,
    domain: str = DEFAULT_DOMAIN,
) -> dict[str, str]:
    url = _plugin(endpoint, prefix, f"/auth/state?platform={platform}")
    _status, _hdrs, body = request("POST", url, headers=anonymous_headers(domain), body={})
    data = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or not data.get("state") or not data.get("authUrl"):
        raise RuntimeError(f"auth/state returned no state/authUrl: {body!r}"[:400])
    return {"state": str(data["state"]), "authUrl": str(data["authUrl"])}


def _envelope_code(body: Any) -> int | None:
    if isinstance(body, dict) and isinstance(body.get("code"), int):
        return body["code"]
    return None


def poll_token(
    state: str,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    prefix: str = DEFAULT_PREFIX,
    domain: str = DEFAULT_DOMAIN,
    timeout_s: float = LOGIN_TIMEOUT_S,
    on_tick: Callable[[], None] | None = None,
) -> dict[str, Any]:
    url = _plugin(endpoint, prefix, f"/auth/token?state={state}")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            _status, _hdrs, body = request("GET", url, headers=anonymous_headers(domain), timeout=15)
        except HttpError as e:
            parsed = e.json()
            if _envelope_code(parsed) == RETRY_TOKEN:
                if on_tick:
                    on_tick()
                time.sleep(POLL_INTERVAL_S)
                continue
            raise
        code = _envelope_code(body)
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if code == RETRY_TOKEN or not data:
            if on_tick:
                on_tick()
            time.sleep(POLL_INTERVAL_S)
            continue
        if isinstance(data, dict) and data.get("accessToken"):
            now = int(time.time() * 1000)
            data.setdefault("lastRefreshTime", now)
            if not data.get("expiresAt") and data.get("expiresIn"):
                data["expiresAt"] = now + int(data["expiresIn"]) * 1000
            if not data.get("refreshExpiresAt") and data.get("refreshExpiresIn"):
                data["refreshExpiresAt"] = now + int(data["refreshExpiresIn"]) * 1000
            if not data.get("domain"):
                data["domain"] = domain
            return data
        if on_tick:
            on_tick()
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError("login timed out (5 minutes). Re-run login and finish the browser flow.")


def fetch_account(
    state: str,
    auth: dict[str, Any],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    prefix: str = DEFAULT_PREFIX,
    domain: str = DEFAULT_DOMAIN,
) -> dict[str, Any] | None:
    url = _plugin(endpoint, prefix, f"/login/account?state={state}")
    headers = {
        "Authorization": f"Bearer {auth['accessToken']}",
        "X-Domain": auth.get("domain") or domain,
        "X-No-User-Id": "true",
        "X-No-Enterprise-Id": "true",
        "X-No-Department-Info": "true",
    }
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            _status, _hdrs, body = request("GET", url, headers=headers, timeout=15)
        except HttpError as e:
            parsed = e.json()
            if _envelope_code(parsed) == RETRY_ACCOUNT or e.status in (401, 403):
                time.sleep(POLL_INTERVAL_S)
                continue
            return None
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if isinstance(data, dict) and data.get("uid"):
            return data
        time.sleep(POLL_INTERVAL_S)
    return None


def fetch_accounts(
    auth: dict[str, Any],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    prefix: str = DEFAULT_PREFIX,
    domain: str = DEFAULT_DOMAIN,
) -> list[dict[str, Any]]:
    url = _plugin(endpoint, prefix, "/accounts")
    headers = {
        "Authorization": f"Bearer {auth['accessToken']}",
        "X-Domain": auth.get("domain") or domain,
    }
    try:
        _status, _hdrs, body = request("GET", url, headers=headers, timeout=20)
    except HttpError:
        return []
    data = (body or {}).get("data") if isinstance(body, dict) else None
    if isinstance(data, dict) and isinstance(data.get("accounts"), list):
        return data["accounts"]
    return []


def login(
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    platform: str = DEFAULT_PLATFORM,
    prefix: str = DEFAULT_PREFIX,
    domain: str = DEFAULT_DOMAIN,
    open_browser: bool = True,
    timeout_s: float = LOGIN_TIMEOUT_S,
) -> dict[str, Any]:
    started = start_login(endpoint=endpoint, platform=platform, prefix=prefix, domain=domain)
    auth_url = started["authUrl"]
    print(f"Open this URL and sign in with your WorkBuddy / Tencent account:\n  {auth_url}", file=sys.stderr)
    if open_browser:
        try:
            webbrowser.open(auth_url, new=2)
        except Exception as e:
            print(f"(could not open browser: {e})", file=sys.stderr)
    print("Waiting for login", file=sys.stderr, end="", flush=True)

    def tick() -> None:
        print(".", file=sys.stderr, end="", flush=True)

    auth = poll_token(
        started["state"],
        endpoint=endpoint,
        prefix=prefix,
        domain=domain,
        timeout_s=timeout_s,
        on_tick=tick,
    )
    print("\nToken received.", file=sys.stderr)
    account = fetch_account(
        started["state"], auth, endpoint=endpoint, prefix=prefix, domain=domain
    )
    accounts = fetch_accounts(auth, endpoint=endpoint, prefix=prefix, domain=domain)
    if not account and accounts:
        account = next((a for a in accounts if a.get("lastLogin")), accounts[0])
    if not account:
        account = {"uid": "", "nickname": "", "type": "personal"}
    payload = {
        "account": account,
        "auth": auth,
        "accounts": accounts or [account],
        "allAccounts": accounts or [account],
        "endpoint": endpoint,
        "platform": platform,
        "prefix": prefix,
    }
    path = sess.save(payload)
    print(f"Saved session → {path}", file=sys.stderr)
    return payload


def refresh(
    session: dict[str, Any],
    *,
    endpoint: str | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    auth = session.get("auth") or {}
    refresh_tok = auth.get("refreshToken")
    if not refresh_tok:
        return session
    ep = str(endpoint or session.get("endpoint") or DEFAULT_ENDPOINT)
    px = str(prefix or session.get("prefix") or DEFAULT_PREFIX)
    domain = auth.get("domain") or DEFAULT_DOMAIN
    url = _plugin(ep, px, "/auth/token/refresh")
    headers = {
        "X-Refresh-Token": refresh_tok,
        "X-Auth-Refresh-Source": "plugin",
        "X-Domain": domain,
        "Authorization": f"Bearer {auth.get('accessToken', '')}",
    }
    _status, _hdrs, body = request("POST", url, headers=headers, body={}, timeout=20)
    data = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or not data.get("accessToken"):
        raise RuntimeError("token refresh returned no accessToken")
    now = int(time.time() * 1000)
    data.setdefault("lastRefreshTime", now)
    if not data.get("expiresAt") and data.get("expiresIn"):
        data["expiresAt"] = now + int(data["expiresIn"]) * 1000
    if not data.get("refreshExpiresAt") and data.get("refreshExpiresIn"):
        data["refreshExpiresAt"] = now + int(data["refreshExpiresIn"]) * 1000
    if not data.get("domain"):
        data["domain"] = domain
    session = {**session, "auth": data}
    sess.save(session)
    return session


def import_desktop(src=None) -> dict[str, Any]:
    path = src or first_desktop_session()
    if path is None:
        raise FileNotFoundError(
            "no WorkBuddy desktop session found. Run the desktop app once, or: "
            "python3 -m workbuddy_openai login"
        )
    return sess.import_file(path)
