"""Email digest + draft proposal helpers."""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from .. import paths as pathmod
from ..approvals import submit_tool_proposal
from ..errors import EMAIL_ACCOUNT_NOT_FOUND, EMAIL_AUTH_UNAVAILABLE, OperatorError
from ..models import (
    ApprovalSubmissionResult,
    EmailAccountDigest,
    EmailDigestResult,
    EmailMessageView,
)
from ..settings import get_settings

_cache_lock = threading.RLock()

# Tool name for draft execution — must exist in scripts.json before live approve-exec.
DRAFT_TOOL_NAME = "operator_email_create_draft"


def _redact_from(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if "<" in v and ">" in v:
        # keep domain-ish tail only
        return "[redacted]"
    if "@" in v:
        local, _, domain = v.partition("@")
        return f"{local[:1]}***@{domain}"
    return v[:3] + "***" if len(v) > 3 else "***"


def _redact_snippet(value: str, limit: int = 80) -> str:
    text = " ".join((value or "").split())
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


def _load_cache() -> dict[str, Any]:
    path = pathmod.email_digest_cache_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(payload: dict[str, Any]) -> None:
    path = pathmod.email_digest_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _account_ids_from_config() -> list[str]:
    try:
        from email_sorter.accounts import load_account_specs

        return [s.account_id for s in load_account_specs()]
    except Exception:
        # Fallback known IDs from accounts.yaml (verified in audit)
        return ["jgdproperties", "jagadnursery", "nugzdispo"]


def fetch_unread_digest(
    account_ids: list[str] | None = None,
    *,
    limit_per_account: int = 20,
    cache_ttl_seconds: int | None = None,
    use_live: bool = True,
) -> EmailDigestResult:
    """
    Fetch unread digest.
    Live path imports company email helpers; unit tests monkeypatch or set use_live=False.
    """
    settings = get_settings()
    ttl = settings.email_digest_cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
    ids = account_ids or _account_ids_from_config()
    known = set(_account_ids_from_config())
    for aid in ids:
        if aid not in known:
            raise OperatorError(EMAIL_ACCOUNT_NOT_FOUND, f"Unknown account_id: {aid}")

    cache_key = f"{','.join(ids)}|{limit_per_account}"
    now = time.time()
    with _cache_lock:
        cache = _load_cache()
        hit = cache.get(cache_key)
        if isinstance(hit, dict) and now - float(hit.get("ts", 0)) <= ttl:
            body = hit.get("result")
            if isinstance(body, dict):
                return EmailDigestResult(
                    ok=True,
                    source="gmail_api_cache",
                    freshness="fresh",
                    generated_at=body.get("generated_at"),
                    accounts=[],  # filled below from serialized
                    total_unread=int(body.get("total_unread", 0)),
                    cache_hit=True,
                    warnings=list(body.get("warnings") or []),
                )

    if not use_live:
        return EmailDigestResult(
            ok=True,
            source="test_stub",
            freshness="fresh",
            accounts=[],
            total_unread=0,
            cache_hit=False,
            warnings=["use_live=False"],
        )

    try:
        from email_sorter.accounts import get_account_gmail_service, load_account_specs
        from email_sorter.company_triage import EmailMessage, classify_company_email
    except ImportError as exc:
        raise OperatorError(EMAIL_AUTH_UNAVAILABLE, f"email_sorter unavailable: {exc}") from exc

    # Reuse fetch logic from company email command center module when possible
    try:
        from scripts import company_email_command_center as cec
    except ImportError:
        cec = None  # type: ignore

    specs = {s.account_id: s for s in load_account_specs()}
    accounts_out: list[EmailAccountDigest] = []
    total = 0
    warnings: list[str] = []

    for aid in ids:
        spec = specs.get(aid)
        if spec is None:
            warnings.append(f"missing spec {aid}")
            continue
        try:
            service = get_account_gmail_service(aid)
        except Exception as exc:
            raise OperatorError(EMAIL_AUTH_UNAVAILABLE, f"Auth failed for {aid}: {exc}") from exc
        try:
            if cec is not None and hasattr(cec, "_fetch_unread_inbox"):
                raw_msgs = cec._fetch_unread_inbox(service, limit=limit_per_account)
            else:
                raise OperatorError(EMAIL_AUTH_UNAVAILABLE, "digest fetch helper missing")
        except OperatorError:
            raise
        except Exception as exc:
            raise OperatorError(EMAIL_AUTH_UNAVAILABLE, f"Fetch failed for {aid}: {exc}") from exc

        views: list[EmailMessageView] = []
        for m in raw_msgs:
            classified = classify_company_email(
                EmailMessage(
                    account_id=aid,
                    message_id=m.get("id", ""),
                    thread_id=m.get("threadId", ""),
                    from_header=m.get("from", ""),
                    subject=m.get("subject", ""),
                    snippet=m.get("snippet", ""),
                    body=m.get("body", ""),
                )
            )
            label = getattr(classified, "category", None) or "unclassified"
            if isinstance(classified, dict):
                label = classified.get("category") or "unclassified"
            views.append(
                EmailMessageView(
                    id=m.get("id", ""),
                    thread_id=m.get("threadId", ""),
                    from_redacted=_redact_from(m.get("from", "")),
                    subject=m.get("subject", "")[:200],
                    classification=str(label),
                    snippet_redacted=_redact_snippet(m.get("snippet", "")),
                )
            )
        total += len(views)
        accounts_out.append(
            EmailAccountDigest(account_id=aid, email=getattr(spec, "email", ""), messages=views)
        )

    result = EmailDigestResult(
        ok=True,
        source="gmail_api",
        freshness="fresh",
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        accounts=accounts_out,
        total_unread=total,
        cache_hit=False,
        warnings=warnings,
    )

    # Cache a minimal JSON-safe summary (no bodies)
    serial = {
        "generated_at": result.generated_at,
        "total_unread": result.total_unread,
        "warnings": result.warnings,
        "accounts": [
            {
                "account_id": a.account_id,
                "email": a.email,
                "count": len(a.messages),
            }
            for a in accounts_out
        ],
    }
    with _cache_lock:
        cache = _load_cache()
        cache[cache_key] = {"ts": now, "result": serial}
        _save_cache(cache)
    return result


def propose_draft_reply(
    account_id: str,
    message_id: str,
    body_text: str,
    *,
    reason: str = "Operator Desk draft proposal",
) -> ApprovalSubmissionResult:
    """
    Queue approval to create a Gmail draft.
    Does not call Gmail until human approves AND scripts.json registers DRAFT_TOOL_NAME.
    """
    known = set(_account_ids_from_config())
    if account_id not in known:
        raise OperatorError(EMAIL_ACCOUNT_NOT_FOUND, f"Unknown account_id: {account_id}")
    # Prefer proposal even if tool not yet registered: try submit; surface allowlist error clearly.
    return submit_tool_proposal(
        DRAFT_TOOL_NAME,
        {
            "account_id": account_id,
            "message_id": message_id,
            "body_text": body_text,
        },
        reason=reason,
        risk_level="medium",
        action_type="email_create_draft",
        file_path="operator_desk/email",
    )


def redact_for_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop body/token-like keys before telemetry."""
    blocked = {"body", "body_text", "token", "credentials", "authorization", "password"}
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if str(k).lower() in blocked:
            out[k] = "[redacted]"
        elif isinstance(v, dict):
            out[k] = redact_for_telemetry(v)
        else:
            out[k] = v
    return out
