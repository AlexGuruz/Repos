#!/usr/bin/env python3
"""
Drive Watcher - monitors Google Drive folder for new sales CSV files.
Downloads new files to csv_dump, then runs extract_unique_brands and calculate_daily_cog.
Config: config/config.yaml (watch_folder_id, paths.copy_rules for copying to paths outside C:).
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

from lib.config_loader import get_drive_folder_id, get_path, load_config


def get_drive_service():
    """Build Drive API v3 service using service account (device-wide or config)."""
    from lib.config_loader import get_service_account_path
    creds_file = get_service_account_path()
    if not creds_file:
        raise FileNotFoundError(
            "No service account found. Put google_service_account.json in D:\\_config\\ "
            "or set GOOGLE_APPLICATION_CREDENTIALS"
        )
    credentials = service_account.Credentials.from_service_account_file(
        str(creds_file),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=credentials)


def list_csv_files(service, folder_id: str):
    """List CSV files in the Drive folder (by .csv extension)."""
    results = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, modifiedTime)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )
    files = results.get("files", [])
    return [f for f in files if f.get("name", "").lower().endswith(".csv")]


def download_file(service, file_id: str, dest_path: Path):
    """Download a Drive file to local path."""
    request = service.files().get_media(fileId=file_id)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


def load_state(state_path: Path) -> dict:
    """Load drive watcher state (processed file IDs)."""
    if not state_path.exists():
        return {"processed_ids": []}
    with open(state_path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state_path: Path, state: dict):
    """Save drive watcher state."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def copy_to_configured_paths(source_path: Path, filename: str) -> list:
    """
    If config has paths.copy_rules for this filename (or _all), copy the file to each path.
    Paths can be full file paths or directories (same filename). Returns list of paths written.
    """
    written = []
    cfg = load_config()
    rules = (cfg.get("paths") or {}).get("copy_rules")
    if not rules or not isinstance(rules, dict):
        return written
    targets = []
    if "_all" in rules:
        val = rules["_all"]
        if isinstance(val, list):
            targets.extend(val)
        elif isinstance(val, str) and val.strip():
            targets.append(val.strip())
    if filename in rules:
        val = rules[filename]
        if isinstance(val, list):
            targets.extend(val)
        elif isinstance(val, str) and val.strip():
            targets.append(val.strip())
    for raw in targets:
        raw = raw.strip()
        if not raw:
            continue
        is_dir = raw.endswith("/") or raw.endswith("\\")
        dest = Path(raw.rstrip("/\\"))
        if not dest.is_absolute():
            dest = (Path(__file__).parent.parent) / dest
        try:
            if not is_dir and dest.suffix and dest.suffix.lower() == ".csv":
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, dest)
                written.append(str(dest))
            else:
                dest.mkdir(parents=True, exist_ok=True)
                out = dest / filename
                shutil.copy2(source_path, out)
                written.append(str(out))
        except Exception as e:
            print(f"[drive_watcher] Failed to copy {filename} to {raw}: {e}")
    return written


def run_once():
    """Check Drive once, download new CSVs, run COG pipeline."""
    if not HAS_GOOGLE:
        print("[drive_watcher] ERROR: Install google-api-python-client and google-auth")
        print("  pip install google-api-python-client google-auth")
        return 1

    folder_id = get_drive_folder_id()
    csv_dump = get_path("csv_dump", "data/csv_dump")
    state_dir = get_path("state", "data/state")
    state_path = state_dir / "drive_watcher_state.json"
    scripts_dir = Path(__file__).parent

    csv_dump.mkdir(parents=True, exist_ok=True)

    try:
        service = get_drive_service()
    except FileNotFoundError as e:
        print(f"[drive_watcher] {e}")
        print("  Add config/config.yaml and config/service_account.json")
        return 1

    state = load_state(state_path)
    processed = set(state.get("processed_ids", []))

    files = list_csv_files(service, folder_id)
    new_files = []

    for f in files:
        fid = f["id"]
        name = f.get("name", "unknown.csv")
        if fid in processed:
            continue
        dest = csv_dump / name
        if dest.exists():
            processed.add(fid)
            continue
        try:
            download_file(service, fid, dest)
            new_files.append(dest)
            processed.add(fid)
            # Copy to configured paths outside C: if paths.copy_rules is set
            copied = copy_to_configured_paths(dest, name)
            for p in copied:
                print(f"[drive_watcher] Copied to {p}")
        except Exception as e:
            print(f"[drive_watcher] Failed to download {name}: {e}")

    state["processed_ids"] = list(processed)
    save_state(state_path, state)

    if not new_files:
        print("[drive_watcher] No new CSV files")
        return 0

    print(f"[drive_watcher] Downloaded {len(new_files)} new file(s)")

    # Run extract_unique_brands
    try:
        subprocess.run(
            [sys.executable, str(scripts_dir / "extract_unique_brands.py")],
            cwd=str(scripts_dir.parent),
            check=False,
        )
    except Exception as e:
        print(f"[drive_watcher] extract_unique_brands failed: {e}")

    # Run calculate_daily_cog for new files
    for p in new_files:
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(scripts_dir / "calculate_daily_cog.py"),
                    "--csv-files",
                    str(p),
                ],
                cwd=str(scripts_dir.parent),
                check=False,
            )
        except Exception as e:
            print(f"[drive_watcher] calculate_daily_cog failed for {p}: {e}")

    return 0


def main():
    ap = argparse.ArgumentParser(description="Watch Google Drive for sales CSVs")
    ap.add_argument("--run-once", action="store_true", help="Run once and exit")
    args = ap.parse_args()

    cfg = load_config()
    interval = cfg.get("google_drive", {}).get("check_interval_minutes", 5) * 60

    if args.run_once:
        return run_once()

    print(f"[drive_watcher] Watching Drive folder, checking every {interval // 60} min")
    while True:
        run_once()
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main() or 0)
