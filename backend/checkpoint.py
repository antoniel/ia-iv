from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from backend.config import CHECKPOINT_PATH

log = logging.getLogger(__name__)

TaskStatus = Literal["pending", "running", "done", "failed"]
_LOCK_PATH = CHECKPOINT_PATH.with_suffix(".lock")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def checkpoint_lock() -> Iterator[None]:
    """Lock de arquivo — seguro entre processos paralelos."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK_PATH.open("w", encoding="utf-8") as lockf:
        try:
            import fcntl

            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        yield
        try:
            import fcntl

            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass


def load_checkpoint(path: Path = CHECKPOINT_PATH) -> dict:
    if not path.exists():
        return {"version": 1, "tasks": {}}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_checkpoint(data: dict, path: Path = CHECKPOINT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def task_key(*parts: str) -> str:
    return ":".join(parts)


def get_task_status(key: str) -> TaskStatus:
    with checkpoint_lock():
        data = load_checkpoint()
        return data.get("tasks", {}).get(key, {}).get("status", "pending")


def is_done(key: str) -> bool:
    return get_task_status(key) == "done"


def mark_running(key: str) -> None:
    with checkpoint_lock():
        data = load_checkpoint()
        data.setdefault("tasks", {})[key] = {"status": "running", "started_at": _now()}
        save_checkpoint(data)


def mark_done(key: str, **meta: object) -> None:
    with checkpoint_lock():
        data = load_checkpoint()
        entry = data.setdefault("tasks", {}).get(key, {})
        entry.update({"status": "done", "finished_at": _now(), **meta})
        data["tasks"][key] = entry
        save_checkpoint(data)
    log.info("checkpoint ✓ %s", key)


def mark_failed(key: str, error: str) -> None:
    with checkpoint_lock():
        data = load_checkpoint()
        data.setdefault("tasks", {})[key] = {
            "status": "failed",
            "failed_at": _now(),
            "error": error,
        }
        save_checkpoint(data)
    log.error("checkpoint ✗ %s — %s", key, error)
