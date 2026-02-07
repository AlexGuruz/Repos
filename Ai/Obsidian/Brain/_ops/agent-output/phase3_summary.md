# Phase 3 Summary - New Rig Orchestrator

**Timestamp:** 2026-02-03

## Overview

Phase 3 implementation completed on new rig. Vault templates created, deploy target registry established, and deploy.ps1 upgraded with target-based deployment capabilities. All outputs stored in Obsidian vault.

## Links

- [[phase2_summary]] - Phase 2 implementation summary
- [[../30_infra/hosts/oldrig|oldrig]] - Legacy worker node host note
- [[../30_infra/hosts/newrig|newrig]] - New orchestrator node host note

## Vault Templates

### Watcher Template
- **Location**: `30_infra\watchers\_template.md`
- **Purpose**: Template for creating watcher configurations to monitor infrastructure components
- **Fields**: watcher_name, target_host, target_type, check_interval, status, checks, alerts

### Docker Stack Template
- **Location**: `30_infra\docker\_stack_template.md`
- **Purpose**: Template for documenting Docker stacks deployed across infrastructure
- **Fields**: stack_name, host, compose_path, services, deployment details

### Service Runbook Template
- **Location**: `10_runbooks\_service_runbook_template.md`
- **Purpose**: Template for creating operational runbooks for services
- **Fields**: service_name, service_type, common operations, troubleshooting guides

### Index Notes
- **Location**: `30_infra\watchers\index.md` - Watchers index
- **Location**: `30_infra\docker\index.md` - Docker stacks index
- **Purpose**: Centralized navigation for watchers and Docker stacks

## Deploy Target Registry

### Registry Schema

The deploy target registry uses JSON format with the following structure:

```json
{
  "version": "1.0",
  "updated": "ISO8601 timestamp",
  "targets": [
    {
      "name": "unique-target-name",
      "type": "docker-stack|scheduled-task",
      "host": "hostname",
      "path": "path (for docker-stack)",
      "task": "task-name (for scheduled-task)",
      "description": "human-readable description"
    }
  ]
}
```

### Registry Locations

- **Vault Location**: `E:\Ai\Obsidian\Brain\30_infra\deploy_targets.json`
- **Mirror Location**: `C:\worker\ops\deploy_targets.json`
- **Purpose**: Centralized registry of deployment targets accessible from both vault and operational scripts

### Initial Targets

1. **oldrig-core-redis**
   - Type: docker-stack
   - Host: oldrig
   - Path: `C:\worker\docker\stacks\core`
   - Description: Core Redis stack on oldrig

2. **oldrig-telemetry**
   - Type: scheduled-task
   - Host: oldrig
   - Task: `Worker-Telemetry`
   - Description: Telemetry scheduled task on oldrig

3. **oldrig-agents-runner**
   - Type: scheduled-task
   - Host: oldrig
   - Task: `Worker-Agents`
   - Description: Agents runner scheduled task on oldrig

## Deploy Script Upgrade

### Script Location
- **Path**: `C:\worker\ops\oldrig\deploy.ps1`
- **Log File**: `C:\worker\logs\phase3_newrig.log`

### New Features

1. **Target-Based Deployment**
   - Loads targets from `C:\worker\ops\deploy_targets.json`
   - Supports `-Target <name>` parameter to specify deployment target
   - Lists all available targets if none specified

2. **Execution Modes**
   - **Dry Run (Default)**: `-DryRun` (default) - Shows what would be executed without making changes
   - **Execute Mode**: `-Execute` - Actually performs the deployment
   - **Safety**: Defaults to dry-run mode to prevent accidental deployments

3. **Target Type Support**
   - **docker-stack**: Executes `ssh <host> "cd <path> && docker compose up -d"`
   - **scheduled-task**: Executes `schtasks /Run /TN <taskname>`

4. **Error Handling**
   - Validates target exists in registry
   - Validates required properties for each target type
   - Provides clear error messages and exit codes

### Usage Examples

List all available targets:
```powershell
.\deploy.ps1
```

Dry run (default) - see what would happen:
```powershell
.\deploy.ps1 -Target oldrig-core-redis
```

Execute deployment:
```powershell
.\deploy.ps1 -Target oldrig-core-redis -Execute
```

Deploy scheduled task:
```powershell
.\deploy.ps1 -Target oldrig-telemetry -Execute
```

## Scripts Changed/Created

### Created Scripts
- None (deploy.ps1 was upgraded, not created)

### Modified Scripts
- `C:\worker\ops\oldrig\deploy.ps1` - Upgraded with target registry support and execution modes

### Created Files
- `E:\Ai\Obsidian\Brain\30_infra\watchers\_template.md` - Watcher template
- `E:\Ai\Obsidian\Brain\30_infra\docker\_stack_template.md` - Docker stack template
- `E:\Ai\Obsidian\Brain\10_runbooks\_service_runbook_template.md` - Service runbook template
- `E:\Ai\Obsidian\Brain\30_infra\watchers\index.md` - Watchers index
- `E:\Ai\Obsidian\Brain\30_infra\docker\index.md` - Docker stacks index
- `E:\Ai\Obsidian\Brain\30_infra\deploy_targets.json` - Deploy targets registry (vault)
- `C:\worker\ops\deploy_targets.json` - Deploy targets registry (mirror)

## Directory Structure

```
C:\worker\
├── logs\
│   └── phase3_newrig.log
└── ops\
    ├── deploy_targets.json
    └── oldrig\
        └── deploy.ps1

E:\Ai\Obsidian\Brain\
├── 10_runbooks\
│   └── _service_runbook_template.md
├── 30_infra\
│   ├── deploy_targets.json
│   ├── docker\
│   │   ├── _stack_template.md
│   │   └── index.md
│   ├── hosts\
│   │   ├── oldrig.md
│   │   └── newrig.md
│   └── watchers\
│       ├── _template.md
│       └── index.md
└── _ops\
    └── agent-output\
        ├── phase2_summary.md
        └── phase3_summary.md
```

## Notes

- All scripts handle errors gracefully and log to `C:\worker\logs\phase3_newrig.log`
- Deploy script defaults to dry-run mode for safety
- Deploy targets registry is stored in both vault and operational location for redundancy
- Templates follow Obsidian markdown format with frontmatter metadata
- No secrets stored in notes, logs, or registry files (per constraints)
- Index notes provide centralized navigation for watchers and Docker stacks

## Next Steps

### Phase 4: Real Watcher Implementation

1. **Watcher System**:
   - Implement actual watcher scripts to monitor oldrig status
   - Create watcher configurations using the template
   - Set up automated health checks

2. **Deployment Automation**:
   - Consider scheduling deployments
   - Add deployment validation and rollback
   - Implement deployment notifications

3. **Registry Expansion**:
   - Add more deployment targets as needed
   - Document deployment procedures
   - Create runbooks for each service

4. **Monitoring Integration**:
   - Connect watchers to telemetry system
   - Set up alerting thresholds
   - Create monitoring dashboards
