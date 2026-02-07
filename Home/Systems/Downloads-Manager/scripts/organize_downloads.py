#!/usr/bin/env python3
"""
Downloads-Manager: watch Downloads folder, classify files, move to destination.
Supports --dry-run (log only, no moves) and --run-once (scan existing files then exit).
"""
import argparse
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path

# Project root = parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Extension -> (destination subfolder under destination_root). Lowercase keys.
DEFAULT_RULES = {
    "jpg": "Images/JPEG",
    "jpeg": "Images/JPEG",
    "png": "Images/PNG",
    "gif": "Images/GIF",
    "webp": "Images/WebP",
    "bmp": "Images/Other",
    "heic": "Images/Other",
    "svg": "Images/Other",
    "ico": "Images/Other",
    "exe": "PreRecycleBin",
    "msi": "PreRecycleBin",
    "dmg": "PreRecycleBin",
    "pdf": "Documents/PDF",
    "doc": "Documents/Word",
    "docx": "Documents/Word",
    "xls": "Documents/Excel",
    "xlsx": "Documents/Excel",
    "ppt": "Documents/Presentations",
    "pptx": "Documents/Presentations",
    "txt": "Documents/Other",
    "odt": "Documents/Other",
    "zip": "Archives",
    "7z": "Archives",
    "rar": "Archives",
    # Video / design idea dump (e.g. Firefly clips, UI inspiration)
    "mp4": "Webapp Design Idea Dump",
    "mov": "Webapp Design Idea Dump",
    "webm": "Webapp Design Idea Dump",
    "avi": "Webapp Design Idea Dump",
    "mkv": "Webapp Design Idea Dump",
    "m4v": "Webapp Design Idea Dump",
    "wmv": "Webapp Design Idea Dump",
}

# Filename keywords that indicate church-related video -> Church/Music Videos
CHURCH_VIDEO_KEYWORDS = (
    "church", "worship", "gospel", "hymn", "christian", "faith", "sermon",
    "praise", "ministry", "bible", "choir", "hymnal", "ccv", "bethel",
)


def get_destination_subfolder(ext: str, filename: str = "") -> str:
    """Return subfolder under destination_root. Uses filename for church-video detection."""
    ext_lower = ext.lower()
    default = DEFAULT_RULES.get(ext_lower, "Other")

    # Church-related videos (e.g. mp4) -> Church/Music Videos
    if ext_lower in ("mp4", "mov", "webm", "avi", "mkv", "m4v", "wmv"):
        name_lower = (filename or "").lower()
        if any(kw in name_lower for kw in CHURCH_VIDEO_KEYWORDS):
            return "Church/Music Videos"

    return default


def load_config():
    """Load config from config/config.yaml, expand env vars in paths."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        return {
            "watch_folder": os.path.expandvars(r"%USERPROFILE%\Downloads"),
            "destination_root": os.path.expandvars(r"%USERPROFILE%\OrganizedDownloads"),
            "stable_seconds": 3,
        }
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:
        logging.warning("Could not load config: %s. Using defaults.", e)
        raw = {}
    watch = raw.get("watch_folder") or os.path.expandvars(r"%USERPROFILE%\Downloads")
    dest = raw.get("destination_root") or os.path.expandvars(r"%USERPROFILE%\OrganizedDownloads")
    return {
        "watch_folder": os.path.expandvars(watch) if isinstance(watch, str) else watch,
        "destination_root": os.path.expandvars(dest) if isinstance(dest, str) else dest,
        "stable_seconds": int(raw.get("stable_seconds", 3)),
    }


def resolve_dest_path(destination_root: Path, subfolder: str, filename: str) -> Path:
    """Destination path; if file exists, add (1), (2), etc."""
    base = destination_root / subfolder
    dest = base / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for i in range(1, 1000):
        dest = base / f"{stem} ({i}){suffix}"
        if not dest.exists():
            return dest
    dest = base / f"{stem}_{int(time.time())}{suffix}"
    return dest


def process_file(
    src_path: Path,
    destination_root: Path,
    dry_run: bool,
    log: logging.Logger,
) -> bool:
    """Classify and move (or log if dry_run) one file. Returns True if handled."""
    if not src_path.is_file():
        return False
    ext = src_path.suffix
    if ext.startswith("."):
        ext = ext[1:]
    subfolder = get_destination_subfolder(ext, src_path.name)
    dest_path = resolve_dest_path(destination_root, subfolder, src_path.name)
    if dry_run:
        log.info("[DRY RUN] would move: %s -> %s", src_path, dest_path)
        return True
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dest_path))
        log.info("Moved: %s -> %s", src_path.name, dest_path)
        return True
    except Exception as e:
        log.error("Failed to move %s: %s", src_path, e)
        return False


def run_once(watch_folder: Path, destination_root: Path, dry_run: bool, log: logging.Logger) -> None:
    """Scan top-level files in watch_folder, process each (move or dry-run log)."""
    watch_path = Path(watch_folder)
    dest_root = Path(destination_root)
    if not watch_path.is_dir():
        log.error("Watch folder does not exist: %s", watch_path)
        return
    count = 0
    for p in watch_path.iterdir():
        if p.is_file():
            process_file(p, dest_root, dry_run, log)
            count += 1
    if dry_run:
        log.info("[DRY RUN] Scan complete. Would process %s file(s) in %s", count, watch_path)
    else:
        log.info("Scan complete. Processed %s file(s).", count)


def main():
    parser = argparse.ArgumentParser(description="Downloads-Manager: organize Downloads folder")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be done; do not move files")
    parser.add_argument("--run-once", action="store_true", help="Scan watch folder once and exit (no watcher)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger(__name__)

    config = load_config()
    watch_folder = Path(config["watch_folder"])
    destination_root = Path(config["destination_root"])

    log.info("Watch folder: %s", watch_folder)
    log.info("Destination root: %s", destination_root)
    if args.dry_run:
        log.info("DRY RUN - no files will be moved")

    if args.run_once:
        run_once(watch_folder, destination_root, args.dry_run, log)
        return 0

    # Watcher mode (not run for dry-run-only; user would run --run-once --dry-run for scan)
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
    except ImportError:
        log.error("Install watchdog: pip install watchdog")
        return 1

    class Handler(FileSystemEventHandler):
        def __init__(self, dest_root: Path, dry_run: bool, stable_seconds: float, logger: logging.Logger):
            self.dest_root = dest_root
            self.dry_run = dry_run
            self.stable_seconds = stable_seconds
            self.log = logger
            self._pending = {}

        def _schedule_process(self, src_path: Path):
            if not src_path.is_file():
                return
            key = str(src_path)
            if key in self._pending:
                return
            self._pending[key] = True

            def wait_stable_then_process():
                last_size, last_mtime = -1, -1
                deadline = time.monotonic() + self.stable_seconds
                while time.monotonic() < deadline:
                    try:
                        st = src_path.stat()
                        if st.st_size == last_size and st.st_mtime == last_mtime:
                            time.sleep(0.5)
                            if time.monotonic() >= deadline:
                                break
                        last_size, last_mtime = st.st_size, st.st_mtime
                        time.sleep(0.5)
                    except OSError:
                        time.sleep(0.5)
                try:
                    process_file(src_path, self.dest_root, self.dry_run, self.log)
                finally:
                    self._pending.pop(key, None)

            t = threading.Thread(target=wait_stable_then_process, daemon=True)
            t.start()

        def on_created(self, event):
            if event.is_directory:
                return
            self._schedule_process(Path(event.src_path))

        def on_moved(self, event):
            if event.is_directory:
                return
            self._schedule_process(Path(event.dest_path))

    handler = Handler(
        destination_root,
        dry_run=args.dry_run,
        stable_seconds=config["stable_seconds"],
        logger=log,
    )
    observer = Observer()
    observer.schedule(handler, str(watch_folder), recursive=False)
    observer.start()
    log.info("Watching %s (Ctrl+C to stop)", watch_folder)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
