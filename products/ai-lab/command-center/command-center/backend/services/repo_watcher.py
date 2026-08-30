"""
repo_watcher.py — uses watchdog to monitor lab repo paths and publish
file-level events (read/write) to the EventBus.

Only watches directories listed in WATCH_PATHS (configured via env or
passed at startup). Publishes a 'repo' event per file change so the
Repo Tracker tab stays live.
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from services.channels import channels
from services.repo_index_coordinator import get_coordinator


WATCH_PATHS: list[str] = []     # populated by main.py from env/config


class LabFileHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _publish(self, op: str, path: str, src_path: str = ""):
        rel = path
        try:
            path_norm = os.path.normpath(path)
            for wp in WATCH_PATHS:
                wp_norm = os.path.normpath(wp)
                if path_norm.startswith(wp_norm) or path.startswith(wp):
                    rel = os.path.relpath(path, os.path.dirname(wp))
                    break
            rel = rel.replace("\\", "/")  # match tree API so frontend fileActivity key matches
        except (ValueError, OSError):
            rel = path.replace("\\", "/")

        data = {
            "path": rel,
            "abs_path": path,
            "agent": "fs-watcher",      # real agent injected by supervisor bridge
            "op": op,
            "bytes_moved": None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        asyncio.run_coroutine_threadsafe(channels.ops.publish("repo", data), self._loop)

        # Hub indexing: mark repo dirty asynchronously (never block watcher).
        # Derive repo_id from the top-level directory name under the watched parent.
        try:
            repo_id = rel.split("/", 1)[0] if rel else ""
            if repo_id:
                get_coordinator().mark_dirty(repo_id, data)
        except Exception:
            pass

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory:
            self._publish("write", event.src_path)

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory:
            self._publish("write", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory:
            self._publish("exec", event.src_path)


_observer: Observer | None = None


def start_watcher(loop: asyncio.AbstractEventLoop):
    global _observer
    if not WATCH_PATHS:
        return
    handler = LabFileHandler(loop)
    _observer = Observer()
    for path in WATCH_PATHS:
        p = Path(path)
        if p.exists():
            _observer.schedule(handler, str(p), recursive=True)
    _observer.start()


def stop_watcher():
    global _observer
    if _observer:
        try:
            _observer.stop()
            if _observer.is_alive():
                _observer.join(timeout=3)
        except RuntimeError:
            pass
        _observer = None
