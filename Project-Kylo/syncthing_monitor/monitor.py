import datetime
import os
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

try:
    from telemetry.emitter import emit as telemetry_emit
except Exception:  # pragma: no cover - optional dependency
    telemetry_emit = None

_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_env() -> None:
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key in os.environ:
            continue
        os.environ[key] = value.strip()


_load_env()

API_KEY = os.environ.get("SYNCTHING_API_KEY", "PUT_YOUR_API_KEY_HERE")
API_URL = os.environ.get("SYNCTHING_API_URL", "http://127.0.0.1:8384/rest/db/status?folder=")
LOG_PATH = os.environ.get("SYNCTHING_LOG_PATH", r"D:\syncthing_sync_log.txt")
FOLDER_IDS = os.environ.get("SYNCTHING_FOLDER_IDS", "aiassist,scripthub,zbxah-3zeap")
INTERVAL = int(os.environ.get("SYNCTHING_POLL_INTERVAL", "60"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS = [
    entry.strip()
    for entry in os.environ.get("TELEGRAM_CHAT_ID", "").split(",")
    if entry.strip()
]
TELEGRAM_ALLOWED_USER_IDS = [
    entry.strip()
    for entry in os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
    if entry.strip()
]
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "").strip()
EMAIL_RECIPIENTS = [
    entry.strip()
    for entry in os.environ.get("EMAIL_RECIPIENTS", "").split(",")
    if entry.strip()
]

_headers = {"X-API-Key": API_KEY}
_executor = ThreadPoolExecutor(max_workers=4)

_SYNCTHING_BASE_URL = os.environ.get("SYNCTHING_BASE_URL", "").rstrip("/")
if not _SYNCTHING_BASE_URL:
    if "rest/db/status" in API_URL:
        _SYNCTHING_BASE_URL = API_URL.split("rest/db/status", 1)[0].rstrip("/")
    else:
        _SYNCTHING_BASE_URL = API_URL.split("?")[0].rstrip("/")

STATUS_URL = (
    os.environ.get("SYNCTHING_STATUS_URL") or f"{_SYNCTHING_BASE_URL}/rest/db/status"
)
PAUSE_URL = (
    os.environ.get("SYNCTHING_PAUSE_URL") or f"{_SYNCTHING_BASE_URL}/rest/system/pause"
)
RESUME_URL = (
    os.environ.get("SYNCTHING_RESUME_URL") or f"{_SYNCTHING_BASE_URL}/rest/system/resume"
)


@dataclass
class FolderStatus:
    folder_id: str
    state: str
    percent: float
    global_bytes: int
    in_sync_bytes: int


class _StateTracker:
    def __init__(self) -> None:
        self._states: Dict[str, str] = {}
        self._errors: Dict[str, str] = {}

    def register_status(self, status: FolderStatus) -> Optional[str]:
        previous = self._states.get(status.folder_id)
        self._states[status.folder_id] = status.state
        self._errors.pop(status.folder_id, None)

        if previous == status.state:
            return None
        if status.state != "inSync":
            return "degraded"
        if previous and previous != "inSync":
            return "recovered"
        return None

    def register_error(self, folder_id: str, error: Exception) -> bool:
        message = str(error)
        previous = self._errors.get(folder_id)
        if previous == message:
            return False
        self._errors[folder_id] = message
        self._states.pop(folder_id, None)
        return True

    def get_snapshot(self) -> Dict[str, Dict[str, object]]:
        snapshot: Dict[str, Dict[str, object]] = {}
        for folder_id, state in self._states.items():
            snapshot[folder_id] = {"state": state, "error": None}
        for folder_id, message in self._errors.items():
            snapshot.setdefault(folder_id, {"state": "unknown", "error": None})[
                "error"
            ] = message
        return snapshot


class TelegramNotifier:
    def __init__(self) -> None:
        self._token = TELEGRAM_BOT_TOKEN
        self._chat_ids = TELEGRAM_CHAT_IDS
        self._allowed_user_ids = TELEGRAM_ALLOWED_USER_IDS
        self._offset = 0
        if self.enabled:
            self._prime_offset()

    @property
    def enabled(self) -> bool:
        return bool(self._token and self._chat_ids)

    def send_async(self, text: str, chat_id: Optional[str] = None) -> None:
        if not self.enabled:
            return
        targets = [chat_id] if chat_id else self._chat_ids
        for target in targets:
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            payload = {"chat_id": target, "text": text}
            _executor.submit(self._post, url, payload)

    @staticmethod
    def _post(url: str, payload: Dict[str, str]) -> None:
        try:
            requests.post(url, data=payload, timeout=10)
        except Exception:
            pass

    def _prime_offset(self) -> None:
        url = f"https://api.telegram.org/bot{self._token}/getUpdates"
        try:
            response = requests.get(url, params={"timeout": 0}, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = data.get("result") or []
            if results:
                self._offset = max(item.get("update_id", 0) for item in results)
        except Exception:
            self._offset = 0

    @dataclass
    class Command:
        chat_id: str
        user_id: Optional[str]
        text: str
        message_id: int

    def poll_commands(self) -> List["TelegramNotifier.Command"]:
        if not self.enabled:
            return []
        url = f"https://api.telegram.org/bot{self._token}/getUpdates"
        params: Dict[str, object] = {"timeout": 0}
        if self._offset:
            params["offset"] = self._offset + 1
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        commands: List[TelegramNotifier.Command] = []
        for update in data.get("result", []):
            update_id = update.get("update_id", 0)
            self._offset = max(self._offset, update_id)
            message = update.get("message") or update.get("channel_post")
            if not message:
                continue
            text = (message.get("text") or "").strip()
            if not text.startswith("/"):
                continue
            chat = message.get("chat") or {}
            chat_id = str(chat.get("id", ""))
            user = message.get("from") or {}
            user_id = user.get("id")
            commands.append(
                TelegramNotifier.Command(
                    chat_id=chat_id,
                    user_id=str(user_id) if user_id is not None else None,
                    text=text,
                    message_id=message.get("message_id", 0),
                )
            )
        return commands

    def is_authorized_user(self, user_id: Optional[str]) -> bool:
        if not self._allowed_user_ids:
            return True
        if user_id is None:
            return False
        return user_id in self._allowed_user_ids


class EmailNotifier:
    def __init__(self) -> None:
        self._host = SMTP_HOST
        self._port = SMTP_PORT
        self._username = SMTP_USERNAME
        self._password = SMTP_PASSWORD
        self._sender = EMAIL_SENDER
        self._recipients = EMAIL_RECIPIENTS

    @property
    def enabled(self) -> bool:
        return all([self._host, self._sender, self._recipients])

    def send_async(self, subject: str, body: str) -> None:
        if not self.enabled:
            return
        _executor.submit(self._send, subject, body)

    def _send(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._sender
        message["To"] = ", ".join(self._recipients)
        message.set_content(body)

        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as client:
                client.starttls()
                if self._username and self._password:
                    client.login(self._username, self._password)
                client.send_message(message)
        except Exception:
            pass


_tracker = _StateTracker()
_telegram = TelegramNotifier()
_email = EmailNotifier()


def _log(msg: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}\n"
    print(line, end="")
    log_path = Path(LOG_PATH)
    parent = log_path.parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(line)


def _check_folder(folder_id: str) -> Tuple[Optional[FolderStatus], Optional[Exception]]:
    try:
        response = requests.get(
            STATUS_URL,
            headers=_headers,
            timeout=10,
            params={"folder": folder_id},
        )
        response.raise_for_status()
        data = response.json()
        global_bytes = data.get("globalBytes", 0)
        in_sync = data.get("inSyncBytes", 0)
        percent = (in_sync / global_bytes * 100) if global_bytes else 100.0
        state = data.get("state", "unknown")
        status = FolderStatus(
            folder_id=folder_id,
            state=state,
            percent=percent,
            global_bytes=global_bytes,
            in_sync_bytes=in_sync,
        )
        _log(f"{folder_id}: {percent:.1f}% synced ({state})")
        return status, None
    except Exception as exc:
        _log(f"{folder_id}: ERROR {exc}")
        return None, exc


def _iter_folder_ids() -> Iterable[str]:
    for entry in FOLDER_IDS.split(","):
        entry = entry.strip()
        if entry:
            yield entry


def _emit_telemetry(step: str, level: str, payload: Dict[str, object]) -> None:
    if telemetry_emit is None:
        return
    try:
        telemetry_emit(
            event_type="syncthing_monitor",
            trace_id=f"syncthing-{payload.get('folder_id', 'unknown')}",
            step=step,
            payload=payload,
            level=level,
        )
    except Exception:
        pass


def _notify_degraded(status: FolderStatus) -> None:
    message = (
        f"Syncthing folder {status.folder_id} is not in sync.\n"
        f"State: {status.state}\n"
        f"Progress: {status.percent:.1f}% ({status.in_sync_bytes}/{status.global_bytes} bytes)"
    )
    _telegram.send_async(message)
    _email.send_async(
        subject=f"[Syncthing] Folder {status.folder_id} degraded ({status.state})",
        body=message,
    )
    _emit_telemetry(
        step="state_degraded",
        level="warning",
        payload={
            "folder_id": status.folder_id,
            "state": status.state,
            "percent": status.percent,
            "global_bytes": status.global_bytes,
            "in_sync_bytes": status.in_sync_bytes,
        },
    )


def _notify_recovered(status: FolderStatus) -> None:
    message = (
        f"Syncthing folder {status.folder_id} has recovered.\n"
        f"State: {status.state}\n"
        f"Progress: {status.percent:.1f}% ({status.in_sync_bytes}/{status.global_bytes} bytes)"
    )
    _telegram.send_async(message)
    _email.send_async(
        subject=f"[Syncthing] Folder {status.folder_id} recovered",
        body=message,
    )
    _emit_telemetry(
        step="state_recovered",
        level="info",
        payload={
            "folder_id": status.folder_id,
            "state": status.state,
            "percent": status.percent,
            "global_bytes": status.global_bytes,
            "in_sync_bytes": status.in_sync_bytes,
        },
    )


def _notify_error(folder_id: str, error: Exception) -> None:
    message = f"Syncthing folder {folder_id} check failed.\nError: {error}"
    _telegram.send_async(message)
    _email.send_async(
        subject=f"[Syncthing] Folder {folder_id} error",
        body=message,
    )
    _emit_telemetry(
        step="state_error",
        level="error",
        payload={
            "folder_id": folder_id,
            "error": str(error),
        },
    )


def _pause_folder(folder_id: str) -> None:
    response = requests.post(
        PAUSE_URL,
        headers=_headers,
        timeout=10,
        params={"folder": folder_id},
    )
    response.raise_for_status()


def _resume_folder(folder_id: str) -> None:
    response = requests.post(
        RESUME_URL,
        headers=_headers,
        timeout=10,
        params={"folder": folder_id},
    )
    response.raise_for_status()


def _process_telegram_commands() -> None:
    if not _telegram.enabled:
        return
    commands = _telegram.poll_commands()
    for command in commands:
        if command.chat_id not in TELEGRAM_CHAT_IDS:
            continue
        if not _telegram.is_authorized_user(command.user_id):
            _telegram.send_async(
                "Not authorized to control Syncthing from this chat.",
                chat_id=command.chat_id,
            )
            continue
        _handle_command(command)


def _handle_command(command: TelegramNotifier.Command) -> None:
    parts = command.text.split()
    if not parts:
        return
    cmd = parts[0].split("@", 1)[0].lower()

    if cmd == "/list":
        snapshot = _tracker.get_snapshot()
        if not snapshot:
            body = "No folder data yet. Monitoring will populate this shortly."
        else:
            lines = []
            for folder_id in sorted(snapshot):
                entry = snapshot[folder_id]
                state = entry.get("state", "unknown")
                error = entry.get("error")
                lines.append(
                    f"{folder_id}: {state}"
                    + (f" (error: {error})" if error else "")
                )
            body = "Monitored folders:\n" + "\n".join(lines)
        _telegram.send_async(body, chat_id=command.chat_id)
        return

    if cmd == "/pause":
        if len(parts) < 2:
            _telegram.send_async(
                "Usage: /pause <folder_id>",
                chat_id=command.chat_id,
            )
            return
        folder_id = parts[1]
        try:
            _pause_folder(folder_id)
        except Exception as exc:
            _log(f"pause command failed for {folder_id}: {exc}")
            _telegram.send_async(
                f"Failed to pause {folder_id}: {exc}",
                chat_id=command.chat_id,
            )
            return
        _log(f"Paused Syncthing folder {folder_id} via Telegram command.")
        _telegram.send_async(
            f"Folder {folder_id} paused.",
            chat_id=command.chat_id,
        )
        return

    if cmd == "/resume":
        if len(parts) < 2:
            _telegram.send_async(
                "Usage: /resume <folder_id>",
                chat_id=command.chat_id,
            )
            return
        folder_id = parts[1]
        try:
            _resume_folder(folder_id)
        except Exception as exc:
            _log(f"resume command failed for {folder_id}: {exc}")
            _telegram.send_async(
                f"Failed to resume {folder_id}: {exc}",
                chat_id=command.chat_id,
            )
            return
        _log(f"Resumed Syncthing folder {folder_id} via Telegram command.")
        _telegram.send_async(
            f"Folder {folder_id} resumed.",
            chat_id=command.chat_id,
        )
        return

    # Unknown command
    _telegram.send_async(
        "Unknown command. Try /pause <folder_id> or /resume <folder_id>.",
        chat_id=command.chat_id,
    )


def main() -> int:
    _log("=== Syncthing continuous monitor started ===")
    while True:
        for folder_id in _iter_folder_ids():
            status, error = _check_folder(folder_id)
            if error:
                if _tracker.register_error(folder_id, error):
                    _notify_error(folder_id, error)
                continue
            if not status:
                continue
            transition = _tracker.register_status(status)
            if transition == "degraded":
                _notify_degraded(status)
            elif transition == "recovered":
                _notify_recovered(status)
        _process_telegram_commands()
        time.sleep(max(1, INTERVAL))


if __name__ == "__main__":
    raise SystemExit(main())
