# System catalog (generated)

Do not edit by hand. Regenerate with:

```bash
pip install -r scripts/requirements-catalog.txt
python scripts/generate_catalog_doc.py
```

Specification: [CATALOG_SSOT_IMPLEMENTATION_PLAN.md](../CATALOG_SSOT_IMPLEMENTATION_PLAN.md).

## Environments

| id | runtime_class | purpose |
|----|---------------|---------|
| main-rig | local_main | Primary workstation; canonical repo_registry paths; catalog validation |
| worker-rig | local_worker | Approved remote execution; not a second path column in repo_registry (v1) |
| cloud-hosted | cloud_hosted | Externally hosted dependencies (APIs, managed DB, etc.) |

## Components

| id | type | lifecycle | primary_repo | code_owner |
|----|------|-----------|--------------|------------|
| ai-lab | platform | partial | ai-lab | lab-core |
| command-center | orchestration | partial | command-center | lab-core |
| geomapper | application | partial | geomapper | lab-core |
| worker | worker_runtime | partial | worker | lab-core |
| secrets-config-plane | config_secrets_plane | partial | lab-secrets | lab-core |
