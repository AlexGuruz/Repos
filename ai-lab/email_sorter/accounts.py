from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_AI_LAB_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ACCOUNTS_PATH = _AI_LAB_ROOT / "email_sorter" / "config" / "accounts.yaml"


@dataclass(frozen=True)
class AccountSpec:
    id: str
    email: str
    display_name: str
    token_file: Path
    roles: tuple[str, ...]
    digest_priority: str = "normal"


def _resolve_repo_path(raw: str | Path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (_AI_LAB_ROOT / p).resolve()


def load_accounts_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or _DEFAULT_ACCOUNTS_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Accounts config not found: {cfg_path}")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid accounts config (expected mapping): {cfg_path}")
    return data


def load_account_specs(path: Path | None = None) -> list[AccountSpec]:
    data = load_accounts_config(path=path)
    credentials_file = _resolve_repo_path(data.get("credentials_file") or "secrets/gmail/credentials.json")
    accounts_raw = data.get("accounts") or []
    if not isinstance(accounts_raw, list) or not accounts_raw:
        raise ValueError("accounts.yaml must define a non-empty `accounts` list.")

    specs: list[AccountSpec] = []
    for row in accounts_raw:
        if not isinstance(row, dict):
            continue
        account_id = str(row.get("id") or "").strip()
        email = str(row.get("email") or "").strip()
        if not account_id or not email:
            continue
        token_raw = row.get("token_file") or f"secrets/gmail/tokens/{account_id}.json"
        roles_raw = row.get("roles") or []
        roles = tuple(str(r).strip() for r in roles_raw if str(r).strip()) if isinstance(roles_raw, list) else ()
        specs.append(
            AccountSpec(
                id=account_id,
                email=email,
                display_name=str(row.get("display_name") or account_id).strip(),
                token_file=_resolve_repo_path(token_raw),
                roles=roles,
                digest_priority=str(row.get("digest_priority") or "normal").strip(),
            )
        )
    if not specs:
        raise ValueError("No valid account entries found in accounts.yaml.")
    return specs


def resolve_shared_credentials_file(path: Path | None = None) -> Path:
    data = load_accounts_config(path=path)
    return _resolve_repo_path(data.get("credentials_file") or "secrets/gmail/credentials.json")


def load_gmail_client_module() -> Any:
    """Prefer gmail_portable (multi-account token_file / credentials_file kwargs)."""
    legacy = _AI_LAB_ROOT / "Ai" / "Email-Inbox-Agent---Doo-Made"
    portable = _AI_LAB_ROOT / "email_sorter" / "gmail_portable"
    # Portable first: supports per-account OAuth paths used by accounts.yaml.
    if (portable / "app" / "gmail_client.py").exists():
        agent_root = portable
    elif (legacy / "app" / "gmail_client.py").exists():
        agent_root = legacy
    else:
        raise FileNotFoundError(
            "Gmail adapter not found. Expected email_sorter/gmail_portable or Ai/Email-Inbox-Agent---Doo-Made."
        )
    # Avoid a stale `app` package from a previous import of the other adapter.
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    else:
        # Ensure this adapter wins if both roots are on sys.path.
        sys.path.remove(str(agent_root))
        sys.path.insert(0, str(agent_root))
    from app import gmail_client as gmail_client_mod  # type: ignore

    return gmail_client_mod


def get_account_gmail_service(account: AccountSpec, *, credentials_file: Path | None = None) -> Any:
    gmail_client = load_gmail_client_module()
    creds_path = credentials_file or resolve_shared_credentials_file()
    return gmail_client.get_gmail_service(
        token_file=str(account.token_file),
        credentials_file=str(creds_path),
    )


def preflight_account(account: AccountSpec, *, credentials_file: Path | None = None) -> dict[str, Any]:
    gmail_client = load_gmail_client_module()
    creds_path = credentials_file or resolve_shared_credentials_file()
    detail: dict[str, Any]
    if hasattr(gmail_client, "preflight_gmail_auth"):
        try:
            detail = gmail_client.preflight_gmail_auth(
                token_file=str(account.token_file),
                credentials_file=str(creds_path),
            )
        except TypeError:
            detail = {
                "ok": account.token_file.exists() and creds_path.exists(),
                "token_file": str(account.token_file),
                "credentials_file": str(creds_path),
            }
    else:
        detail = {
            "ok": account.token_file.exists() and creds_path.exists(),
            "token_file": str(account.token_file),
            "credentials_file": str(creds_path),
        }
    # Company multi-account: require per-account token, not only shared client secrets.
    token_ok = account.token_file.exists()
    creds_ok = creds_path.exists()
    detail["ok"] = bool(token_ok and creds_ok)
    detail["account_token_present"] = token_ok
    detail["shared_credentials_present"] = creds_ok
    return detail


def auth_account(account_id: str, *, accounts_path: Path | None = None) -> dict[str, Any]:
    account = _find_account(account_id, accounts_path=accounts_path)
    gmail_client = load_gmail_client_module()
    creds_path = resolve_shared_credentials_file(path=accounts_path)
    account.token_file.parent.mkdir(parents=True, exist_ok=True)
    service = gmail_client.get_gmail_service(
        token_file=str(account.token_file),
        credentials_file=str(creds_path),
    )
    profile = service.users().getProfile(userId="me").execute()
    return {
        "account_id": account.id,
        "email": profile.get("emailAddress") or account.email,
        "token_file": str(account.token_file),
    }


def _find_account(account_id: str, *, accounts_path: Path | None = None) -> AccountSpec:
    wanted = account_id.strip().lower()
    for spec in load_account_specs(path=accounts_path):
        if spec.id.lower() == wanted:
            return spec
    raise KeyError(f"Unknown account id: {account_id}")


def auth_check_all(*, accounts_path: Path | None = None) -> dict[str, Any]:
    creds_path = resolve_shared_credentials_file(path=accounts_path)
    rows: list[dict[str, Any]] = []
    ok = True
    for account in load_account_specs(path=accounts_path):
        preflight = preflight_account(account, credentials_file=creds_path)
        row_ok = bool(preflight.get("ok"))
        ok = ok and row_ok
        rows.append(
            {
                "id": account.id,
                "email": account.email,
                "display_name": account.display_name,
                "token_file": str(account.token_file),
                "ok": row_ok,
                "preflight": preflight,
            }
        )
    return {
        "ok": ok,
        "credentials_file": str(creds_path),
        "accounts": rows,
    }


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Company Gmail account registry and OAuth helper.")
    ap.add_argument("--accounts", type=Path, default=_DEFAULT_ACCOUNTS_PATH, help="Path to accounts.yaml")
    ap.add_argument("--auth-check", action="store_true", help="Verify credential/token files for all accounts.")
    ap.add_argument("--auth", metavar="ACCOUNT_ID", help="Run OAuth for one account (interactive browser).")
    ap.add_argument("--list", action="store_true", help="Print configured accounts.")
    args = ap.parse_args()

    if args.list:
        for spec in load_account_specs(path=args.accounts):
            print(f"{spec.id}\t{spec.email}\t{spec.token_file}")
        return 0

    if args.auth_check:
        report = auth_check_all(accounts_path=args.accounts)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1

    if args.auth:
        result = auth_account(args.auth, accounts_path=args.accounts)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
