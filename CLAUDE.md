# Cadence: AI Context & Implementation Guide

This document captures architecture, conventions, and project state for Claude and human developers.

## Project Identity

- **Name:** Cadence (formerly Aegis)
- **Scope:** MVP daily intelligence note + interactive negotiation + task tracking
- **Status:** Project initialization (skeleton files created, implementation begins next session)
- **Version:** 0.3.0

## System Overview

**Objective:** Every morning, a draft daily plan is ready before wake-up. User opens webapp, negotiates with AI, approves plan, and goes. Throughout the day, user marks tasks and adds notes. All decisions captured as structured JSON.

**Core Components:**
1. **Pipeline (VPS, cron 06:00):** Fetch news/calendar → build context → call AI agent → produce draft
2. **API (FastAPI, port 8420):** 6 endpoints for review, negotiation, approval, task tracking
3. **Webapp (SPA, HTML/CSS/JS):** Morning review screen, active day screen, mobile-first
4. **Vault (Syncthing, `~/vault/`):** User data (notes, tasks, training), synced but separate from code

## Architecture Layers

### VPS Pipeline (scripts/)

```
fetch_all.py (cron entry)
  ├── fetch/news_fetcher.py → vault/.system/state/news_state.json
  ├── fetch/calendar_fetcher.py → vault/.system/state/cal_state.json
  └── build_context.py → vault/.system/context/daily_context.md

agent_daily_planner.py → calls Claude → vault/.system/drafts/today_draft.json

pipeline.py (orchestration)
```

**Cron line:**
```bash
0 6 * * * cd /home/shu/cadence && make pipeline
```

### API Server (api/)

FastAPI on port 8420, serves:
- **GET /api/today** — current draft or approved plan
- **POST /api/negotiate** — one negotiation round (user text → agent response + mutations)
- **POST /api/approve** — lock plan, write daily note, start task tracking
- **POST /api/tasks/:id** — update task (complete, drop, defer, notes)
- **POST /api/tasks** — add ad-hoc task
- **GET /api/status** — system health + state freshness

Webapp served as static files at `/app`.

### Webapp (webapp/)

Single HTML file (SPA), vanilla JS, no build step.

**Screens:**
- **Morning:** Draft review, news cards, schedule, tasks, training, negotiation chat, approve button
- **Daytime:** Task checklist with complete/drop/defer/notes, remaining schedule, day stats

**Interactions:** All hit API immediately, no save button. State server-authoritative.

### Vault Structure

```
~/vault/
  Daily/                           # Approved daily notes (Obsidian)
    YYYY-MM-DD.md
  data/
    tasks/{inbox,today,backlog}.md
    training/{plan,log}.md
  .system/                         # VPS writes here ONLY
    state/
      {news,calendar,day_state,decisions}.json
    context/
      daily_context.md
    drafts/
      today_draft.json
    config/
      {interests,daily_template,negotiation_template}.md
      google_credentials.json
    logs/
      {fetch,agent,api}.log
    model/
      user_model.json              # Post-MVP
```

**Critical invariant:** VPS writes only to `.system/`. User-facing files written on approval.

## Data Models (Pydantic, schemas.py)

All models in `scripts/schemas.py`. Key ones:

### Calendar
- `CalendarEvent` — title, start, end, location, all_day
- `CalendarState` — fetched_at, date, events[], tomorrow_preview[]

### News
- `NewsItem` — title, source, url, summary, topic, published, relevance (0-1)
- `NewsState` — fetched_at, items[], errors[]

### Tasks
- `Task` — id, text, source (today/carried_over/suggested/negotiation/ad_hoc), priority, status, notes, drop_reason, deferred_to
- `TaskStatus` enum: pending, completed, dropped, deferred
- `DayTasks` — date, tasks[]

### Day Lifecycle
- `DayStatus` enum: draft_pending, negotiating, active, completed
- `DayState` — date, status, draft_generated_at, negotiation_started_at, approved_at, completed_at

### Draft (JSON schema)
```json
{
  "schema_version": 1,
  "date": "YYYY-MM-DD",
  "generated_at": "ISO8601",
  "news": [{id, topic, headline, summary, url, relevance}],
  "schedule": [{id, time_start, time_end, title, location, all_day}],
  "tomorrow_preview": [{title, time_start, all_day}],
  "tasks": [{id, text, source, priority, status, completed_at, notes}],
  "training": {summary, plan_reference},
  "agent_suggestions": ["..."]
}
```

### Decisions (JSON schema)
```json
{
  "date": "YYYY-MM-DD",
  "negotiation_decisions": [
    {timestamp, action, target, reason, energy_note, context_tag, agent_suggestion}
  ],
  "task_outcomes": [
    {task_id, text, status, completed_at, notes, duration_estimate}
  ]
}
```

## API Spec (Detailed)

### GET /api/today
Returns JSON based on `day_state.json` status.

**Response (draft_pending):**
```json
{
  "status": "draft",
  "draft": { ...draft object... },
  "freshness": { "calendar": true, "news": true, "age_minutes": 15 }
}
```

**Response (active):**
```json
{
  "status": "active",
  "plan": { ...approved draft... },
  "tasks": { "date": "...", "tasks": [...] }
}
```

### POST /api/negotiate
Request: `{ "text": "user message" }`
Response: `{ "message": "agent response", "draft": { ...updated... }, "decisions": [...] }`

Extracts structured changes from agent response (via `<changes>` XML block), applies mutations to draft, records decisions.

### POST /api/approve
No request body needed.
Response: `{ "status": "approved", "note_path": "Daily/YYYY-MM-DD.md", "tasks": { ...DayTasks... } }`

Locks draft, writes daily note, updates day_state to `active`.

### POST /api/tasks/:id
Request: `{ "action": "complete" | "drop" | "defer", "reason": "...", "defer_to": "..." }`
Response: `{ "tasks": { ...updated DayTasks... } }`

- `complete` — sets completed_at timestamp
- `drop` — requires reason (422 if missing)
- `defer` — defer_to: "tomorrow", "backlog", or ISO date

### POST /api/tasks
Request: `{ "text": "...", "priority": "high" | "normal" | "low" }`
Response: `{ "task": { ...new Task... }, "tasks": { ...DayTasks... } }`

Creates ad-hoc task with source="ad_hoc".

### GET /api/status
Response: `{ "calendar_fresh": bool, "news_fresh": bool, "day_status": "...", "last_fetch": "...", "errors": [] }`

## Agent Prompts

### Daily Planner (`vault/.system/config/daily_template.md`)
- Input: `daily_context.md` (2000 token budget, merged from all state files)
- Output: **JSON only** (no markdown, no explanation)
- Behavior: 3-5 top-relevance news, chronological schedule, tasks from context, suggest 1-2 if light day, one-line training summary

### Negotiation (`vault/.system/config/negotiation_template.md`)
- System behavior: Accept user pushback immediately, no arguments, mention time blocks, 1 suggestion per response, 2-4 sentences max
- Response format includes `<changes>` XML block with JSON actions:
  ```xml
  <changes>
  {"action": "drop_task", "task_id": "t3"}
  {"action": "add_task", "text": "...", "priority": "high"}
  </changes>
  ```

## Configuration (cadence.toml)

```toml
[vault]
path = "/home/shu/vault"

[fetch]
cron_hour = 6
max_state_age_hours = 2

[agent]
runtime = "claude_api"
model = "claude-sonnet-4-6"
max_tokens = 1500
planner_prompt_path = "daily_template.md"
negotiation_prompt_path = "negotiation_template.md"

[api]
host = "0.0.0.0"
port = 8420
allowed_origins = ["http://localhost:8420"]

[logging]
level = "INFO"
```

## Implementation Phases

1. **Phase 1 (Day 1):** Schemas + test infrastructure
   - `scripts/schemas.py` — all Pydantic models + schema versions
   - `tests/conftest.py` — fixtures, config, mock runtime
   - `tests/fixtures/*.json` — sample state files

2. **Phase 2 (Day 2):** Context builder
   - `scripts/build_context.py` — merge state files → daily_context.md
   - Test: `tests/test_context_builder.py`

3. **Phase 3 (Days 3-4):** Calendar pipeline
   - `scripts/fetch/calendar_fetcher.py` — Google Calendar API → cal_state.json
   - `scripts/config.py` — load cadence.toml, Google credentials
   - Test: `tests/test_fetchers.py`

4. **Phase 4 (Days 4-6):** News pipeline
   - `scripts/fetch/news_fetcher.py` — RSS feeds → news_state.json
   - `scripts/fetch/fetch_all.py` — orchestrate both fetchers
   - Test: `tests/test_fetchers.py`

5. **Phase 5 (Days 6-7):** Agent + draft generation
   - `scripts/runtime.py` — AgentRuntime ABC + ClaudeRuntime
   - `scripts/agent_daily_planner.py` — call agent → draft JSON
   - `scripts/pipeline.py` — full orchestration
   - Tests: `test_agent_output.py`, `test_pipeline.py`

6. **Phase 6 (Days 8-10):** API server
   - `api/server.py` — FastAPI app, static mount, lifespan
   - `api/routes.py` — all endpoints
   - Tests: `test_api.py`, `test_task_lifecycle.py`, `test_day_lifecycle.py`

7. **Phase 7 (Days 10-12):** Negotiation
   - `api/negotiation.py` — NegotiationSession class
   - `/api/negotiate` endpoint
   - Tests: `test_negotiation.py`

8. **Phase 8 (Days 12-15):** Webapp
   - `webapp/index.html`, `styles.css`, `app.js`
   - Two screens: morning review + active day
   - Mobile-responsive, phone-friendly

9. **Phase 9 (Days 15-17):** Automation + hardening
   - Cron setup, systemd service
   - Syncthing + Tailscale configuration
   - Error handling, logging, state validation

10. **Phase 10 (Days 17-28):** Stabilization
    - Run daily for 7+ consecutive days
    - Fix issues, tune prompts
    - Declare MVP done when useful every day

## Conventions

### File Naming
- Python modules: `snake_case.py`
- Test files: `test_*.py`
- State files: `*_state.json`
- Drafts: `today_draft.json`
- Daily notes: `YYYY-MM-DD.md`

### Code Style
- Python 3.11+
- Pydantic v2 for validation
- Type hints on all functions
- 100-char line limit (ruff)
- No complex logic; graceful degradation on errors

### Error Handling
- Pipeline: If step fails, log and skip section (don't fail entire pipeline)
- API: Try/except, return 422 or 500 with error message
- Vault: Validate JSON against schema; return None if invalid
- Agent: JSON parse failure → fallback to raw context as text

### Testing
- Unit tests for schemas, fetchers, context builder
- Integration tests for pipeline, API, negotiation
- Fixtures in `tests/fixtures/`
- Slow tests marked `@pytest.mark.slow`

### Git Workflow
- Commit messages: "Phase N: Feature description"
- One feature per PR
- All tests pass before merge
- Code review for API/agent changes

## Key Files to Reference During Implementation

| Phase | Files |
|---|---|
| 1 | schemas.py, conftest.py, fixtures/ |
| 2 | build_context.py, test_context_builder.py |
| 3 | calendar_fetcher.py, config.py, test_fetchers.py |
| 4 | news_fetcher.py, fetch_all.py, test_fetchers.py |
| 5 | runtime.py, agent_daily_planner.py, pipeline.py, test_agent_output.py, test_pipeline.py |
| 6 | server.py, routes.py, test_api.py, test_task_lifecycle.py, test_day_lifecycle.py |
| 7 | negotiation.py, test_negotiation.py |
| 8 | webapp/*, no tests (manual testing on phone) |
| 9 | systemd config, crontab, Syncthing config, deployment guide |
| 10 | docs, user guide, post-MVP roadmap |

## Post-MVP Roadmap

### Phase A (2 weeks after stabilization)
- Weekly reflection agent: reads 7 days of notes/decisions/outcomes
- Updates `user_model.json` with patterns (energy, task types, deferrals, suggestion acceptance)

### Phase B
- Feed user_model to Daily Planner and Negotiation agents
- Agent references patterns in decisions

### Phase C (2-3 months)
- Proactive suggestions: predict deferrals, recommend schedule changes, detect interest shifts
- Training Coach integration
- Event-driven architecture

## Troubleshooting

### State files missing/stale
- Check `/home/shu/vault/.system/state/` for JSON files
- Check logs: `/home/shu/vault/.system/logs/pipeline.log`
- Run manually: `make fetch && make pipeline`

### API errors
- Check port 8420 is not in use: `lsof -i :8420`
- Check vault path in cadence.toml matches reality
- Check Anthropic API key is set: `echo $ANTHROPIC_API_KEY`

### Google Calendar fails
- Verify `google_credentials.json` in vault/.system/config/
- Check token refresh logic (auto-refresh should work)
- Run fetcher manually: `python -m scripts.fetch.calendar_fetcher`

### Webapp won't load
- Check API server is running: `curl http://localhost:8420/api/status`
- Check static mount: `curl http://localhost:8420/app/`
- Clear browser cache

## Next Session

The next session will:
1. Start Phase 1: Implement all schemas in `scripts/schemas.py`
2. Create test fixtures and conftest.py
3. Set up test infrastructure
4. Verify imports work

After Phase 1 is done and tested, subsequent sessions will follow phases 2-10 sequentially.
