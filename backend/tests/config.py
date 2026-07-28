"""Execution-scoped Playwright authentication stored outside generated scripts."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")
_LOCK = threading.Lock()


def overwrite(execution_token: str, email: str, password: str) -> None:
    with _LOCK:
        CONFIG_PATH.write_text(
            json.dumps({
                "execution_token": execution_token,
                "email": email,
                "password": password,
            }),
            encoding="utf-8",
        )
        if os.name != "nt":
            os.chmod(CONFIG_PATH, 0o600)


def read(execution_token: str) -> dict[str, str] | None:
    with _LOCK:
        if not CONFIG_PATH.is_file():
            return None
        try:
            payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
    if payload.get("execution_token") != execution_token:
        return None
    if not payload.get("email") or not payload.get("password"):
        return None
    return {"email": str(payload["email"]), "password": str(payload["password"])}


def clear(execution_token: str | None = None) -> None:
    with _LOCK:
        if not CONFIG_PATH.is_file():
            return
        if execution_token:
            try:
                payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                payload = {}
            if payload.get("execution_token") != execution_token:
                return
        CONFIG_PATH.unlink(missing_ok=True)
