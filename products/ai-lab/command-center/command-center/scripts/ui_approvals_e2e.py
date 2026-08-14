"""Browser UI E2E: Approve / Deny / Always Approve on Command Center Chat tab."""
from __future__ import annotations

import json
import sys
import urllib.request

sys.path.insert(0, r"E:\Repos\products\ai-lab")
from brain.approval_queue.queue import list_pending, submit  # noqa: E402

UI = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("INSTALLING_PLAYWRIGHT")
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        from playwright.sync_api import sync_playwright

    with urllib.request.urlopen(API + "/api/approvals", timeout=10) as r:
        print("api_approvals", r.status, "count", len(json.loads(r.read().decode())))

    deny_id = submit(
        {
            "file_path": "operator_desk/ui_deny",
            "action_type": "operator_desk_tool",
            "reason": "UI_DENY_MARKER unique deny target",
            "risk_level": "low",
            "agent": "operator_desk",
            "tool_name": "_ui_deny_smoke",
            "args": {},
        }
    )
    always_id = submit(
        {
            "file_path": "E:/Repos/products/ai-lab/docs/OPERATOR_DESK.md",
            "action_type": "operator_desk_tool",
            "reason": "UI_ALWAYS_MARKER unique always target",
            "risk_level": "low",
            "agent": "operator_desk",
            "tool_name": "_ui_always_smoke",
            "args": {"k": 1},
        }
    )
    approve_id = submit(
        {
            "file_path": "operator_desk/ui_approve",
            "action_type": "operator_desk_tool",
            "reason": "UI_APPROVE_MARKER unique approve target",
            "risk_level": "low",
            "agent": "operator_desk",
            "tool_name": "_ui_approve_smoke",
            "args": {"n": 1},
        }
    )
    print("seeded", approve_id, always_id, deny_id)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(UI, wait_until="domcontentloaded", timeout=60000)
        page.get_by_role("tab", name="Chat").click(timeout=10000)
        page.wait_for_timeout(800)
        page.reload(wait_until="domcontentloaded")
        page.get_by_role("tab", name="Chat").click(timeout=10000)
        page.wait_for_timeout(2000)

        body_text = page.locator("body").inner_text()
        if "UI_APPROVE_MARKER" not in body_text:
            # Dump nearby UI text for diagnosis
            print("PAGE_SNIP", body_text[:1200].replace("\n", " | "))
            page.screenshot(path=r"E:\Repos\products\ai-lab\command-center\command-center\.logs\ui_e2e_fail.png")
            # Directly verify API has marker
            with urllib.request.urlopen(API + "/api/approvals", timeout=10) as r:
                rows = json.loads(r.read().decode())
            print("api_top", [(x["id"], x.get("detail", "")[:40]) for x in rows[:5]])
            browser.close()
            print("UI_E2E_FAIL not visible")
            return 1

        with page.expect_response(
            lambda r: "/api/approvals/resolve" in r.url and r.request.method == "POST",
            timeout=30000,
        ) as resp_info:
            page.get_by_role("button", name="Approve").first.click()
        body = resp_info.value.json()
        print("APPROVE_HTTP", resp_info.value.status, body)
        if not body.get("ok"):
            browser.close()
            print("UI_E2E_FAIL approve body")
            return 1
        page.get_by_text(f"{approve_id} approved", exact=False).first.wait_for(timeout=15000)

        always_card = (
            page.locator("div")
            .filter(has_text="UI_ALWAYS_MARKER")
            .filter(has=page.get_by_role("button", name="Always Approve"))
            .first
        )
        always_card.wait_for(timeout=15000)
        with page.expect_response(
            lambda r: "/api/approvals/permanent" in r.url and r.request.method == "POST",
            timeout=30000,
        ):
            with page.expect_response(
                lambda r: "/api/approvals/resolve" in r.url and r.request.method == "POST",
                timeout=30000,
            ) as always_resolve:
                always_card.get_by_role("button", name="Always Approve").click()
        always_body = always_resolve.value.json()
        print("ALWAYS_RESOLVE", always_body)
        if not always_body.get("ok"):
            browser.close()
            print("UI_E2E_FAIL always")
            return 1
        page.get_by_text("Always Approve: saved permanent rule", exact=False).first.wait_for(timeout=15000)

        deny_card = (
            page.locator("div")
            .filter(has_text="UI_DENY_MARKER")
            .filter(has=page.get_by_role("button", name="Deny"))
            .first
        )
        deny_card.wait_for(timeout=15000)
        with page.expect_response(
            lambda r: "/api/approvals/resolve" in r.url and r.request.method == "POST",
            timeout=30000,
        ) as deny_info:
            deny_card.get_by_role("button", name="Deny").click()
        deny_body = deny_info.value.json()
        print("DENY_HTTP", deny_body)
        if not deny_body.get("ok"):
            browser.close()
            print("UI_E2E_FAIL deny")
            return 1
        page.get_by_text(f"{deny_id} denied", exact=False).first.wait_for(timeout=15000)

        browser.close()

    pending_ids = {i for i, _ in list_pending()}
    leftovers = {approve_id, always_id, deny_id} & pending_ids
    print("pending_leftovers", leftovers)
    if leftovers:
        print("UI_E2E_FAIL still pending")
        return 1
    print("UI_E2E_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
