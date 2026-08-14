# Repos

Monorepo parent for Kylo, Growflow, COG, ai-lab, and supporting systems.

## Documentation

**[docs/AI_LAB_KYLO_GROWFLOW_OVERVIEW.md](docs/AI_LAB_KYLO_GROWFLOW_OVERVIEW.md)** — plain-language overview of **AI Lab**, **Project Kylo**, and **Growflow**.

**[docs/SYSTEMS_AND_REPOS.md](docs/SYSTEMS_AND_REPOS.md)** — unified ops map: worker (`C:\worker`), SSH tunnels, ports, secrets.

**[docs/SENIOR_LAYOUT.md](docs/SENIOR_LAYOUT.md)** — target zone layout (`products/`, `internal/`, …).

**[docs/REPO_PATH_MIGRATION.md](docs/REPO_PATH_MIGRATION.md)** — canonical old→new path map for humans, scripts, and Cursor agents.

**[tools/migration/README.md](tools/migration/README.md)** — migration toolkit (path helpers, inventory, migrate, power-1 smoke).

Index: [docs/README.md](docs/README.md).

## Worker runtime

Autonomous stack (Ollama, Worker Assistant, n8n) runs on the worker PC under **`C:\worker`**; it is not required to live inside this git tree. Details are in the unified doc and `C:\worker\docs\MAIN_RIG_ORCHESTRATION.md`.

## Interview portfolio (quick start)

Highlight on GitHub: `products/ai-lab` (orchestration + command center), `products/project-kylo` (event-driven finance ops), `products/cog-allocation`, and `products/gigatt-geomapper`. Runbooks and demo commands: [docs/INTERVIEW_DEMO_CHECKLIST.md](docs/INTERVIEW_DEMO_CHECKLIST.md).
