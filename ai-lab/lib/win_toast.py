"""Windows desktop toast notifications (BurntToast or PowerShell fallback)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path


def _ai_lab_root() -> Path:
    return Path(__file__).resolve().parents[1]


def show_windows_toast(
    title: str,
    message: str,
    *,
    timeout_sec: float = 30.0,
) -> dict:
    """
    Show a desktop toast on the current Windows machine.
    Prefers BurntToast module; falls back to a balloon/notify script.
    """
    if platform.system() != "Windows":
        raise RuntimeError("Windows toast only supported on Windows")

    title = (title or "Email").strip()[:120]
    message = (message or "").strip()[:800]
    script = _ai_lab_root() / "scripts" / "show_email_toast.ps1"
    if not script.exists():
        raise FileNotFoundError(f"Missing toast script: {script}")

    # Pass text via temp files to avoid quoting / length issues.
    with tempfile.TemporaryDirectory(prefix="email_toast_") as tmp:
        tpath = Path(tmp) / "title.txt"
        mpath = Path(tmp) / "body.txt"
        tpath.write_text(title, encoding="utf-8")
        mpath.write_text(message, encoding="utf-8")
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-TitleFile",
            str(tpath),
            "-BodyFile",
            str(mpath),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def notify_acheron_toast(
    title: str,
    message: str,
    *,
    ssh_target: str | None = None,
    timeout_sec: float = 45.0,
) -> dict:
    """
    Show toast on Acheron.

    - If this host is already Acheron (or ACHERON_TOAST_LOCAL=1), show locally.
    - Else SSH to ACHERON_SSH (default zacle@acheron) and run show_email_toast.ps1.
    """
    force_local = (os.environ.get("ACHERON_TOAST_LOCAL") or "").strip() in {"1", "true", "yes"}
    hostname = platform.node().strip().lower()
    if force_local or hostname in {"acheron", "newrig"}:
        return show_windows_toast(title, message, timeout_sec=timeout_sec)

    target = (ssh_target or os.environ.get("ACHERON_SSH") or "zacle@acheron").strip()
    script_remote = (
        os.environ.get("ACHERON_TOAST_SCRIPT")
        or r"E:\Repos\ai-lab\scripts\show_email_toast.ps1"
    )
    # Write message locally then scp is heavy; pass via stdin-encoded env on remote.
    # Prefer a short remote powershell that writes temp files from base64.
    import base64

    title_b64 = base64.b64encode((title or "").encode("utf-8")).decode("ascii")
    body_b64 = base64.b64encode((message or "").encode("utf-8")).decode("ascii")
    remote_ps = (
        f"$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{title_b64}')); "
        f"$b=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{body_b64}')); "
        f"$td=Join-Path $env:TEMP ('email_toast_'+[guid]::NewGuid().ToString()); "
        f"New-Item -ItemType Directory -Force -Path $td | Out-Null; "
        f"$tf=Join-Path $td 'title.txt'; $bf=Join-Path $td 'body.txt'; "
        f"Set-Content -LiteralPath $tf -Value $t -Encoding UTF8; "
        f"Set-Content -LiteralPath $bf -Value $b -Encoding UTF8; "
        f"& powershell -NoProfile -ExecutionPolicy Bypass -File '{script_remote}' "
        f"-TitleFile $tf -BodyFile $bf; "
        f"Remove-Item -LiteralPath $td -Recurse -Force -ErrorAction SilentlyContinue"
    )
    ssh = shutil.which("ssh") or "ssh"
    cmd = [
        ssh,
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        target,
        "powershell",
        "-NoProfile",
        "-Command",
        remote_ps,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "via": f"ssh:{target}",
    }
