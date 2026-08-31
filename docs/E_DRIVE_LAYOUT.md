# E: Drive Layout

**Purpose:** Classify every top-level folder on `E:\` so business code, secrets, personal media, and experiments stay separated.  
**As of:** 2026-07-23  
**Related:** [REPO_FUNCTION_OWNERSHIP.md](REPO_FUNCTION_OWNERSHIP.md) · [SYSTEMS_AND_REPOS.md](SYSTEMS_AND_REPOS.md)

---

## Zone map (target)

| Zone | Path | Role |
|------|------|------|
| **Secrets** | `E:\secrets\` | Credential store — never commit |
| **Business monorepo** | `E:\Repos\` | Flagships, support projects, docs SSOT |
| **Personal / media** | `E:\Personal\` | Photos, dashcam, loose media |
| **Archive** | `E:\_archive_E\YYYY-MM-DD\` | Learning clones, vendor sandboxes, tmp |
| **Tooling** | `E:\Git\`, `E:\.vscode\`, `E:\.claude\` | Host tooling (stay at root) |
| **OS / system** | `$RECYCLE.BIN`, `System Volume Information`, `Recovery` | Leave alone |

Runtime on other hosts (`C:\worker` on power-1 / worker-node) is **documented only** — not moved by this cleanup.

---

## Classification table (every current `E:\` top-level)

| Item | Zone | Decision | Notes |
|------|------|----------|-------|
| `Repos\` | Business | **Keep** | Canonical monorepo |
| `secrets\` | Secrets | **Keep** | Never into git |
| `kylo-site\` | Duplicate product | **Move to `_archive_E`** | Canonical = `Repos\kylo-site` (has `.git` + remote) |
| `Leighas iphone photos\` | Personal | **Move to `E:\Personal\`** | Media |
| `Gigatt DashCam\` | Personal | **Move to `E:\Personal\`** | Media |
| `1000_F_444052013_….jpg` | Personal | **Move to `E:\Personal\`** | Loose JPG at root |
| `Ossu Learning This Shit\` | Learning | **Move to `_archive_E`** | Not a business product |
| `MoneyPrinter\` | Learning | **Move to `_archive_E`** | Experiment |
| `MLB system\` | Learning | **Move to `_archive_E`** | Experiment |
| `Flower Package Labels\` | Learning | **Move to `_archive_E`** | Experiment |
| `Normal\` | Learning | **Move to `_archive_E`** | Experiment |
| `AppFlowy\` | Learning | **Move to `_archive_E`** | Upstream / local app clone |
| `copier\` | Vendor | **Move to `_archive_E`** | Tooling vendor clone |
| `focalboard\` | Vendor | **Move to `_archive_E`** | Tooling vendor clone |
| `pre-commit\` | Vendor | **Move to `_archive_E`** | Tooling vendor clone |
| `renovate\` | Vendor | **Move to `_archive_E`** | Tooling vendor clone |
| `Git\` | Tooling | **Keep** | Portable / local Git |
| `.vscode\` | Tooling | **Keep** | Editor settings |
| `.claude\` | Tooling | **Keep** | Agent tooling |
| `barrier.conf` | Tooling | **Keep** | KVM config |
| `.git.backup-pre-professionalization\` | Quarantine | **Keep archived** | Do not restore drive-root git |
| `msdownld.tmp\` | Quarantine | **Move to `_archive_E`** | Temp |
| `DumpStack.log.tmp` | Quarantine | **Move to `_archive_E`** | Temp log |
| `$RECYCLE.BIN` | OS | **Leave** | System |
| `System Volume Information` | OS | **Leave** | System |
| `Recovery` | OS | **Leave** | System |

---

## After cleanup — expected `E:\` root

```text
E:\
  Personal\          # photos, dashcam, media
  Repos\             # business monorepo
  secrets\           # credentials (never git)
  _archive_E\        # dated quarantine of experiments/vendors
  Git\               # tooling
  .vscode\  .claude\
  barrier.conf
  README.txt         # this map in one screen
  (.git.backup-… remains hidden/archived)
```

---

## Non-negotiables

1. Never move secret JSON into `Repos` git tree.  
2. Do not delete personal media or live secrets without explicit OK.  
3. Physical moves only follow [REPO_FUNCTION_OWNERSHIP.md](REPO_FUNCTION_OWNERSHIP.md).  
4. power-1 Kylo watchers / `C:\worker` are out of scope for file moves.
