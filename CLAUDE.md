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

**Phase 8.1+: React 18 + TypeScript + Tailwind + Vite build (replaced vanilla JS)**
- Modern SPA with feature-first component architecture
- TanStack Query for data fetching and cache management
- Instant data refresh on mutations (no `location.reload()`)
- TypeScript strict mode, full type safety

**Screens:**
- **No Draft:** "Waiting for draft" empty state (during morning pipeline)
- **Morning Review:** Draft review, news cards, schedule, tomorrow preview, tasks, training, negotiation chat, approve button
- **Active Day:** Task checklist with complete/drop/defer/notes, remaining schedule, day stats, inline task add, negotiation still available
- **Completed:** Celebration screen

**Interactions:** All hit API immediately, no save button. State server-authoritative. Mutations instantly update UI via query invalidation.

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

## Developer Commands

All commands run via `make` targets. Pre-authorized for Claude to execute without prompts.

### Testing
```bash
make test              # Fast tests (excludes slow agent calls)
make test-all          # All tests including slow tests
make test-schema       # Schema validation tests only
make test-context      # Context builder tests
make test-fetch        # Fetcher tests
make test-agent        # Agent output tests
make test-api          # API endpoint tests
make test-negotiate    # Negotiation session tests
make test-tasks        # Task + day lifecycle tests
```

### Pipeline & Data Fetching
```bash
make fetch             # Run all fetchers (news + calendar)
make pipeline          # Full pipeline: fetch → context → draft
make check-state       # Check state file freshness
make init-vault        # Initialize vault directory structure
```

### Server & API
```bash
make serve             # Start API server (dev mode with --reload)
make serve-prod        # Start API server (production)
```

### Maintenance
```bash
make lint              # Type checking (mypy + ruff)
make clean             # Remove build artifacts and caches
make install           # Install dev dependencies
make commit            # Stage and commit changes (prompts for message)
make push MSG="..."    # Push commits to origin
```

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
| 8 (vanilla) | webapp/app.js, webapp/styles.css, webapp/index.html (deprecated — Phase 8.1 replaced) |
| **8.1 (React)** | **webapp/src/{main.tsx, App.tsx, api.ts, types.ts}, features/*, shared/ui/*, screens/** |
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
- Check `webapp/dist/` exists: `ls -la webapp/dist/`
- Rebuild if missing: `make webapp-build`
- Clear browser cache (hard refresh: Ctrl+Shift+R or Cmd+Shift+R)
- Check React app errors: open browser DevTools → Console tab

### Webapp build fails
- Check Node.js version: `node --version` (should be 18+)
- Clear cache: `rm -rf webapp/node_modules webapp/dist`
- Reinstall: `make webapp-install && make webapp-build`
- Check TypeScript errors: `cd webapp && npm run lint` (should be clean)

## Next Session

**Session 10 Status (Just Completed):**
- ✅ Fixed 4 webapp bugs (schedule, times, approval flow)
- ✅ All changes committed and tested
- ✅ Webapp ready for proper E2E testing

**Session 11 Plan: Phase 8.2 (E2E Testing + Polish)**
1. Comprehensive testing of all 4 screens with real API data
   - No Draft → Morning Review → Active Day → Completed
   - All transitions and data flows
2. Negotiation chat testing (Collie button → mutations → refetch)
3. Task CRUD (complete, drop with reason, defer, add ad-hoc)
4. Approval flow (SEND IT → instant transition + tasks display)
5. Mobile responsiveness on real phone (landscape/portrait)
6. Browser DevTools inspection for errors/warnings
7. Document any remaining UX improvements

**Phase 9 (Automation + Hardening) After E2E Passes:**
1. Cron setup: `0 6 * * * cd /home/shu/cadence && make pipeline`
2. Systemd service: create `/etc/systemd/system/cadence-api.service`
3. Syncthing configuration for vault syncing
4. Tailscale/WireGuard setup for remote access
5. Deployment guide (VPS setup, GitHub Actions, monitoring)

**Current project status:**
- Phases 0–7: Complete ✅ (all Python backend + API server + negotiation)
- Phase 8.1: Complete ✅ (React SPA redesign with modern stack)
- **Bug Fixes: Complete ✅** (schedule, times, approval flow fixed)
- Phase 8.2: Next (E2E testing + polish)
- Phase 9–10: Pending (automation, stabilization, production rollout)

## ⚠️ Gotchas & Known Issues

### Webapp Data Flow Gotchas

**1. Schedule time format handling**
- **Issue:** Draft stores schedule `time_start` as `"HH:MM"` (e.g., `"09:30"`), NOT ISO 8601 datetimes
- **Gotcha:** `new Date("09:30")` → Invalid Date. Must detect `HH:MM` pattern and parse manually
- **Fix:** `formatTime()` in `utils.ts` checks regex `^\d{1,2}:\d{2}$` before calling `new Date()`
- **Lesson:** Time-only strings are ambiguous. Document format in schemas (Done: `# HH:MM` comment added)

**2. Tomorrow preview field naming inconsistency**
- **Issue:** Pydantic `CalendarTomorrowEvent` uses field `start: str` but TypeScript interface had `time_start?: string`
- **Gotcha:** API serializes `start` but frontend expected `time_start` → data always `undefined`
- **Fix:** TypeScript interface updated to match Pydantic schema. Normalize in component merge: `time_start: e.start`
- **Lesson:** After Pydantic schema changes, verify TypeScript types are in sync. Consider auto-generating types from Pydantic

**3. Past-event filtering in Morning Review**
- **Issue:** `ScheduleTimeline.tsx` filtered events with `eventTime > now` to hide past events
- **Gotcha:** Morning Review is a planning screen, not a live tracker. If viewed after 9:00 AM, all morning events hidden
- **Fix:** Removed the filter entirely. Show all events in Morning Review; past filtering only makes sense on Active Day
- **Lesson:** Question filtering logic — what's the intended use case? Don't assume "past = hidden"

**4. Query cache race condition in mutation callback**
- **Issue:** `onSuccess: () => queryClient.invalidateQueries()` schedules async refetch but returns immediately
- **Gotcha:** Old data still in cache while refetch pending → old screen renders briefly → race condition
- **Fix:** Return the promise from `refetchQueries()` so mutation loading state persists until refetch completes
- **Lesson:** In React Query, returning a promise from `onSuccess` makes the mutation wait. Use this for cache coherency

### API Response Structure Gotchas

**5. `ApproveResponse` doesn't include plan/schedule**
- **Issue:** `POST /api/approve` returns only `{ status, note_path, tasks }`, not the full plan
- **Gotcha:** Can't eagerly update cache with just this response; must refetch `/api/today` to get active plan
- **Fix:** Refetch after approve succeeds. API design: consider returning full plan on mutations that transition state
- **Lesson:** Mutation responses should include everything needed to update the cache without a refetch

## 💡 Learning & Patterns
- Document surprising patterns or common mistakes here to help future sessions.
- **Minimalist Rule:** Add entries only when something goes wrong; remove when fixed.
- **Workflow:** Read `PROGRESS.md` at the start of every session for current state.
- **Learning Folder Rule:** Whenever introducing a new tool, feature, library, framework, or process that would be beneficial for the user to understand, update `learning/` folder with a focused guide or topic list. Examples: "Phase 2 introduces build_context.py and markdown templating" → create `learning/phase2-context-builder.md` with topics like template syntax, markdown structure, string formatting. Link new files from MEMORY.md for discovery.

## 🤖 Swarm & Architecture Rules
- **Stack:** Python 3.11+, FastAPI, Pydantic v2, Claude API (claude-sonnet-4-6).
- **Frontend Stack:** React 18, TypeScript 5, Tailwind CSS, Vite, TanStack Query.
- **Structure:** Feature-area folders — `scripts/` (pipeline/fetchers/agent), `api/` (server/routes/negotiation), `tests/` (mirrors source layout), `webapp/` (React SPA with feature-first structure). Do not flatten or reorganise without explicit instruction.
- **Imports:** Always use absolute module paths (e.g. `from scripts.schemas import Task`). Never use relative imports (`from ..schemas`) unless inside a package that requires it.
- **Testing:** Test files live in `tests/` and mirror the module they test (e.g. `tests/test_schemas.py` ↔ `scripts/schemas.py`). Fixtures go in `tests/fixtures/`. Webapp tested manually (no automated tests).
- **Conflict Resolution:** If agents disagree on file placement or API design, the Lead Agent defaults to the architecture defined in this CLAUDE.md and the phased plan in IMPLEMENTATION_PLAN.md.
- **Agent Scope:** Each agent should own a single phase or a clearly bounded file set. Avoid agents touching files outside their stated scope without flagging it.
- **State Invariant:** VPS writes only to `vault/.system/`. Never let an agent write user-facing files (Daily/, data/) except through the `POST /api/approve` code path.

## 🎨 React/TypeScript/Tailwind Conventions

### Webapp Structure (Phase 8.1+)
```
webapp/src/
  main.tsx, App.tsx, api.ts, types.ts, index.css
  shared/
    ui/             # Atomic components (Button, Card, Badge)
    utils.ts        # Utility functions (formatDate, formatTime, etc.)
  features/         # Feature-first structure
    header/         # (Header, DayStats)
    news/           # (NewsCards)
    schedule/       # (ScheduleTimeline)
    tasks/          # (TaskList, AddTaskForm)
    training/       # (TrainingCard)
    negotiate/      # (CollieButton, ChatPanel)
    approve/        # (ApproveBanner)
  screens/          # Full-page layouts (NoDraft, MorningReview, ActiveDay, Completed)
```

### Design System (Peak Performance Dark Mode)
**Colors (custom Tailwind config):**
- `obsidian` (#030712) — page background
- `slate-dark` (#111827) — card backgrounds
- `topo` (#334155) — borders, subtle patterns
- `orange` (#FF5733) — CTAs, primary actions (SEND IT, Collie button)
- `collie-blue` (#2196F3) — secondary accents, info badges, timeline spine
- `canopy` (#4CAF50) — success, completion, approval
- `diamond-red` (#D32F2F) — high priority, critical actions

**Typography:**
- Space Mono — headings, code-like feel
- Inter — body text, maximum legibility

### React Patterns
**Data Fetching:**
- Use TanStack Query `useQuery` for read operations (caches, auto-retry, loading states)
- Use `useMutation` + `queryClient.invalidateQueries()` for mutations (instant refresh, no `location.reload()`)
- Type queries with `{ queryKey: ['today'], queryFn: api.getToday }` (deterministic cache keys)

**Component Props:**
- Define interfaces for all prop types (strict TypeScript)
- Use `React.forwardRef` for UI primitives (Button, Card, Badge)
- Prefer explicit variant props (`variant="primary"`) over className spreads

**Styling:**
- Use `cn()` utility (clsx + tailwind-merge) for conditional classes
- Example: `cn('px-4 py-2', { 'bg-orange': variant === 'primary' })`
- Never use string concatenation for Tailwind classes

**Component Hierarchy:**
- **Screens:** Full-page layouts (NoDraft, MorningReview, ActiveDay, Completed)
- **Features:** Feature domains with internal components (news/, schedule/, tasks/, etc.)
- **Shared UI:** Reusable primitives (Button, Card, Badge) with minimal props
- **Utils:** Pure functions (formatDate, formatTime, isPastEvent, cn)

### Task Priority Icons (MTB Difficulty System)
- **High (Black Diamond ◆):** `text-diamond-red` — urgent, blocking
- **Normal (Blue Square ■):** `text-collie-blue` — standard priority
- **Low (Green Circle ●):** `text-canopy` — nice-to-have, flexible

### Common Patterns
**Floating Buttons:**
```tsx
className="fixed bottom-6 right-6 z-40 w-16 h-16 rounded-full bg-orange text-white shadow-lg hover:bg-orange/90 transition-all animate-pulse"
```
Use `animate-pulse` for attention-grabbing (Collie button). Position over main content with `z-40`.

**Cards:**
```tsx
<Card className="p-4">
  <h3 className="font-serif font-bold text-gray-100">Title</h3>
  <p className="text-gray-400">Content</p>
</Card>
```
All cards use `bg-slate-dark` with `border border-topo/30` (consistency). Use internal padding (`p-4`, `p-6`).

**Status Badges:**
```tsx
<Badge variant="success">✓ Completed</Badge>
<Badge variant="info">📅 Fresh</Badge>
<Badge variant="error">✕ Stale</Badge>
```
Variants: default, success, warning, error, info. Use emoji + text for clarity.

**Inline Forms:**
Replace `window.prompt()` with inline text inputs:
```tsx
<input
  type="text"
  placeholder="..."
  className="w-full bg-obsidian border border-topo/30 rounded px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-orange/50"
/>
```

### No-Build Guarantee
- Webapp builds with `npm run build` → `webapp/dist/` (static files)
- FastAPI mounts `dist/` at `/app/` (SPA-friendly with `html=True`)
- No runtime bundling or lazy-loading required for MVP
- All imports resolved at build time by Vite

### Testing (Manual)
- No automated UI tests (per CLAUDE.md)
- Manual testing on phone/browser after `make serve`
- Use browser DevTools for state inspection (React DevTools, Network tab for API calls)
- Smoke test checklist: all 4 screens load, negotiate works, approve switches screens, tasks CRUD works

## 🔓 Pre-Authorized Commands for Claude

Claude may execute the following commands without asking for permission:

### Testing & Validation
- Run all test commands (`make test`, `make test-all`, `make test-*`)
- Run linting and type checks (`make lint`)
- Install dependencies (`make install`)

### Development Workflow
- Run the full pipeline (`make pipeline`, `make fetch`)
- Start the API server in dev or prod mode (`make serve`, `make serve-prod`)
- Initialize vault structure (`make init-vault`)
- Check system state (`make check-state`)

### Python Script Execution
- Execute any Python modules under `scripts/` (e.g., `python -m scripts.build_context`)
- Execute any test modules (e.g., `pytest tests/test_*.py`)
- Run configuration checks and utilities

### Git Operations
- Commit changes with descriptive messages
- Push commits to the main branch
- View git status and logs

**Authorization scope:** These commands are pre-approved for development and testing in this repository. Claude will NOT prompt for permission before running them.
