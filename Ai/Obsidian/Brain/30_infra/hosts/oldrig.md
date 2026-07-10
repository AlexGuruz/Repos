---
hostname: oldrig
ip: 192.168.40.25
role: legacy-worker-node
user: worker
identity_file: C:/Users/zacle/.ssh/id_oldrig_nopass
status: active
---

# Oldrig

## Overview
Legacy worker node hosting core Docker stack.

## Connection
```powershell
ssh oldrig
```

## Key Commands

### Status Check
```powershell
ssh oldrig whoami
ssh oldrig docker ps
ssh oldrig docker compose ps
```

### System Info
```powershell
ssh oldrig uptime
ssh oldrig df -h
```

### Docker Operations
```powershell
ssh oldrig docker ps
ssh oldrig docker compose -f /path/to/compose.yml ps
```

## Related
- [[30_infra/hosts/newrig|newrig]]
- [[_ops/agent-output/phase0_gate|phase0_gate]]
- [[_ops/agent-output/phase1_summary|phase1_summary]]
