# Cadence

Personal intelligence system — a daily note pipeline that generates, negotiates, and tracks daily plans.

**Status:** Project initialization (skeleton only, implementation begins next session)

## Overview

Every morning, a VPS runs an automated pipeline that:
1. Fetches news (AI industry, Anthropic, relevant topics)
2. Retrieves today's calendar events
3. Collects your task list and training plan
4. Calls an AI agent to generate a structured daily draft

You then open a mobile-first webapp to:
- **Review** the draft
- **Negotiate** with an AI agent to adjust the plan
- **Approve** the plan, which writes your daily note
- **Track** tasks throughout the day (mark complete, drop, defer, add notes)

All decisions and outcomes are captured as structured JSON to feed a long-term user model.

## Project Structure

```
cadence/
  scripts/          # Pipeline scripts (fetch, context, agent, config)
  api/              # FastAPI server + routes
  webapp/            # Frontend: HTML/CSS/JS SPA
  tests/             # Test suite
  cadence.toml      # Configuration
  pyproject.toml    # Python dependencies
  README.md         # This file
  CLAUDE.md         # AI context + implementation guide
  IMPLEMENTATION_PLAN.md  # Phased build plan
```

## Quick Start

### Prerequisites
- Python 3.11+
- Google Calendar credentials (OAuth JSON)
- Anthropic API key

### Setup

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Initialize vault structure:**
   ```bash
   make init-vault
   ```

3. **Add credentials to `~/vault/.system/config/`:**
   - `google_credentials.json` — from Google Cloud Console
   - Set `ANTHROPIC_API_KEY` environment variable

4. **Edit `cadence.toml`** if your vault path differs from `~/vault`

### Development

- **Run tests:** `make test`
- **Start API server:** `make serve` (dev) or `make serve-prod`
- **Run pipeline:** `make pipeline`
- **Check code:** `make lint`

## Architecture

### Daily Lifecycle

```
06:00 cron → pipeline.py
  ├── fetch_all.py (news + calendar)
  ├── build_context.py (merge state)
  └── agent_daily_planner.py (generate draft)

API Server (8420)
  GET /api/today      → current draft or approved plan
  POST /api/negotiate → agent conversation exchange
  POST /api/approve   → lock plan, write daily note
  POST /api/tasks/:id → update task status
  GET /api/status     → system health

Webapp
  → morning: review → negotiate → approve
  → daytime: check off tasks, add notes
```

### Data Flow

- **VPS writes only to** `.system/` (internal state)
- **User-facing files** (`Daily/`, `data/tasks/`) written on approval
- **Vault synced** via Syncthing (data only, not code)
- **Code deployed** via git push (separate from vault)

## Implementation Plan

The project follows a phased build (10 phases, ~17-28 days):

1. **Phase 1** — Schemas + test infrastructure
2. **Phase 2** — Context builder
3. **Phase 3** — Calendar pipeline
4. **Phase 4** — News pipeline
5. **Phase 5** — Agent + draft generation
6. **Phase 6** — API server + endpoints
7. **Phase 7** — Negotiation system
8. **Phase 8** — Webapp (both screens)
9. **Phase 9** — Automation + hardening
10. **Phase 10** — Stabilization (7 consecutive days = MVP done)

See `IMPLEMENTATION_PLAN.md` for details.

## Configuration

Edit `cadence.toml` to customize:
- Vault path
- Cron schedule
- API port
- Claude model + token limit
- Log level

## Testing

```bash
make test              # Fast tests only
make test-all          # All tests including slow ones
make test-api          # API endpoint tests
make test-tasks        # Task lifecycle tests
```

## Deployment

1. Push code to VPS: `git push origin main`
2. Set up cron: `crontab -e` → `0 6 * * * cd ~/cadence && make pipeline`
3. Run API as systemd service:
   ```ini
   [Unit]
   Description=Cadence API
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8420
   WorkingDirectory=/home/shu/cadence
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
4. Enable Syncthing to sync `~/vault` across devices
5. Configure Tailscale/WireGuard for remote access

## Roadmap

### MVP (This Phase)
- ✅ Skeleton + configuration
- ⬜ Schemas + test infrastructure
- ⬜ News + calendar pipeline
- ⬜ Draft generation via Claude
- ⬜ Interactive negotiation
- ⬜ Mobile webapp
- ⬜ Daily automation

### Post-MVP (Phase B+)
- Weekly reflection agent (patterns from 7 days)
- User model (long-term behavior prediction)
- Proactive suggestions (energy/defer patterns)
- Training coach integration
- Event-driven architecture

## License

MIT
