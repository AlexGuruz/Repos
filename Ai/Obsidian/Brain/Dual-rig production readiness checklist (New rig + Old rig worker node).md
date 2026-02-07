Dual-rig production readiness checklist (New rig + Old rig worker node)
0) Status markers

 SSH: ssh oldrig "whoami" works with no password/passphrase

 Remote Docker: ssh oldrig "docker ps" works

1) Network + access hardening

 Assign static DHCP reservation for old rig IP (router) or set static IP

 Confirm both rigs on same VLAN/subnet (expected: 192.168.40.0/24)

 Lock SSH to LAN only (firewall scope) or restrict allowed source IPs to new rig

 Disable SSH password auth (keys-only) once confirmed stable

 Confirm OpenSSH logs to OpenSSH/Operational and rotation is acceptable

 Create a “break glass” local admin account (documented offline)

2) Identity + secrets

 Decide service account model on old rig (keep worker as automation user)

 Store required secrets in your chosen vault (Google Secret Manager / local encrypted file / Windows Credential Manager)

 Define .env conventions for Docker stacks and watchers

 Create C:\worker\secrets\ (restricted ACL) for any local-only secrets (if needed)

3) Filesystem + workspace standardization (old rig)

 Confirm folder layout exists:

 C:\worker\docker\stacks\

 C:\worker\repos\

 C:\worker\agents\

 C:\worker\logs\

 C:\worker\venvs\

 Add log subfolders:

 C:\worker\logs\docker\

 C:\worker\logs\watchers\

 C:\worker\logs\tasks\

 Decide repo sync model (recommended):

 New rig = edit/commit/push

 Old rig = pull/build/run

4) Docker production baseline (old rig)

 Confirm Docker Desktop starts on boot and engine is stable

 Create core stack directory: C:\worker\docker\stacks\core\

 Add baseline compose (at minimum):

 Redis (already)

 Optional: Postgres (if needed for services)

 Optional: Portainer (for UI management)

 Set restart: unless-stopped on all long-running services

 Standardize volumes under C:\worker\docker\data\ (if using bind mounts)

 Verify reboot persistence: containers come back after reboot

5) Watchers / scripts runtime model

 Choose primary runner approach:

 Scheduled Tasks (recommended first)

 Dockerized watchers (later)

 Create C:\worker\agents\run.ps1 (master runner)

 Add per-watcher config files (YAML/JSON) under C:\worker\agents\configs\

 Create Scheduled Task: Worker-Agents

 Trigger: At startup

 Run whether user logged on or not

 Highest privileges

 Logs to C:\worker\logs\watchers\

 Add health checks / restart-on-crash loop

6) Remote operations (new rig → old rig)

 Create ssh wrapper scripts on new rig:

 oldrig-status.ps1 (whoami, docker ps, task status)

 oldrig-deploy.ps1 (git pull, build, restart stack)

 oldrig-logs.ps1 (tail key logs)

 Add “single command” deploy pattern:

 ssh oldrig "cd C:\worker\repos\<repo> && git pull && docker compose up -d --build"

7) Monitoring + logging

 Decide monitoring baseline:

 Windows Event log export for SSH/Docker issues

 Container logs strategy (json-file defaults vs driver)

 Implement log retention policy (size/time)

 Add simple heartbeat:

 ssh oldrig "docker ps" returns expected containers

 Worker-Agents task reports running

 Optional: add uptime + disk + GPU checks (scheduled)

8) CI/CD integration (optional but production-grade)

 Decide trigger mechanism:

 Manual (SSH deploy scripts)

 GitHub Actions → self-hosted runner on old rig

 If self-hosted runner:

 Install runner as service

 Restrict repo access and secrets

 Define deploy workflow to Docker stacks

9) Reliability / recovery

 Create restore procedure doc:

 Reinstall Docker Desktop

 Restore C:\worker\docker\ + volumes

 Restore Scheduled Tasks

 Restore SSH keys

 Setup backups:

 C:\worker\docker\ (compose + config)

 C:\worker\agents\ (runner + scripts)

 critical repos or git remote ensures recoverability

 Test failure modes:

 power loss reboot

 Docker engine restart

 watcher crash auto-restart

10) Security finalization

 Remove unused SSH keys from administrators_authorized_keys

 Confirm Windows updates policy (maintenance window)

 Confirm Defender exclusions (only if necessary; document)

 Tighten firewall rules for services ports (only expose what’s needed)

 Least-privilege review (if worker admin is not required long-term)

11) Production “go-live” checklist

 All required containers up and stable for 24h

 Watchers running and producing expected outputs

 Logs are written and rotated

 Remote deploy script works end-to-end

 Rollback plan validated (previous image/tag or compose version)

 Backup verified (restore test performed)

can i do most of the rest via new rig or do i still need manual access to old rig?
Thought for 14s

Yes—you can do most of the remaining work from the new rig via ssh oldrig .... You only need manual/GUI access to the old rig for a small set of Windows/Docker Desktop “user session” items.

You can do from the new rig (SSH-only)
Windows services, firewall, SSH hardening

 Restart/verify services (sshd, etc.)

 Create/limit firewall rules (scope to new rig IP only)

 Edit C:\ProgramData\ssh\sshd_config and restart sshd

 Disable password auth (keys-only)

Docker operations

 docker ps / compose up -d / compose logs / compose pull

 Create stacks under C:\worker\docker\stacks\...

 Deploy updates remotely (git pull && docker compose up -d --build)

Watchers/scripts and automation

 Create/update files under C:\worker\agents\...

 Create Scheduled Tasks (schtasks / PowerShell ScheduledTasks)

 Start/stop/check tasks and logs

 Health checks (disk, uptime, container status)

Repo sync model

 Clone/pull repos into C:\worker\repos\...

 Build/run with Docker or Python/Node from old rig, triggered by SSH

Pattern you’ll use constantly:

ssh oldrig "powershell -NoProfile -Command `"hostname; docker ps`""

You still want occasional manual access to the old rig (GUI/session-required)
Docker Desktop realities on Windows

Docker Desktop typically depends on a user session (tray app) even if the engine is running. Manual access is useful for:

 First-time Docker Desktop setup dialogs/settings

 Confirming “Start Docker Desktop on login” + “Use WSL2 engine”

 Any update prompts/restarts that block background operation

One-time OS/driver/admin chores

 Windows Update reboots / interactive prompts

 GPU driver installers (if you update them)

 Confirming power settings, auto-login (optional), and desktop startup behavior

Troubleshooting

 If Docker Desktop gets “stuck starting,” the fastest fix is often GUI-level restart/check.

How to minimize manual time on the old rig

 Keep Synergy as your “emergency hands” access

 Enable RDP (Pro) so you don’t need the physical monitor most of the time

 Add Portainer (optional) so container management is browser-based

 Make sure Docker Desktop is configured to start on login

 Put watchers under Scheduled Tasks so they survive reboots without you touching anything