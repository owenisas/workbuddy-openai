"""Paths and region defaults. No secrets in this module."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ENDPOINT = "https://www.workbuddy.ai"
DEFAULT_PLATFORM = "workbuddy-ai"
DEFAULT_PREFIX = "/plugin"
DEFAULT_DOMAIN = "www.workbuddy.ai"
DEFAULT_UA = "WorkBuddy/5.4.2"
DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8787
AUTH_ID = "workbuddy-desktop-ai"

# Desktop app stores the same Keycloak session here (plaintext JSON, mode 0600).
DESKTOP_AUTH_CANDIDATES = (
    Path.home() / "Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop-ai.info",
    Path.home() / "Library/Application Support/CodeBuddyExtension/Data/Public/auth/Tencent-Cloud.coding-copilot.info",
    Path.home() / ".local/share/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop-ai.info",
)


def config_dir() -> Path:
    override = os.environ.get("WORKBUDDY_OPENAI_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".workbuddy-openai"


def session_path() -> Path:
    return config_dir() / "session.json"


def env_path() -> Path:
    return config_dir() / "env"


def first_desktop_session() -> Path | None:
    for p in DESKTOP_AUTH_CANDIDATES:
        if p.is_file():
            return p
    return None
