# Cadence Deployment Guide

This guide covers setting up Cadence for daily use on your machine or VPS. The system runs a cron job at 6:00 AM to generate the daily draft, and a systemd service to keep the API server running 24/7.

## Prerequisites

- **Python 3.11+** — check with `python3 --version`
- **Node.js 18+** — for building the webapp (check with `node --version`)
- **pip** — Python package manager
- **git** — for cloning the repository
- **Anthropic API key** — get from https://console.anthropic.com
- **Google Calendar credentials** — OAuth2 setup (see step 4)
- **systemd** — for running the API server as a service (native Linux or WSL2 with `systemd=true`)
- **cron** — for scheduling the daily pipeline (usually pre-installed)

## Step 1: Clone & Install Dependencies

```bash
# Clone the repository
git clone https://github.com/anthropics/cadence.git
cd cadence

# Install Python dependencies
pip install -e ".[dev]"

# Install and build the webapp
make webapp-install
make webapp-build

# Verify build
ls -lh webapp/dist/
# Should show index.html, bundle files, etc.
```

## Step 2: Initialize Vault Directory

The vault is where all user data lives (notes, tasks, daily plans). It's separate from the code repo and synced via Syncthing.

```bash
make init-vault

# Verify structure
ls -la ~/vault/.system/
# Should show: config, context, drafts, logs, model, state
```

## Step 3: Set Up Google Calendar

Cadence fetches your calendar events to build the daily plan.

1. **Create OAuth2 credentials:**
   - Go to https://console.cloud.google.com/
   - Create a new project called "Cadence"
   - Enable "Google Calendar API"
   - Create an OAuth2 "Desktop application" credential
   - Download the JSON file (called `client_secret_...json`)

2. **Place credentials in vault:**
   ```bash
   cp ~/Downloads/client_secret_*.json ~/vault/.system/config/google_credentials.json
   ```

3. **Test the calendar fetcher:**
   ```bash
   python3 -m scripts.fetch.calendar_fetcher
   # First run: opens browser for OAuth consent
   # Subsequent runs: uses stored token (auto-refreshes)
   # Check output: ~/vault/.system/state/calendar_state.json
   ```

## Step 4: Set Anthropic API Key

The pipeline calls Claude API to generate daily plans.

```bash
# Option A: Environment variable (temporary, for testing)
export ANTHROPIC_API_KEY="sk-ant-..."
make pipeline

# Option B: Systemd environment (persistent, for production)
# Create ~/.config/cadence/api_key with your key
mkdir -p ~/.config/cadence
echo "sk-ant-..." > ~/.config/cadence/api_key
chmod 600 ~/.config/cadence/api_key

# Update systemd service to use it (edit /etc/systemd/system/cadence-api.service)
# Uncomment line: Environment=ANTHROPIC_API_KEY=%h/.config/cadence/api_key
```

## Step 5: Test Pipeline Locally

Before automating, run the full pipeline manually:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
make pipeline

# Check output
cat ~/vault/.system/logs/pipeline.log
cat ~/vault/.system/drafts/today_draft.json | jq .
```

Expected output:
- `pipeline.log` — detailed log of each pipeline step
- `today_draft.json` — JSON with news, schedule, tasks, training
- `day_state.json` — status set to "draft_pending"

## Step 6: Start the API Server

The API server serves the webapp and handles negotiation, approval, task tracking.

```bash
# Development mode (with auto-reload)
make serve

# In another terminal, test the API
curl http://localhost:8420/api/status
# Returns: { "calendar_fresh": true, "news_fresh": true, ... }
```

Open browser: http://localhost:8420/app/
- Should show "Morning Review" screen with today's draft
- Can negotiate, approve, track tasks

## Step 7: Set Up Systemd Service (Production)

To run the API server as a background service that auto-restarts on failure:

### WSL2 Users: Enable Systemd

WSL2 doesn't have systemd by default. Enable it:

```bash
# Edit /etc/wsl.conf
sudo nano /etc/wsl.conf

# Add these lines:
[boot]
systemd=true

# Save and exit WSL (from PowerShell):
# wsl.exe --shutdown

# Restart WSL:
# Open a new terminal and run: wsl
```

### Install the Service

```bash
# Copy systemd unit to system directory and enable
make install-service

# Verify installation
sudo systemctl status cadence-api
# Should show: "enabled" and "active"

# View logs
journalctl -u cadence-api -f
# (Press Ctrl+C to exit)

# Manual commands
sudo systemctl start cadence-api    # Start the service
sudo systemctl stop cadence-api     # Stop the service
sudo systemctl restart cadence-api  # Restart the service
sudo systemctl enable cadence-api   # Auto-start on boot
sudo systemctl disable cadence-api  # Don't auto-start
```

## Step 8: Set Up Cron Job

To run the pipeline automatically every day at 6:00 AM:

```bash
# Install cron entry
make setup-cron

# Verify it was added
crontab -l | grep cadence
# Should show: 0 6 * * * cd /home/shu/projects/Cadence && make pipeline >> ...

# Manual cron editing (if needed)
crontab -e
# Edit, save (Ctrl+O, Enter, Ctrl+X in nano)
```

The cron job will run at 6:00 AM UTC (adjust the `cron_hour` in `cadence.toml` if you want a different time).

## Step 9: Syncthing Configuration (Optional)

Syncthing lets you sync the vault between devices (laptop, phone, VPS) without a cloud service.

1. **Install Syncthing** on all devices:
   ```bash
   # macOS
   brew install syncthing

   # Linux
   sudo apt install syncthing

   # Windows: download from https://syncthing.net/download/
   ```

2. **Start Syncthing and open UI** (default: `http://localhost:8384`):
   ```bash
   syncthing
   # Open http://localhost:8384 in browser
   ```

3. **Add vault folder**:
   - Click "Add Folder"
   - Path: `/home/shu/vault`
   - Folder Label: "Cadence Vault"
   - Folder ID: `cadence-vault`
   - Click "Save"

4. **Add remote devices**:
   - Get the Device ID from each device (shown in Syncthing UI)
   - Go back to Settings and pair devices
   - Add the folder to remote devices and accept the share

5. **Ignore patterns** (to avoid syncing code repo):
   ```
   .git/
   .venv/
   __pycache__/
   *.pyc
   webapp/node_modules/
   webapp/dist/
   ```

Now the vault syncs across all your devices automatically.

## Step 10: Tailscale Configuration (Optional)

Tailscale provides a private mesh network so you can access the API from anywhere securely.

1. **Install Tailscale**:
   ```bash
   # macOS
   brew install tailscale

   # Linux
   sudo apt install tailscale

   # Run the daemon
   sudo tailscaled &
   ```

2. **Authenticate**:
   ```bash
   sudo tailscale up
   # Opens browser to authenticate
   ```

3. **Get your Tailscale IP**:
   ```bash
   tailscale ip -4
   # Example: 100.64.1.23
   ```

4. **Update cadence.toml**:
   ```toml
   allowed_origins = [
     "http://localhost:8420",
     "http://100.64.1.23:8420"
   ]
   ```

5. **Restart API server**:
   ```bash
   sudo systemctl restart cadence-api
   # Or: make serve
   ```

Now you can access the API from any device on your Tailscale network:
```bash
# From another device
curl http://100.64.1.23:8420/api/status
```

## Step 11: Verification Checklist

Run this checklist to verify everything is working:

```bash
# 1. Vault initialized
ls -la ~/vault/.system/state/
# Should have: calendar_state.json, news_state.json, day_state.json, etc.

# 2. API server running
curl http://localhost:8420/api/status
# Should return JSON with freshness info

# 3. Systemd service status
sudo systemctl status cadence-api
# Should show: "active (running)"

# 4. Cron entry installed
crontab -l | grep cadence
# Should show the pipeline entry

# 5. Recent logs
tail -20 ~/vault/.system/logs/pipeline.log
tail -20 ~/vault/.system/logs/api.log

# 6. Make status command
make status
# Shows systemd, cron, and vault status

# 7. Run pipeline manually
export ANTHROPIC_API_KEY="sk-ant-..."
make pipeline
# Should complete without errors

# 8. Open webapp
# http://localhost:8420/app/ in browser
# Should show the draft for today
```

## Troubleshooting

### Systemd Service Won't Start
```bash
# View detailed error
journalctl -u cadence-api --no-pager | tail -50

# Common issues:
# 1. Working directory doesn't exist: check path in cadence-api.service
# 2. ANTHROPIC_API_KEY not set: set in environment
# 3. Vault path missing: run make init-vault
```

### Pipeline Fails at Cron Time
```bash
# Check cron logs
tail -f /var/log/syslog | grep CRON

# Run pipeline manually to see the error
make pipeline

# Check vault/system/logs/pipeline.log for details
tail -100 ~/vault/.system/logs/pipeline.log
```

### Google Calendar API Errors
```bash
# Re-authenticate
rm ~/.config/gcloud/credentials.json  # Force re-auth
python3 -m scripts.fetch.calendar_fetcher

# Check credentials file
ls -la ~/vault/.system/config/google_credentials.json
```

### API Server Crashes
```bash
# Check systemd logs
journalctl -u cadence-api -f

# Restart manually
sudo systemctl restart cadence-api

# Check port 8420 is available
lsof -i :8420
```

## Advanced: Custom Cron Time

By default, the pipeline runs at 6:00 AM UTC. To change it:

```bash
# Edit cadence.toml
nano cadence.toml

# Change cron_hour:
# [fetch]
# cron_hour = 7  # For 7:00 AM

# Then update the cron entry
make setup-cron  # Re-install
```

## Advanced: Update Cadence

To pull the latest code:

```bash
cd ~/projects/Cadence
git pull origin main

# Rebuild if webapp changed
make webapp-build

# Restart API server
sudo systemctl restart cadence-api
```

## Next Steps

1. Wait for 6:00 AM tomorrow (or run `make pipeline` manually)
2. Open webapp at http://localhost:8420/app/
3. Review the draft, negotiate if needed, approve
4. Track tasks throughout the day
5. Check `/home/shu/vault/Daily/YYYY-MM-DD.md` for your approved note
6. Review decisions in `/home/shu/vault/.system/state/decisions.json`

## Getting Help

- **Logs**: Check `/home/shu/vault/.system/logs/pipeline.log` and `api.log`
- **API status**: `curl http://localhost:8420/api/status`
- **Systemd status**: `sudo systemctl status cadence-api`
- **Code issues**: See `CLAUDE.md` for project structure and conventions
