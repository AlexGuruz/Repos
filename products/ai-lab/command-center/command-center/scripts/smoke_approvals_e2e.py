"""E2E smoke: approve / deny / always against live CC API (default :8000)."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, r"E:\Repos\products\ai-lab")
from brain.approval_queue.queue import list_pending, submit  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def post(path: str, body: dict, timeout: float = 20.0):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
            print(f"OK {path} {r.status} {int((time.perf_counter()-t0)*1000)}ms {payload}")
            return r.status, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        print(f"HTTP {path} {e.code} {int((time.perf_counter()-t0)*1000)}ms {payload}")
        return e.code, payload
    except Exception as e:
        print(f"ERR {path} {int((time.perf_counter()-t0)*1000)}ms {type(e).__name__}: {e}")
        return 0, {"ok": False, "error": str(e)}


def main() -> int:
    a = submit(
        {
            "file_path": "operator_desk/test",
            "action_type": "operator_desk_tool",
            "reason": "approve smoke",
            "risk_level": "low",
            "agent": "operator_desk",
            "tool_name": "_cc_approve_smoke",
            "args": {"n": 1},
        }
    )
    b = submit(
        {
            "file_path": "operator_desk/test",
            "action_type": "operator_desk_tool",
            "reason": "deny smoke",
            "risk_level": "low",
            "agent": "operator_desk",
            "tool_name": "_cc_deny_smoke",
            "args": {},
        }
    )
    c = submit(
        {
            "file_path": "E:/Repos/products/ai-lab/docs/OPERATOR_DESK.md",
            "action_type": "operator_desk_tool",
            "reason": "always smoke",
            "risk_level": "low",
            "agent": "operator_desk",
            "tool_name": "_cc_always_smoke",
            "args": {"k": "v"},
        }
    )
    print("submitted", a, b, c)

    results = {}
    for key, path, body in [
        ("APPROVE", "/api/approvals/resolve", {"id": a, "resolution": "approved"}),
        ("DENY", "/api/approvals/resolve", {"id": b, "resolution": "denied"}),
        ("PERM", "/api/approvals/permanent", {"approval_id": c, "note": "repair smoke"}),
        ("ALWAYS_RESOLVE", "/api/approvals/resolve", {"id": c, "resolution": "approved"}),
        ("DUP", "/api/approvals/resolve", {"id": a, "resolution": "approved"}),
        ("MISS", "/api/approvals/resolve", {"id": "approval-missing-xyz", "resolution": "approved"}),
    ]:
        results[key] = post(path, body)
        time.sleep(0.15)

    pending = [i for i, _ in list_pending()]
    print("pending_count", len(pending))

    ok = True
    if not results["APPROVE"][1].get("ok"):
        ok = False
    if not results["DENY"][1].get("ok"):
        ok = False
    if not results["PERM"][1].get("ok"):
        ok = False
    if not results["ALWAYS_RESOLVE"][1].get("ok"):
        ok = False
    if results["DUP"][1].get("ok") is not False:
        ok = False
    if results["MISS"][1].get("ok") is not False:
        ok = False
    if a in pending or b in pending or c in pending:
        ok = False
        print("FAIL: smoke ids still pending")
    print("E2E_OK" if ok else "E2E_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
