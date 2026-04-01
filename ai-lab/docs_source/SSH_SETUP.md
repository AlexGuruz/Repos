# SSH setup (main ↔ worker)

Canonical worker identity for this repo is defined in `docs_source/WORKER_CURRENT.md`.

## Main rig

- Ensure SSH client is available (OpenSSH on Windows, or PuTTY).
- Use key-based auth. Generate key if needed: `ssh-keygen -t ed25519 -f agent_main_key -C agent-main`.
- Add worker host to `~/.ssh/config` (or equivalent):

```
Host worker
  HostName worker-node
  User worker
  IdentityFile ~/.ssh/agent_main_key
```

- Test: `ssh worker "echo ok"`. Success/failure can be recorded for health checks.

## Worker rig

- SSH server running (sshd).
- Ensure user `worker` exists (or update `WORKER_CURRENT.md` first if changing identity).
- Add main's public key to `worker@worker-node:~/.ssh/authorized_keys`.
- Restrict to agent-only commands if desired (authorized_keys command=).

## Health check

Optional script (run from main): SSH to worker with short timeout, run `echo ok`, record result in observability or pass to health collector. See `observability/collect_health.py`.
