# Phase 9 Learning: Automation + Hardening

**Goal:** Understand the systems that keep Cadence running reliably — cron for daily automation, systemd for service management, logging for debugging, and deployment for getting the app into production.

---

## 1. Systemd Fundamentals

**What it is:** Systemd is the system and service manager for modern Linux. It replaces older `init` systems and handles service lifecycle, startup dependencies, and automatic restarts.

**Key concepts:**
- **Unit file** — Configuration for a service (stored in `/etc/systemd/system/` or `/usr/lib/systemd/system/`)
- **Service** — A daemon or program that runs in the background
- **Enable** — Register the service to start automatically on boot
- **Start/Stop/Restart** — Manual control of a service

**Cadence systemd file** (`cadence-api.service`):
```ini
[Unit]
Description=Cadence API Server
After=network.target                    # Start after network is up

[Service]
Type=simple                             # Simple foreground service
User=shu                                # Run as user 'shu'
WorkingDirectory=/home/shu/projects/Cadence
ExecStart=/usr/local/bin/uvicorn api.server:app --port 8420
Restart=on-failure                      # Auto-restart if process crashes
RestartSec=5                            # Wait 5 seconds before restarting

[Install]
WantedBy=multi-user.target              # Include in multi-user boot target
```

**Common commands:**
```bash
sudo systemctl start cadence-api        # Start the service
sudo systemctl stop cadence-api         # Stop the service
sudo systemctl restart cadence-api      # Restart
sudo systemctl enable cadence-api       # Auto-start on boot
sudo systemctl disable cadence-api      # Don't auto-start
sudo systemctl status cadence-api       # Show current status
sudo systemctl daemon-reload            # Reload unit files after edit
journalctl -u cadence-api -f            # View logs in real-time
journalctl -u cadence-api --since 1h    # Last hour of logs
```

**Why use systemd instead of manual `nohup` or screen?**
- **Auto-restart on crash** — keeps your app alive even after unexpected failures
- **Boot integration** — automatically starts at system startup
- **Dependency management** — `After=network.target` ensures network is ready
- **Centralized logging** — all output goes to systemd journal (searchable, rotated)
- **Signal handling** — graceful shutdown on `systemctl stop`

---

## 2. WSL2 + Systemd

**The challenge:** Windows Subsystem for Linux (WSL2) runs a lightweight Linux kernel but traditionally doesn't start systemd. This matters because Cadence expects to run services via systemd.

**WSL2 systemd support (Windows 11 build 22000+):**
WSL2 now supports systemd natively with a config change.

**Enable systemd in WSL2:**
1. Edit `/etc/wsl.conf`:
   ```bash
   sudo nano /etc/wsl.conf
   ```
   Add:
   ```ini
   [boot]
   systemd=true
   ```

2. Exit WSL and restart from PowerShell:
   ```powershell
   wsl.exe --shutdown
   wsl
   ```

3. Verify systemd is running:
   ```bash
   systemctl status
   # Should show: System has not been booted with systemd as init system
   # (this is normal in WSL2 — systemd is running but not PID 1)
   ```

**Differences in WSL2:**
- Systemd is NOT PID 1 (the Linux kernel is)
- But all systemctl commands work normally
- Services run in the same user session
- Journalctl logging works the same

**When to use WSL2 systemd:**
- **Development:** Test the exact systemd setup you'll use in production
- **Automation:** Same cron + systemd workflow as production VPS

**Limitations:**
- Systemd services don't survive WSL restart (system resets)
- For persistent services, keep them running manually with `make serve` during development

---

## 3. Cron Syntax & Scheduling

**What it is:** Cron is a time-based job scheduler. It runs commands at specified times (daily, weekly, monthly, etc.).

**Cadence pipeline runs at 6:00 AM daily via cron.**

**Cron entry format:**
```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-7, 0=Sunday, 7=Sunday)
│ │ │ │ │
0 6 * * * /path/to/command
```

**Cadence cron entry:**
```
0 6 * * * cd /home/shu/projects/Cadence && make pipeline >> ~/vault/.system/logs/pipeline.log 2>&1
```

Breaking it down:
- `0` — minute 0 (top of the hour)
- `6` — hour 6 (6 AM in UTC, adjust if needed)
- `*` — every day of the month
- `*` — every month
- `*` — every day of the week
- `cd .../Cadence && make pipeline` — the command to run
- `>> ...pipeline.log 2>&1` — append stdout AND stderr to log file

**Common cron patterns:**
```
0 6 * * *        # Daily at 6 AM
0 */4 * * *      # Every 4 hours
0 0 * * 0        # Every Sunday at midnight
0 9,17 * * *     # At 9 AM and 5 PM
*/5 * * * *      # Every 5 minutes
```

**Management:**
```bash
crontab -l       # List current cron entries
crontab -e       # Edit cron entries (opens editor)
crontab -r       # Remove all cron entries
```

**Cron logs:**
```bash
# On Linux (not WSL2 by default)
tail /var/log/syslog | grep CRON

# More reliable: check your task's output file
tail -f ~/vault/.system/logs/pipeline.log
```

**Why cron instead of `at` or `systemd.timer`?**
- **Ubiquitous** — available on every Unix/Linux system
- **Simple** — one-liners are easy to understand
- **Reliable** — battle-tested since 1975
- **Standard** — system administrators expect it

**Gotchas:**
1. **Timezone:** Cron uses the system timezone. Check with `date` or `timedatectl`.
2. **Environment variables:** Cron has a minimal environment (no $PATH expansion). Use absolute paths.
3. **Output:** If a command produces output, cron will email it. Redirect to a file with `>> logfile 2>&1`.
4. **Permissions:** The user running cron must have permission to execute the command and write the log.

---

## 4. Python Logging Module

**What it is:** Python's built-in `logging` module provides structured, flexible logging for applications. Better than `print()` because logs can go to files, be filtered by severity, and include timestamps.

**Basic concepts:**
- **Logger** — the object you use to log messages (`logging.getLogger(__name__)`)
- **Handler** — determines where logs go (console, file, email, etc.)
- **Formatter** — controls the format of each log line
- **Level** — severity: DEBUG, INFO, WARNING, ERROR, CRITICAL

**Cadence setup:**
```python
import logging
import logging.handlers

def setup_logging(vault_path: str, log_level: str = "INFO") -> None:
    """Configure root logger with file handlers."""
    logs_dir = Path(vault_path) / ".system" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    # File handler (rotates after 1MB)
    handler = logging.handlers.RotatingFileHandler(
        logs_dir / "pipeline.log",
        maxBytes=1_000_000,
        backupCount=3
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
```

**Using the logger:**
```python
logger = logging.getLogger(__name__)

logger.debug("Detailed info, usually disabled in production")
logger.info("Informational message — pipeline is running")
logger.warning("Warning — something might be wrong")
logger.error("Error — something went wrong but we recovered")
logger.critical("Critical — the app might crash")
```

**Log levels:**
- `DEBUG` — Fine-grained diagnostic information (disabled by default)
- `INFO` — General informational messages
- `WARNING` — Warning messages (default minimum level)
- `ERROR` — Error messages (something went wrong)
- `CRITICAL` — Severe messages (app might crash)

**Why logging instead of print?**
1. **Severity filtering** — show only relevant messages
2. **Timestamps** — know when things happened
3. **Module tracking** — know which part of the code logged
4. **File output** — logs persist for debugging
5. **Structured format** — easy to parse and analyze

---

## 5. Log Rotation & File Management

**The problem:** If your application runs 24/7 and logs everything, log files grow unbounded (GB per day). Eventually, the disk fills up and the app crashes.

**Solution: Log rotation** — automatically archive old logs and start fresh.

**Cadence uses `RotatingFileHandler`:**
```python
handler = logging.handlers.RotatingFileHandler(
    "pipeline.log",
    maxBytes=1_000_000,     # 1 MB
    backupCount=3           # Keep 3 old files
)
```

**How it works:**
1. Write to `pipeline.log`
2. When file reaches 1 MB, rename it to `pipeline.log.1`
3. Previous `.1` becomes `.2`, etc.
4. Keep only 3 backups (delete `.4` and beyond)
5. Start fresh `pipeline.log`

**Example (after rotation):**
```
pipeline.log       (current, < 1 MB)
pipeline.log.1     (previous, 1 MB, most recent)
pipeline.log.2     (older, 1 MB)
pipeline.log.3     (oldest, 1 MB, deleted when new rotation happens)
```

**Advantages:**
- **Bounded disk usage** — predictable space (maxBytes × backupCount)
- **History** — old logs kept for troubleshooting
- **Automatic** — no manual intervention needed

**Alternatives:**
1. **`TimedRotatingFileHandler`** — rotate by time (daily, hourly) instead of size
2. **`logrotate`** — system-level log rotation (more flexible, needs cron)
3. **Syslog** — let the system handle rotation

**Cadence choice:** `RotatingFileHandler` because:
- Size-based rotation is more predictable
- Works on any OS (Windows, macOS, Linux)
- No external tools needed
- Simple to understand

---

## 6. Syncthing Concepts

**What it is:** Syncthing is a peer-to-peer file synchronization tool. It syncs your vault across multiple devices (laptop, phone, VPS) without a central cloud server.

**Key terms:**
- **Device** — a computer or phone running Syncthing
- **Folder** — a directory being synced (e.g., `~/vault/`)
- **Device ID** — unique identifier for a device (looks like a long hash)
- **Connection** — direct or relayed peer-to-peer link between devices

**How Syncthing works:**
1. Each device runs Syncthing daemon
2. Devices discover each other (via discovery server or manual)
3. When a file changes, the change is sent to other devices
4. Conflicts handled via first-write-wins or by creating `.sync.conflict` copies

**Cadence setup:**
```
VPS: ~/vault/      ↔ Syncthing ↔  Laptop: ~/vault/
                    ↔ Syncthing ↔  Phone: ~/vault/
```

**Ignore patterns (to avoid syncing code):**
```
.git/
.venv/
__pycache__/
.DS_Store
webapp/node_modules/
webapp/dist/
```

**Security:**
- All transfers encrypted (TLS)
- Device IDs are verified before pairing
- You control which devices can access your vault
- No data goes through Syncthing servers (only metadata)

**Advantages over cloud storage:**
- **Privacy** — full control, no cloud company reading your data
- **Offline** — works without internet between devices
- **Speed** — direct device-to-device is faster than cloud
- **Cost** — free, open source

**Trade-offs:**
- **Sync conflicts** — if you edit the same file on two devices, conflict resolution is manual
- **Discovery** — requires devices to find each other (can use public discovery server)
- **Bandwidth** — syncs everything, not selective

---

## 7. Tailscale: Private Mesh Networking

**What it is:** Tailscale is a VPN that creates a private mesh network. It lets you access your devices securely from anywhere without port forwarding or complex firewall rules.

**Key concepts:**
- **Tailnet** — your personal Tailscale network (all your devices)
- **Tailscale IP** — unique IP on your private network (e.g., `100.64.1.23`)
- **MagicDNS** — DNS names for devices (e.g., `mycomputer.tail12345.ts.net`)
- **ACL** — access control rules (who can connect to what)

**How Tailscale works:**
1. Install Tailscale on all devices
2. Authenticate with Tailscale account
3. Devices automatically discover each other
4. WireGuard encryption between devices (peer-to-peer when possible, relayed if behind NAT)

**Cadence use case:**
```
At home:
- Open http://localhost:8420/app/

On the road (with Tailscale):
- Open http://100.64.1.23:8420/app/   (VPS running Cadence)
```

**Setup:**
```bash
sudo tailscale up
# Authenticates and joins your Tailnet

tailscale ip -4
# Returns your Tailscale IP (e.g., 100.64.1.23)

# Add to cadence.toml:
allowed_origins = ["http://localhost:8420", "http://100.64.1.23:8420"]
```

**Advantages:**
- **No port forwarding** — Tailscale handles NAT traversal
- **Encrypted** — all traffic is encrypted by default
- **No DNS setup** — Tailscale provides DNS names
- **Easy** — install and click "Authenticate"

**Security model:**
- Authentication via Tailscale account (2FA recommended)
- Private IP addresses only (no exposure to internet)
- ACLs can restrict access (e.g., "only my devices")

---

## 8. CORS: Cross-Origin Resource Sharing

**What it is:** CORS is a browser security feature. When JavaScript on one domain tries to fetch from another domain, the browser checks if the server allows it.

**Cadence scenario:**
```
Browser loads:  http://100.64.1.23:8420/app/   (React app)
JavaScript calls: http://100.64.1.23:8420/api/today  (same domain → OK)

BUT:
Browser loads:  http://someoneelse.com
JavaScript calls: http://100.64.1.23:8420/api/today  (cross-origin → BLOCKED)
```

**CORS headers:**
The server must send:
```
Access-Control-Allow-Origin: http://100.64.1.23:8420
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

**Cadence setup:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8420", "http://100.64.1.23:8420"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Why not just allow everything?**
```python
allow_origins=["*"]  # ❌ DANGEROUS
```
This allows malicious websites to call your API. Instead, whitelist safe origins:
```python
allow_origins=[
    "http://localhost:8420",           # Local development
    "http://100.64.1.23:8420",         # Tailscale IP
]
```

**Common mistakes:**
1. **Forgetting http://** — CORS is protocol-sensitive: `http://` ≠ `https://`
2. **Port mismatch** — `localhost:8420` ≠ `localhost:3000`
3. **Wildcard trap** — `*` allows anyone to call your API (security risk)

---

## 9. Deployment Checklist Pattern

**What it is:** A structured approach to deployment documentation. Instead of narrative prose, use a checklist that guides users through each step, with verification at each stage.

**Cadence DEPLOY.md pattern:**
1. **Prerequisites** — what the user must have before starting
2. **Step-by-step instructions** — numbered, with bash commands
3. **Verification** — commands to verify each step worked
4. **Troubleshooting** — common errors and how to fix them
5. **Advanced** — optional customizations

**Why this pattern?**
- **Skimmable** — users can quickly find their situation
- **Testable** — each step has a verification command
- **Reproducible** — exact bash commands, not abstract descriptions
- **Fault-tolerant** — troubleshooting section catches issues early

**Example checklist entry:**
```markdown
## Step 6: Verify Cron

Run these commands to verify the cron job was installed:

1. List cron entries:
   crontab -l | grep cadence
   # Expected output: 0 6 * * * cd /home/shu/projects/Cadence && make pipeline...

2. Check cron logs:
   tail -f /var/log/syslog | grep CRON

3. Test manually:
   make pipeline
   # Should complete without errors
```

**When DEPLOY.md helps:**
- **New developers** — clear path from zero to running
- **Operations** — step-by-step guides reduce mistakes
- **Troubleshooting** — dedicated section for common issues
- **Reproducibility** — exact commands, no guessing

---

## Key Takeaways

| Topic | Purpose | Cadence Usage |
|---|---|---|
| **Systemd** | Service management | Keep API server running 24/7 |
| **WSL2 + Systemd** | Development on Windows | Test exact production setup locally |
| **Cron** | Scheduled tasks | Run pipeline daily at 6:00 AM |
| **Logging** | Application observability | Track pipeline and API behavior |
| **Log Rotation** | Disk space management | Prevent unbounded log growth |
| **Syncthing** | Data synchronization | Sync vault across devices |
| **Tailscale** | Remote access | Access API from anywhere securely |
| **CORS** | Browser security | Whitelist safe origins for API calls |
| **Deployment Guide** | Reproducible setup | Clear path from zero to production |

---

## Further Reading

- **Systemd**: https://systemd.io/
- **Cron**: `man 5 crontab`
- **Python Logging**: https://docs.python.org/3/library/logging.html
- **Syncthing**: https://syncthing.net/
- **Tailscale**: https://tailscale.com/
- **Cadence DEPLOY.md**: See main repository
