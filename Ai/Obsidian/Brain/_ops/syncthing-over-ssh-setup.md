# Syncthing Over SSH (New Rig ↔ Old Rig)

Use your existing SSH setup to tunnel Syncthing instead of opening extra firewall ports.

## Prerequisites

- SSH access: new rig → old rig as `worker@192.168.40.25`
- Syncthing installed on **both** machines
- Old rig (WORKER-NODE) runs Syncthing and listens on port 22000

---

## How It Works

Syncthing needs one working connection. An **SSH local forward** on the new rig tunnels local port 22001 → old rig’s Syncthing (127.0.0.1:22000). Syncthing on the new rig then reaches the old rig via `tcp://127.0.0.1:22001`.

```
[New Rig Syncthing] --connect--> [127.0.0.1:22001] --SSH tunnel--> [Old Rig Syncthing :22000]
```

Once connected, the session is bidirectional. No reverse tunnel needed.

---

## Step 1: Start the SSH Tunnel

On the **new rig**, run:

```powershell
ssh -L 22001:127.0.0.1:22000 worker@192.168.40.25 -N
```

- `-L 22001:127.0.0.1:22000`: forward local 22001 to old rig’s Syncthing
- `-N`: no remote shell (tunnel only)

Keep this terminal open. Or use the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File "E:\Repos\_scripts\syncthing_ssh_tunnel.ps1"
```

---

## Step 2: Add Old Rig in Syncthing (New Rig)

1. Open Syncthing UI: http://127.0.0.1:8384
2. **Settings → Connections**: enable “Enable NAT traversal” (default)
3. **Add Remote Device**:
   - Paste the old rig’s **Device ID** (from its Syncthing UI)
   - Or: **Add Device** → Advanced → Addresses → add `tcp://127.0.0.1:22001`
   - Save

---

## Step 3: Add New Rig in Syncthing (Old Rig)

On the old rig’s Syncthing UI:

1. Add the new rig’s Device ID
2. If the tunnel is running, the new rig will connect to the old rig and the link will establish

If the old rig can reach the new rig directly (same LAN, no firewall blocking 22000), you can also add `tcp://192.168.40.76:22000` as a fallback.

---

## Step 4: Shared Folders

Create shared folders as usual. Example for `E:\Repos`:

| Machine  | Folder Path        | Folder ID | Share With   |
|----------|--------------------|-----------|--------------|
| New rig  | E:\Repos           | repos     | Old rig      |
| Old rig  | E:\Repos (or equiv)| repos     | New rig      |

Same for `E:\Repos\Ai\Obsidian\Brain` if you want the vault synced.

---

## Auto-Start Tunnel (Optional)

Use **autossh** (if installed) or a **Windows Scheduled Task** to run the tunnel at logon. The helper script can be run at startup.

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| Tunnel dies | Keep the SSH session alive; use `autossh` or a persistent task |
| “Connection refused” | Syncthing must be running on the old rig and listening on 22000 |
| Devices don’t connect | Ensure the tunnel is running before adding the address; restart Syncthing on the new rig |
