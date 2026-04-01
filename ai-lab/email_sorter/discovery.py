from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    # E:/Repos/ai-lab/email_sorter/discovery.py -> E:/Repos/ai-lab
    return Path(__file__).resolve().parents[1]


def _normalize_label_name(value: str) -> str:
    """
    Normalize label names for duplicate detection.

    Mirrors the normalization strategy in:
    Ai/Email-Inbox-Agent---Doo-Made/app/gmail_client.py
    """
    if value is None:
        return ""
    v = str(value)
    # Keep it dependency-free: strip down to lowercase alnum + a small punctuation set.
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789 ")
    # Expand with common label characters observed in the email agent.
    extra = set("&/ - _")
    out_chars: list[str] = []
    for ch in v.lower():
        if ch in allowed or ch in extra or ch.isspace():
            out_chars.append(ch)
        # else: drop
    # Collapse whitespace
    return " ".join("".join(out_chars).split())


def _required_canonical_labels() -> list[str]:
    # Canonical label names requested by the user spec.
    return [
        "Permits",
        "MYDOT",
        "PROGRESSIVE COMMERCIAL INSURANCE",
        "Driver Credentials / Documents",
        "Needs Review",
    ]


def _load_email_agent_gmail_client() -> Any:
    """
    Load the existing Gmail adapter from:
      Ai/Email-Inbox-Agent---Doo-Made/app/gmail_client.py

    We import lazily so unit tests that don't touch Gmail won't fail if google deps
    are missing in the environment.
    """
    root = _repo_root()
    agent_root = root / "Ai" / "Email-Inbox-Agent---Doo-Made"
    # The adapter expects the "app" package to be importable.
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from app import gmail_client as _gmail_client  # type: ignore

    return _gmail_client


def discover_labels() -> dict[str, Any]:
    """
    Return a JSON-serializable dict with:
    - all_labels: list of labels (name/id/message counts when available)
    - duplicates: normalized-name -> candidate list
    - required_missing: list of missing canonical label names
    """
    gmail_client = _load_email_agent_gmail_client()
    try:
        service = gmail_client.get_gmail_service()
    except FileNotFoundError as exc:
        msg = (
            "Missing Gmail OAuth credentials for Gmail API access.\n"
            f"{exc}\n\n"
            "Fix: create `credentials.json` in `Ai/Email-Inbox-Agent---Doo-Made/` "
            "or set env vars:\n"
            "- `GOOGLE_CREDENTIALS_FILE` (absolute path to OAuth client JSON)\n"
            "- `GOOGLE_TOKEN_FILE` (absolute path to stored token.json)\n"
        )
        print(msg)
        raise

    # labels.list returns label metadata; fields vary by Gmail API version, but we
    # typically get messagesTotal/messagesUnread.
    resp = service.users().labels().list(userId="me").execute()
    labels = resp.get("labels", []) or []

    all_labels: list[dict[str, Any]] = []
    normalized_map: dict[str, list[str]] = {}
    for lbl in labels:
        name = lbl.get("name", "") or ""
        if not name:
            continue
        norm = _normalize_label_name(name)
        normalized_map.setdefault(norm, []).append(name)

        # Try multiple possible key spellings.
        total = lbl.get("messagesTotal")
        if total is None:
            total = lbl.get("messages_total")
        unread = lbl.get("messagesUnread")
        if unread is None:
            unread = lbl.get("messages_unread")

        all_labels.append(
            {
                "name": name,
                "id": lbl.get("id", ""),
                "messagesTotal": total,
                "messagesUnread": unread,
            }
        )

    # duplicates: only keep normalized groups with more than one candidate.
    duplicates = {k: sorted(v) for k, v in normalized_map.items() if len(v) > 1}

    # Required canonical labels must exist, but we only *recommend* creating them here.
    required = _required_canonical_labels()
    existing_norms = {_normalize_label_name(x.get("name", "")) for x in all_labels}
    required_missing = [r for r in required if _normalize_label_name(r) not in existing_norms]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_labels": sorted(all_labels, key=lambda x: (x.get("name") or "").lower()),
        "duplicates": dict(sorted(duplicates.items(), key=lambda kv: kv[0])),
        "required_missing": required_missing,
    }


def _render_inventory_md(data: dict[str, Any]) -> str:
    required = _required_canonical_labels()

    lines: list[str] = []
    lines.append("# Gmail Label Inventory")
    lines.append("")
    lines.append(f"- Generated at: `{data.get('generated_at', '')}`")
    lines.append(f"- Total labels: `{len(data.get('all_labels') or [])}`")
    lines.append("")

    lines.append("## Labels (name/id)")
    lines.append("")
    lines.append("| Label | ID | messagesTotal | messagesUnread |")
    lines.append("|---|---:|---:|---:|")
    for lbl in data.get("all_labels", []) or []:
        name = str(lbl.get("name", ""))
        lid = str(lbl.get("id", ""))
        total = lbl.get("messagesTotal")
        unread = lbl.get("messagesUnread")
        total_s = "" if total is None else str(total)
        unread_s = "" if unread is None else str(unread)
        lines.append(f"| {name} | {lid} | {total_s} | {unread_s} |")
    lines.append("")

    lines.append("## Duplicate candidates (normalized)")
    lines.append("")
    dup = data.get("duplicates") or {}
    if not dup:
        lines.append("_No duplicates found by normalization._")
    else:
        for norm, names in dup.items():
            lines.append(f"- `{norm}`: {', '.join(names)}")
    lines.append("")

    lines.append("## Required label recommendations")
    lines.append("")
    missing = data.get("required_missing") or []
    if not missing:
        lines.append("_All required canonical labels are present._")
    else:
        lines.append("Missing required canonical labels:")
        for m in missing:
            lines.append(f"- {m}")
    lines.append("")

    # Convenience mapping for user:
    lines.append("### Canonical categories (from user spec)")
    lines.append("")
    for r in required:
        if r == "Driver Credentials / Documents":
            lines.append(f"- `{r}` (parent label; sorter may add per-driver children)")
        else:
            lines.append(f"- `{r}`")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Gmail label discovery for the integrated email sorter.")
    parser.add_argument("--auth-check", action="store_true", help="Fail early if Gmail OAuth credentials/token are missing.")
    args = parser.parse_args()

    gmail_client = _load_email_agent_gmail_client()
    if args.auth_check:
        # File-only preflight; no Gmail API calls.
        preflight = {}
        if hasattr(gmail_client, "preflight_gmail_auth"):
            preflight = gmail_client.preflight_gmail_auth()  # type: ignore[attr-defined]
        else:
            raise SystemExit("gmail_client.preflight_gmail_auth() not found (adapter update required).")

        print(json.dumps(preflight, indent=2))
        if not preflight.get("ok"):
            raise SystemExit(2)
        return

    # Fail early before doing any mailbox work.
    if hasattr(gmail_client, "preflight_gmail_auth"):
        preflight = gmail_client.preflight_gmail_auth()  # type: ignore[attr-defined]
        if not preflight.get("ok"):
            raise SystemExit(
                "Gmail auth preflight failed (missing credentials/token). "
                + json.dumps(preflight, ensure_ascii=False)
            )

    inventory = discover_labels()
    out_path = _repo_root() / "docs" / "LABEL_INVENTORY.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render_inventory_md(inventory), encoding="utf-8")
    print(f"Wrote label inventory: {out_path}")

    # Also print a tiny JSON footer for automation.
    print(json.dumps({"missing_required": inventory.get("required_missing")}, indent=2))


if __name__ == "__main__":
    main()

