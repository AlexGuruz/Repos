"""
Router: classify intent and select agent/tool. Keyword-based with relaxed phrasing (slang, short terms).
"""
from __future__ import annotations


def classify_intent(message: str) -> tuple[str, dict]:
    """
    Return (intent, params). Intents: answer, search, run, propose.
    Accepts natural phrasing: "growflow sales today", "my sales", "find in repos", "scan repo", etc.
    """
    msg = (message or "").strip().lower()
    if msg.startswith("approve ") or msg.startswith("deny "):
        return "approval", {}
    if msg.rstrip(".!?") in ("do it", "yes", "go ahead", "do that", "approve", "ok", "sure"):
        return "execute_proposal", {}
    if "search repos for" in msg or "search repo for" in msg:
        q = msg.split("for", 1)[-1].strip()
        if q:
            return "repo_search", {"query": q}
    if ("find" in msg or "search" in msg) and ("repo" in msg or "repos" in msg) and "scan" not in msg:
        # "find it in repos", "find in repos" -> repo_search; query from context or message
        if " for " in msg:
            q = msg.split(" for ", 1)[-1].strip()
            return "repo_search", {"query": q or None}
        return "repo_search", {"query": None}
    if "approve" in msg or "deny" in msg:
        return "approval", {}
    if "run" in msg and "script" in msg:
        return "run", {}
    # Growflow sales: "sales today", "growflow sales", "my sales", "what's my sales", "sales for today"
    if "growflow" in msg and "sales" in msg:
        return "run", {"tool_hint": "growflow_sales_today", "args": {"date": "today"}}
    if "sales" in msg and ("today" in msg or "for today" in msg):
        return "run", {"tool_hint": "growflow_sales_today", "args": {"date": "today"}}
    # Scan results: "show scan results", "view scan results", "what did the scan tell you", "summary from scan"
    if any(w in msg for w in ("scan result", "scan results", "scan tell", "scan tell you", "improvements from", "summary from scan", "what did the scan", "what did that scan")):
        return "scan_results", {}
    if "show" in msg and "scan" in msg:
        return "scan_results", {}
    if "view" in msg and "scan" in msg:
        return "scan_results", {}
    # Hardware (Guru §25): "what's my hardware doing", "why is system lagging", "GPU memory", "CPU headroom"
    if any(w in msg for w in ("hardware", "gpu", "cpu", "vram", "lagging", "lag", "slow", "headroom", "temperature", "temp ")):
        if any(w in msg for w in ("what", "how", "why", "which", "doing", "using", "using my", "headroom", "right now")):
            return "hardware_status", {}
        if "worker" in msg and ("slow" in msg or "overload" in msg or "which service" in msg):
            return "hardware_status", {}
    if "what's using my gpu" in msg or "what is using my gpu" in msg:
        return "hardware_status", {}
    if "keep" in msg and "responsive" in msg:
        return "hardware_status", {}

    # Worker health (Guru §26): "is the worker up", "is worker assistant healthy", "is n8n reachable"
    if any(w in msg for w in ("worker up", "worker down", "is the worker", "check worker", "worker healthy", "worker assistant", "is n8n", "n8n up", "ollama on the worker", "worker ollama")):
        if any(w in msg for w in ("up", "down", "healthy", "running", "reachable", "responding", "check")):
            return "worker_health", {}
    if "is worker assistant" in msg or "worker assistant running" in msg:
        return "worker_health", {}
    if "is n8n up" in msg or "n8n reachable" in msg:
        return "worker_health", {}
    if "why can't" in msg and "worker" in msg:
        return "worker_health", {}
    if "main rig use the worker" in msg or "use the worker assistant" in msg:
        return "worker_health", {}

    # Worker Assistant: index repo, retrieve (Guru §26)
    if any(w in msg for w in ("index repo", "index repos", "index on worker")):
        repo_path = None
        if " path " in msg or " for " in msg:
            for sep in (" for ", " path ", " repo "):
                if sep in msg:
                    part = msg.split(sep, 1)[-1].strip().split()[0]
                    if part and part not in ("worker", "the", "on"):
                        repo_path = part
                        break
        return "worker_index", {"repo_path": repo_path or "repos_root"}
    if any(w in msg for w in ("query worker", "ask worker", "worker retrieve", "retrieve from worker")):
        q = None
        if " for " in msg or " query " in msg:
            q = msg.split(" for ", 1)[-1].split(" query ", 1)[-1].strip() or msg.split(" query ", 1)[-1].strip()
        return "worker_retrieve", {"query": q or msg[:200]}

    # n8n trigger: "trigger workflow X", "run n8n workflow" (approval-gated)
    if any(w in msg for w in ("trigger workflow", "run n8n", "trigger n8n", "run workflow")):
        workflow_id = None
        for sep in ("workflow ", "n8n ", "trigger ", "run "):
            if sep in msg:
                rest = msg.split(sep, 1)[-1].strip()
                if rest:
                    workflow_id = rest.split()[0] if rest.split() else "default"
                break
        return "trigger_workflow", {"workflow_id": workflow_id or "default"}

    # Company BI / business data (sales, inventory, expenses, payroll) — feed from Growflow BI summary
    if any(w in msg for w in (
        "company bi", "companybi", "business summary", "business data", "sales and expenses",
        "sales, inventory", "inventory and payroll", "how's the business", "business sales",
        "bi summary", "growflow bi", "dispensary sales", "dispensary expenses",
    )):
        return "company_bi", {}
    if ("sales" in msg or "expenses" in msg or "payroll" in msg or "inventory" in msg) and any(w in msg for w in ("summary", "overview", "report", "how are we", "what's our", "our business")):
        return "company_bi", {}

    # Ops overview (Guru §23): "what systems do I have", "list my workers", "ops overview"
    if any(w in msg for w in ("ops overview", "ops fabric", "what systems", "list my workers", "what workers", "what automations", "what's in my ops", "my systems", "my workers")):
        return "ops_overview", {}
    if "systems" in msg and ("have" in msg or "list" in msg or "what" in msg or "show" in msg):
        return "ops_overview", {}
    if "workers" in msg and ("list" in msg or "what" in msg or "show" in msg or "my " in msg):
        return "ops_overview", {}

    # Repo: "scan repo", "summarize repo", "find in repos", "search repos", "look in repo", "find it in repos"
    if "repo" in msg or "repos" in msg:
        if any(w in msg for w in ("scan", "summarize", "find", "search", "look", "show")):
            parts = msg.replace(",", " ").split()
            repo_name = None
            for token in ("repo", "repos"):
                if token in parts:
                    i = parts.index(token)
                    if i + 1 < len(parts):
                        nxt = parts[i + 1]
                        if nxt in ("repo", "repos"):
                            continue
                        if nxt == "for" and i + 2 < len(parts):
                            repo_name = parts[i + 2]
                        elif nxt not in ("for",):
                            repo_name = nxt
                    break
            return "run_agent", {"agent": "repo_cartographer", "repo_name": repo_name or "repos_root"}
    return "answer", {}
