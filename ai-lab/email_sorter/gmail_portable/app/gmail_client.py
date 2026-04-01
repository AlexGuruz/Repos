from __future__ import annotations

import base64
import json
import logging
import os
import unicodedata
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow


def _adapter_load_config() -> Any | None:
    """
    Optional adapter config (OpenAI/agents). Email sorter and other tools only need
    Gmail OAuth paths from env / legacy files — avoid hard dependency on app.config.
    """
    try:
        from app.config import load_config as _lc

        return _lc()
    except Exception:
        return None


LOGGER = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
_GMAIL_SERVICE: Resource | None = None
_LABEL_NAME_TO_ID: dict[str, str] = {}

_ADAPTER_ROOT = Path(__file__).resolve().parent.parent
_LEGACY_CREDENTIALS_FILE = _ADAPTER_ROOT / "credentials.json"
_LEGACY_TOKEN_FILE = _ADAPTER_ROOT / "token.json"


def _dedupe_keep_order(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        s = str(p)
        if s in seen:
            continue
        seen.add(s)
        out.append(p)
    return out


def _resolve_env_path(value: str | None) -> Path | None:
    raw = (value or "").strip()
    if not raw:
        return None
    p = Path(raw)
    # If a relative path is provided, resolve relative to the adapter root.
    # Recommended usage is absolute paths.
    if not p.is_absolute():
        p = _ADAPTER_ROOT / p
    return p


def _candidate_credentials_paths(config: Any | None = None) -> list[Path]:
    candidates: list[Path] = []

    env_credentials = _resolve_env_path(os.getenv("GOOGLE_CREDENTIALS_FILE"))
    if env_credentials:
        candidates.append(env_credentials)

    if config is not None:
        try:
            candidates.append(Path(config.google_credentials_file))
        except Exception:
            pass

    candidates.append(_LEGACY_CREDENTIALS_FILE)
    return _dedupe_keep_order(candidates)


def _candidate_token_paths(config: Any | None = None) -> list[Path]:
    candidates: list[Path] = []

    env_token = _resolve_env_path(os.getenv("GOOGLE_TOKEN_FILE"))
    if env_token:
        candidates.append(env_token)

    if config is not None:
        try:
            candidates.append(Path(config.google_token_file))
        except Exception:
            pass

    candidates.append(_LEGACY_TOKEN_FILE)
    return _dedupe_keep_order(candidates)


def preflight_gmail_auth() -> dict[str, Any]:
    """
    File-only preflight to fail early with clear credential paths.

    Does NOT perform OAuth flow or call Gmail APIs.
    """
    config = _adapter_load_config()
    credential_candidates = _candidate_credentials_paths(config=config)
    token_candidates = _candidate_token_paths(config=config)

    credentials_found = [str(p) for p in credential_candidates if p.exists()]
    token_found = [str(p) for p in token_candidates if p.exists()]

    # First-run needs OAuth client secrets (credentials.json).
    # If a token.json exists, Gmail auth may still work without client secrets.
    ok = bool(credentials_found) or bool(token_found)

    return {
        "ok": ok,
        "credential_candidates": [str(p) for p in credential_candidates],
        "token_candidates": [str(p) for p in token_candidates],
        "credentials_found": credentials_found,
        "token_found": token_found,
        "credentials_missing": [] if credentials_found else [str(p) for p in credential_candidates],
        "token_missing": [] if token_found else [str(p) for p in token_candidates],
    }


def get_gmail_service() -> Resource:
    global _GMAIL_SERVICE
    if _GMAIL_SERVICE is not None:
        return _GMAIL_SERVICE

    config = _adapter_load_config()
    creds: Credentials | None = None
    credential_candidates = _candidate_credentials_paths(config=config)
    token_candidates = _candidate_token_paths(config=config)

    # Where token.json will be written if OAuth flow is required.
    if token_candidates:
        token_file = token_candidates[0]
    elif config is not None:
        token_file = Path(config.google_token_file)
    else:
        token_file = _LEGACY_TOKEN_FILE

    credentials_file = None
    for p in credential_candidates:
        if p.exists():
            credentials_file = p
            break

    # Prefer the first existing token.json among candidates.
    token_file_loaded: Path | None = None
    for candidate_token in token_candidates:
        if not candidate_token.exists():
            continue
        try:
            creds = Credentials.from_authorized_user_file(str(candidate_token), SCOPES)
            token_file_loaded = candidate_token
            break
        except Exception:
            LOGGER.warning("Ignoring invalid token file and starting OAuth flow again: %s", candidate_token)
            try:
                candidate_token.unlink(missing_ok=True)
            except Exception:
                pass
            creds = None

    # If token file exists but invalid, we may fall back to OAuth.
    # If creds are loaded and valid/refreshable, credentials.json may not be required.

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if credentials_file is None or not Path(credentials_file).exists():
                missing = [str(p) for p in credential_candidates if not p.exists()]
                attempted = [str(p) for p in credential_candidates]
                raise FileNotFoundError(
                    "Missing Gmail OAuth credentials.json for Gmail API.\n"
                    f"Attempted credential files (in order): {attempted}\n"
                    f"Missing: {missing}\n\n"
                    "Fix: provide `GOOGLE_CREDENTIALS_FILE`/`GOOGLE_TOKEN_FILE` env vars "
                    "or place credentials.json/token.json in the legacy adapter folder:\n"
                    f"- {str(_LEGACY_CREDENTIALS_FILE)}\n"
                    f"- {str(_LEGACY_TOKEN_FILE)}\n"
                )

            try:
                with Path(credentials_file).open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not (data.get("installed") or data.get("web")):
                    raise ValueError(
                        "credentials.json must contain an OAuth client config with 'installed' or 'web'."
                    )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "credentials.json is empty or invalid JSON. Download OAuth client JSON from "
                    "Google Cloud Console and paste it into credentials.json."
                ) from exc

            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    _GMAIL_SERVICE = build("gmail", "v1", credentials=creds)
    return _GMAIL_SERVICE


def _decode_base64_url(data: str | None) -> str:
    if not data:
        return ""

    padded = data + "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return decoded.decode("utf-8", errors="replace")


def _extract_text_from_payload(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""

    plain_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")

        if body_data:
            decoded = _decode_base64_url(body_data).strip()
            if decoded:
                if mime_type == "text/plain":
                    plain_parts.append(decoded)
                elif mime_type == "text/html":
                    html_parts.append(decoded)
                elif not part.get("parts"):
                    plain_parts.append(decoded)

        for child in part.get("parts", []) or []:
            if isinstance(child, dict):
                walk(child)

    walk(payload)

    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        return "\n".join(html_parts).strip()
    return ""


def _get_header_value(headers: list[dict[str, str]], key: str) -> str:
    key_lower = key.lower()
    for header in headers:
        if header.get("name", "").lower() == key_lower:
            return header.get("value", "")
    return ""


def get_email_by_id(message_id: str) -> dict[str, str]:
    service = get_gmail_service()
    raw_message = service.users().messages().get(userId="me", id=message_id, format="full").execute()

    payload = raw_message.get("payload", {})
    headers = payload.get("headers", [])

    return {
        "id": raw_message.get("id", ""),
        "threadId": raw_message.get("threadId", ""),
        "from": _get_header_value(headers, "From"),
        "subject": _get_header_value(headers, "Subject"),
        "messageIdHeader": _get_header_value(headers, "Message-ID"),
        "snippet": raw_message.get("snippet", ""),
        "body": _extract_text_from_payload(payload),
    }


def fetch_unread_emails(
    max_results: int = 10,
    exclude_label_name: str | None = None,
    exclude_label_names: list[str] | None = None,
    include_read_inbox: bool = False,
    subject_contains: str | None = None,
    max_age_hours: int = 0,
) -> list[dict[str, str]]:
    service = get_gmail_service()
    try:
        list_kwargs: dict[str, Any] = {
            "userId": "me",
            "labelIds": ["INBOX"] if include_read_inbox else ["INBOX", "UNREAD"],
            "maxResults": max_results,
        }
        query_parts: list[str] = []
        exclude_names: list[str] = []
        if exclude_label_name and exclude_label_name.strip():
            exclude_names.append(exclude_label_name.strip())
        for name in exclude_label_names or []:
            if name and name.strip():
                exclude_names.append(name.strip())

        if exclude_names:
            resolved_names: list[str] = []
            for name in exclude_names:
                resolved_names.append(resolve_existing_label_name(name) or name)
            sanitized_names = [name.replace('"', "") for name in resolved_names]
            query_parts.extend(f'-label:"{name}"' for name in sanitized_names)

        if subject_contains and subject_contains.strip():
            sanitized_subject = subject_contains.strip().replace('"', "")
            query_parts.append(f'subject:"{sanitized_subject}"')

        if max_age_hours > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            query_parts.append(f"after:{int(cutoff.timestamp())}")

        if query_parts:
            list_kwargs["q"] = " ".join(query_parts)

        result = service.users().messages().list(**list_kwargs).execute()
        messages = result.get("messages", [])

        emails: list[dict[str, str]] = []
        for message in messages:
            message_id = message.get("id")
            if not message_id:
                continue
            email = get_email_by_id(message_id)
            emails.append(
                {
                    "id": email.get("id", ""),
                    "threadId": email.get("threadId", ""),
                    "from": email.get("from", ""),
                    "subject": email.get("subject", ""),
                    "snippet": email.get("snippet", ""),
                    "body": email.get("body", ""),
                }
            )

        mode = "inbox+read" if include_read_inbox else "unread-only"
        age_filter = f"{max_age_hours}h" if max_age_hours > 0 else "disabled"
        LOGGER.info("Fetched %s inbox email(s) | mode=%s | age_filter=%s.", len(emails), mode, age_filter)
        return emails
    except HttpError as exc:
        LOGGER.exception("Failed to fetch unread emails from Gmail API.")
        raise RuntimeError(f"Gmail API error while fetching unread emails: {exc}") from exc


def save_draft_reply(message_id: str, reply_text: str) -> str:
    service = get_gmail_service()
    try:
        original = get_email_by_id(message_id)

        to_header = original.get("from", "")
        to_address = parseaddr(to_header)[1] or to_header
        subject = original.get("subject", "").strip()
        message_id_header = original.get("messageIdHeader", "").strip()

        if subject.lower().startswith("re:"):
            reply_subject = subject
        else:
            reply_subject = f"Re: {subject}" if subject else "Re:"

        message = EmailMessage()
        message["To"] = to_address
        message["Subject"] = reply_subject
        if message_id_header:
            message["In-Reply-To"] = message_id_header
            message["References"] = message_id_header
        message.set_content(reply_text.strip())

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        draft_body = {
            "message": {
                "raw": encoded_message,
                "threadId": original.get("threadId", ""),
            }
        }

        draft = service.users().drafts().create(userId="me", body=draft_body).execute()
        draft_id = draft.get("id", "")
        LOGGER.info("Created draft %s for message %s.", draft_id, message_id)
        return draft_id
    except HttpError as exc:
        LOGGER.exception("Failed to create Gmail draft for message %s.", message_id)
        raise RuntimeError(f"Gmail API error while creating draft: {exc}") from exc


def _refresh_label_cache() -> None:
    service = get_gmail_service()
    labels: dict[str, str] = {}
    response = service.users().labels().list(userId="me").execute()
    for label in response.get("labels", []):
        name = label.get("name", "")
        label_id = label.get("id", "")
        if name and label_id:
            labels[name] = label_id

    _LABEL_NAME_TO_ID.clear()
    _LABEL_NAME_TO_ID.update(labels)


def _normalize_label_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    cleaned_chars: list[str] = []
    for ch in normalized:
        if ch.isalnum() or ch in {" ", "&", "/", "-", "_"}:
            cleaned_chars.append(ch.lower())
    return " ".join("".join(cleaned_chars).split())


def resolve_existing_label_name(label_name: str) -> str | None:
    if not label_name.strip():
        return None
    if not _LABEL_NAME_TO_ID:
        _refresh_label_cache()
    if label_name in _LABEL_NAME_TO_ID:
        return label_name

    target = _normalize_label_name(label_name)
    for existing_name in _LABEL_NAME_TO_ID:
        existing_norm = _normalize_label_name(existing_name)
        if existing_norm == target or existing_norm.endswith(target):
            return existing_name
    return None


def get_or_create_label_id(label_name: str) -> str:
    if not label_name.strip():
        raise ValueError("Label name cannot be empty.")

    existing = resolve_existing_label_name(label_name)
    if existing and existing in _LABEL_NAME_TO_ID:
        return _LABEL_NAME_TO_ID[existing]

    _refresh_label_cache()
    existing = resolve_existing_label_name(label_name)
    if existing and existing in _LABEL_NAME_TO_ID:
        return _LABEL_NAME_TO_ID[existing]

    service = get_gmail_service()
    body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }

    try:
        created = service.users().labels().create(userId="me", body=body).execute()
        created_id = created.get("id", "")
        if not created_id:
            raise RuntimeError(f"Label create returned no id for: {label_name}")
        _LABEL_NAME_TO_ID[label_name] = created_id
        LOGGER.info("Created Gmail label: %s", label_name)
        return created_id
    except HttpError as exc:
        # Handle race condition where label may have been created by another run.
        LOGGER.warning("Create label failed for '%s', refreshing cache: %s", label_name, exc)
        _refresh_label_cache()
        cached = _LABEL_NAME_TO_ID.get(label_name)
        if cached:
            return cached
        raise RuntimeError(f"Failed to create Gmail label '{label_name}': {exc}") from exc


def apply_action_label(
    message_id: str,
    target_label_name: str,
    all_action_label_names: list[str],
) -> None:
    service = get_gmail_service()
    target_id = get_or_create_label_id(target_label_name)

    remove_ids: list[str] = []
    for label_name in all_action_label_names:
        if label_name == target_label_name:
            continue
        label_id = get_or_create_label_id(label_name)
        remove_ids.append(label_id)

    body = {"addLabelIds": [target_id], "removeLabelIds": remove_ids}
    try:
        service.users().messages().modify(userId="me", id=message_id, body=body).execute()
        LOGGER.info("Applied label '%s' to message %s.", target_label_name, message_id)
    except HttpError as exc:
        raise RuntimeError(
            f"Gmail API error while applying label '{target_label_name}' to {message_id}: {exc}"
        ) from exc


def _label_id_to_name_map() -> dict[str, str]:
    if not _LABEL_NAME_TO_ID:
        _refresh_label_cache()
    return {label_id: label_name for label_name, label_id in _LABEL_NAME_TO_ID.items()}


def get_message_label_names(message_id: str) -> set[str]:
    service = get_gmail_service()
    message = service.users().messages().get(userId="me", id=message_id, format="metadata").execute()
    label_ids = message.get("labelIds", [])
    id_to_name = _label_id_to_name_map()
    return {id_to_name.get(label_id, label_id) for label_id in label_ids}


def message_has_label(message_id: str, label_name: str) -> bool:
    if not label_name.strip():
        return False
    names = get_message_label_names(message_id)
    return label_name in names


def add_label_to_message(message_id: str, label_name: str) -> None:
    service = get_gmail_service()
    label_id = get_or_create_label_id(label_name)
    body = {"addLabelIds": [label_id], "removeLabelIds": []}
    try:
        service.users().messages().modify(userId="me", id=message_id, body=body).execute()
        LOGGER.info("Added label '%s' to message %s.", label_name, message_id)
    except HttpError as exc:
        raise RuntimeError(
            f"Gmail API error while adding label '{label_name}' to {message_id}: {exc}"
        ) from exc


def remove_label_from_message(message_id: str, label_name: str) -> None:
    service = get_gmail_service()
    existing_name = resolve_existing_label_name(label_name)
    if not existing_name:
        return
    label_id = _LABEL_NAME_TO_ID.get(existing_name)
    if not label_id:
        return

    body = {"addLabelIds": [], "removeLabelIds": [label_id]}
    try:
        service.users().messages().modify(userId="me", id=message_id, body=body).execute()
        LOGGER.info("Removed label '%s' from message %s.", existing_name, message_id)
    except HttpError as exc:
        raise RuntimeError(
            f"Gmail API error while removing label '{existing_name}' from {message_id}: {exc}"
        ) from exc


def delete_label_if_exists(label_name: str) -> bool:
    service = get_gmail_service()
    existing_name = resolve_existing_label_name(label_name)
    if not existing_name:
        return False
    label_id = _LABEL_NAME_TO_ID.get(existing_name)
    if not label_id:
        return False

    try:
        service.users().labels().delete(userId="me", id=label_id).execute()
        LOGGER.info("Deleted Gmail label: %s", existing_name)
        _LABEL_NAME_TO_ID.pop(existing_name, None)
        return True
    except HttpError as exc:
        raise RuntimeError(f"Gmail API error while deleting label '{existing_name}': {exc}") from exc
