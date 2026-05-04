"""Credential resolution for OpenAI / Gemini / OpenRouter.

Read order (first hit wins):
1. Environment variable (e.g. ``OPENAI_API_KEY`` or ``GEMINI_API_KEY``).
2. ``~/.solypsizm/credentials.json`` — chmod 600, gitignored.

For OpenAI specifically, callers should *not* rely on us resolving an API
key when OAuth is in use; the ``openai`` SDK reads OAuth tokens itself
from ``~/.openai/auth.json``. Our job there is just to confirm a token
exists and report which mode is active.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

CREDENTIALS_PATH = Path.home() / ".solypsizm" / "credentials.json"


def _load_creds_file() -> dict[str, str]:
    if not CREDENTIALS_PATH.is_file():
        return {}
    try:
        return json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_creds_file(creds: dict[str, str]) -> None:
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    # chmod 600 so other users on the machine can't read it.
    try:
        CREDENTIALS_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def get(name: str, *, env_var: str | None = None) -> str | None:
    """Resolve a credential by short name. Returns None if not found."""
    if env_var:
        from_env = os.environ.get(env_var)
        if from_env:
            return from_env
    return _load_creds_file().get(name)


def set_(name: str, value: str) -> None:
    creds = _load_creds_file()
    creds[name] = value
    _save_creds_file(creds)


def remove(name: str) -> bool:
    creds = _load_creds_file()
    if name not in creds:
        return False
    del creds[name]
    _save_creds_file(creds)
    return True


def status() -> dict[str, str]:
    """Return per-provider availability without leaking the values themselves.

    Each entry is one of: 'env' (set via env var), 'file' (in
    credentials.json), 'oauth' (OpenAI OAuth token present), 'missing'.
    """
    out: dict[str, str] = {}
    creds = _load_creds_file()

    # Gemini.
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        out["gemini"] = "env"
    elif creds.get("gemini"):
        out["gemini"] = "file"
    else:
        out["gemini"] = "missing"

    # OpenRouter.
    if os.environ.get("OPENROUTER_API_KEY"):
        out["openrouter"] = "env"
    elif creds.get("openrouter"):
        out["openrouter"] = "file"
    else:
        out["openrouter"] = "missing"

    # OpenAI: prefer OAuth; fall back to API key.
    openai_oauth = Path.home() / ".openai" / "auth.json"
    if openai_oauth.is_file():
        out["openai"] = "oauth"
    elif os.environ.get("OPENAI_API_KEY"):
        out["openai"] = "env"
    elif creds.get("openai"):
        out["openai"] = "file"
    else:
        out["openai"] = "missing"

    return out


def openai_credential() -> str | None:
    """Resolve the OpenAI credential. Prefer the OAuth flow (return None,
    let the SDK read it); fall back to API key."""
    openai_oauth = Path.home() / ".openai" / "auth.json"
    if openai_oauth.is_file():
        return None  # SDK will pick up OAuth on its own
    return get("openai", env_var="OPENAI_API_KEY")


def gemini_credential() -> str | None:
    return get("gemini", env_var="GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def openrouter_credential() -> str | None:
    return get("openrouter", env_var="OPENROUTER_API_KEY")
