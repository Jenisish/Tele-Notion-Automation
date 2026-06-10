"""Persistent state: last-seen message IDs, imported keys, status."""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from src.config import STATE_FILE, STATUS_FILE, IMPORTED_FILE
from src.logger import get_logger

log = get_logger("state")

_lock = threading.Lock()


def _load_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ── Sync state (last message ID per channel) ──────────

def get_last_message_id(channel: str) -> int:
    """Return the last processed message ID for a channel (0 = none)."""
    with _lock:
        state: dict = _load_json(STATE_FILE, {})
    return state.get(channel, 0)


def set_last_message_id(channel: str, msg_id: int) -> None:
    with _lock:
        state: dict = _load_json(STATE_FILE, {})
        state[channel] = msg_id
        _save_json(STATE_FILE, state)


# ── Deduplication (set of 'channel:msg_id' strings) ───

def is_imported(key: str) -> bool:
    with _lock:
        data: set = set(_load_json(IMPORTED_FILE, []))
    return key in data


def mark_imported(key: str) -> None:
    with _lock:
        data: set = set(_load_json(IMPORTED_FILE, []))
        data.add(key)
        _save_json(IMPORTED_FILE, list(data))


# ── Status file (health monitoring) ────────────────────

def write_status(**kwargs) -> None:
    with _lock:
        status: dict = _load_json(STATUS_FILE, {})
        status["last_update"] = datetime.now(timezone.utc).isoformat()
        status.update(kwargs)
        _save_json(STATUS_FILE, status)


def read_status() -> dict:
    return _load_json(STATUS_FILE, {})
