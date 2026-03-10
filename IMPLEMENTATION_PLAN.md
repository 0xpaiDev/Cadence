# Cadence: 10-Phase Implementation Plan

**Status:** Skeleton created (phase 0). Implementation begins next session.

**Duration:** ~17-28 days (2-4 weeks of full-time work)

**Success Criterion:** 7 consecutive days of generating useful, approved daily plans with decisions captured.

---

## Phase 1: Schemas + Test Infrastructure (Day 1)

**Goal:** Define all data models and set up testing framework.

**Files to create:**
- `scripts/schemas.py` — All Pydantic models (CalendarEvent, Task, DayState, etc.)
- `tests/conftest.py` — Fixtures, config loading, mock AgentRuntime
- `tests/fixtures/*.json` — Sample state files (empty, valid, malformed, v0)

**Pydantic models to implement:**
```python
# Calendar
CalendarEvent(title, start, end, location, all_day)
CalendarTomorrowEvent(title, start, all_day)
CalendarState(schema_version, fetched_at, date, events[], tomorrow_preview[])

# News
NewsItem(title, source, url, summary, topic, published, relevance[0-1])
NewsState(schema_version, fetched_at, items[], errors[])

# Tasks
TaskStatus enum: pending, completed, dropped, deferred
TaskSource enum: today, carried_over, suggested, negotiation, ad_hoc
Task(id, text, source, priority, status, created_at, completed_at, notes, drop_reason, deferred_to)
DayTasks(schema_version, date, tasks[], methods: complete(), drop(), defer(), add())

# Day Lifecycle
DayStatus enum: draft_pending, negotiating, active, completed
DayState(schema_version, date, status, draft_generated_at, negotiation_started_at, approved_at, completed_at)

# Decisions
DecisionAction enum: declined, added, moved, reprioritized, modified, accepted_suggestion
Decision(timestamp, action, target, reason, energy_note, context_tag, agent_suggestion)
DayDecisions(schema_version, date, negotiation_decisions[], task_outcomes[])

# Draft (JSON schema validation)
DraftSchema(schema_version, date, generated_at, news[], schedule[], tomorrow_preview[], tasks[], training{}, agent_suggestions[])
```

**Fixtures to create:**
- `calendar_state.json` — valid state with 3 events
- `calendar_state_empty.json` — no events
- `calendar_state_malformed.json` — invalid JSON/schema
- `calendar_state_v0.json` — old schema version (for migration tests)
- `news_state.json` — valid with 5 items
- `news_state_empty.json` — no news
- `news_state_malformed.json` — invalid
- `tasks_today.md` — markdown task list format
- `training_plan.md` — training context snippet
- `sample_daily_note.md` — example approved daily note
- `sample_draft.json` — example draft output

**Tests to implement:**
- `test_schemas.py` — Pydantic validation, schema version checking, type coercion
  - ✓ CalendarEvent validates start/end dates
  - ✓ Task requires id and text
  - ✓ NewsItem relevance 0-1 bounds
  - ✓ DayState status values
  - ✓ Schema version mismatch handling
  - ✓ Missing required fields raise ValidationError

**Deliverables:**
- All 3 model files with types + defaults
- 10+ test fixtures
- 20+ test assertions passing

**Verification:**
```bash
pytest tests/test_schemas.py -v
# All tests pass, no import errors
```

---

## Phase 2: Context Builder (Day 2)

**Goal:** Merge state files into a single markdown context document for the agent.

**Files to create:**
- `scripts/build_context.py` — merge news/calendar/tasks/training state → daily_context.md
- `scripts/config.py` — load cadence.toml, expose Config dataclass

**Config implementation:**
```python
@dataclass
class Config:
    vault_path: str
    cron_hour: int
    max_state_age_hours: int
    token_budget: int
    news_max_items: int
    agent_runtime: str
    agent_model: str
    agent_max_tokens: int
    api_host: str
    api_port: int
    log_level: str

def load_config(path="cadence.toml") -> Config:
    # Load TOML, parse, return Config instance
```

**Context builder logic:**
```python
def build_context_from_vault(vault_path: str, config: Config) -> str:
    # Load all state files from vault/.system/state/
    # - calendar_state.json
    # - news_state.json
    # - Read data/tasks/today.md
    # - Read data/training/plan.md

    # Render markdown context:
    # ## News Briefing
    # - [headline]({url}) — summary
    #
    # ## Schedule
    # - HH:MM–HH:MM: title
    #
    # ## Tasks
    # - [ ] text
    #
    # ## Training
    # - summary

    # Respect token_budget (count tokens, trim if needed)
    # Return markdown string
```

**Tests:**
- `test_context_builder.py`
  - ✓ Valid state files render correctly
  - ✓ Missing files handled gracefully (skip section)
  - ✓ Token budget enforced (trim items if over)
  - ✓ Markdown formatting correct
  - ✓ Malformed state files logged but don't crash

**Deliverables:**
- config.py with Config dataclass + load_config()
- build_context.py with build_context_from_vault()
- 10+ test assertions

**Verification:**
```bash
pytest tests/test_context_builder.py -v
# All tests pass
```

---

## Phase 3: Calendar Pipeline (Days 3-4)

**Goal:** Fetch Google Calendar events, write cal_state.json.

**Files to create:**
- `scripts/fetch/calendar_fetcher.py` — Google Calendar API integration
- Update `scripts/config.py` — add Google credentials path

**Calendar fetcher logic:**
```python
class CalendarFetcher:
    def __init__(self, config: Config, vault_path: str):
        # Load google_credentials.json from vault/.system/config/
        # Set up Google Calendar service (with token refresh)

    def fetch_today(self) -> CalendarState:
        # Fetch today's events from primary calendar
        # Convert to CalendarEvent objects
        # Fetch tomorrow preview (first event)
        # Return CalendarState(fetched_at=now, date=today, events=[], tomorrow_preview=[])

    def write_state(self, state: CalendarState):
        # Write vault/.system/state/calendar_state.json
```

**Error handling:**
- Missing credentials → log error, return empty state
- API rate limit → retry with backoff
- Network error → return stale state if available, log error
- Invalid token → refresh and retry

**Tests:**
- `test_fetchers.py` (calendar section)
  - ✓ Mock Google API, fetch returns valid CalendarState
  - ✓ Missing credentials returns empty state + error logged
  - ✓ All-day events handled correctly
  - ✓ Tomorrow preview populated
  - ✓ State file written to correct path

**Deliverables:**
- calendar_fetcher.py with CalendarFetcher class
- Google credentials setup guide (in README/CLAUDE.md)
- 5-8 test assertions

**Verification:**
```bash
pytest tests/test_fetchers.py::test_calendar_fetch -v
# All tests pass
```

---

## Phase 4: News Pipeline (Days 4-6)

**Goal:** Fetch news from RSS feeds, write news_state.json.

**Files to create:**
- `scripts/fetch/news_fetcher.py` — RSS feed fetcher
- `scripts/fetch/fetch_all.py` — orchestrate fetchers
- Update `scripts/config.py` — add news sources list

**News fetcher logic:**
```python
class NewsFetcher:
    def __init__(self, config: Config):
        # Hardcode or load news sources from config:
        # - AI industry (main feeds)
        # - Anthropic news (blog, Twitter)
        # - Boris Cherny (personal blog/tweets, if RSS available)

    def fetch(self) -> NewsState:
        # Fetch all feeds, parse with feedparser
        # Convert to NewsItem objects
        # Score relevance based on keywords (AI, Anthropic, Claude, etc.)
        # Sort by relevance, take top N (config.news_max_items)
        # Return NewsState(fetched_at=now, items=[], errors=[])

    def write_state(self, state: NewsState):
        # Write vault/.system/state/news_state.json
```

**fetch_all.py:**
```python
def fetch_all(config: Config, vault_path: str):
    # Instantiate both fetchers
    # Call fetch on each
    # Write both states
    # Log total items fetched, errors
    # Return success status
```

**Error handling:**
- Feed unavailable → log error, skip that feed
- Rate limit → backoff
- Parse error → log, skip item
- Network error → use last cached state if available

**Tests:**
- `test_fetchers.py` (news section)
  - ✓ Mock feedparser, fetch returns valid NewsState
  - ✓ Relevance scoring works (high for AI/Anthropic, low for random)
  - ✓ Items sorted by relevance
  - ✓ Top N limit enforced
  - ✓ Malformed feeds return errors in state
  - ✓ fetch_all orchestrates both fetchers correctly

**Deliverables:**
- news_fetcher.py with NewsFetcher class
- fetch_all.py with orchestration
- News sources list in config (or hardcoded)
- 8-10 test assertions

**Verification:**
```bash
pytest tests/test_fetchers.py -v
# All tests pass
```

---

## Phase 5: Agent + Draft Generation (Days 6-7)

**Goal:** Define AgentRuntime, implement Claude integration, generate daily draft JSON.

**Files to create:**
- `scripts/runtime.py` — AgentRuntime ABC + ClaudeRuntime
- `scripts/agent_daily_planner.py` — call agent, parse response, validate draft
- `scripts/pipeline.py` — orchestrate entire pipeline
- Create agent prompt templates in vault/.system/config/

**Runtime implementation:**
```python
class AgentRuntime(ABC):
    @abstractmethod
    def call(self, prompt: str, max_tokens: int) -> str:
        pass

class ClaudeRuntime(AgentRuntime):
    def __init__(self, model: str, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def call(self, prompt: str, max_tokens: int) -> str:
        # Call Claude API with prompt
        # Return text response
        # Handle errors (rate limit, API down, etc.)
```

**Daily planner logic:**
```python
def generate_draft(context: str, config: Config, runtime: AgentRuntime) -> dict:
    # Load daily_template.md from vault/.system/config/
    # Build system prompt with template
    # Append context_md as user message
    # Call runtime.call(system + context, max_tokens)
    # Parse response as JSON
    # Validate against DraftSchema
    # Return dict (or raise on invalid JSON)
```

**Pipeline orchestration:**
```python
def run_pipeline(config: Config):
    runtime = ClaudeRuntime(model=config.agent_model, api_key=os.getenv("ANTHROPIC_API_KEY"))
    vault = Path(config.vault_path)

    # 1. Fetch all data
    fetch_all(config, vault)

    # 2. Build context
    context = build_context_from_vault(vault, config)
    vault/.system/context/daily_context.md ← context

    # 3. Generate draft
    draft = generate_draft(context, config, runtime)
    vault/.system/drafts/today_draft.json ← draft

    # 4. Update day state
    day_state = DayState(
        date=today,
        status=DayStatus.DRAFT_PENDING,
        draft_generated_at=now
    )
    vault/.system/state/day_state.json ← day_state

    return success
```

**Agent prompt templates:**
Create `vault/.system/config/daily_template.md`:
```markdown
# Daily Planner

You are a personal scheduling assistant. You receive:
1. News briefing (AI industry)
2. Today's calendar
3. Today's task list
4. Training plan

Generate a structured JSON daily plan:
- 3-5 top news items (highest relevance first)
- Schedule in chronological order
- Tasks from today's list
- 1-2 suggestions if day is light
- One-line training summary

**Output ONLY valid JSON, no markdown or explanation.**
```

**Tests:**
- `test_agent_output.py`
  - ✓ Mock Anthropic API, generate valid draft JSON
  - ✓ Draft schema validation (all required fields)
  - ✓ Invalid JSON from agent raises error
  - ✓ Agent suggestions included if light day
  - ✓ News sorted by relevance
  - ✓ Schedule chronological

- `test_pipeline.py` (integration)
  - ✓ Full pipeline runs without errors (all mocked)
  - ✓ All state files written correctly
  - ✓ day_state.status is draft_pending after pipeline
  - ✓ Context file has correct format
  - ✓ Draft file valid JSON

**Deliverables:**
- runtime.py with AgentRuntime ABC + ClaudeRuntime
- agent_daily_planner.py with generate_draft()
- pipeline.py with run_pipeline()
- Two prompt templates in vault/.system/config/
- 15+ test assertions

**Verification:**
```bash
pytest tests/test_agent_output.py tests/test_pipeline.py -v
# All tests pass
```

---

## Phase 6: API Server + Endpoints (Days 8-10)

**Goal:** Build FastAPI server with all 6 endpoints.

**Files to create:**
- `api/server.py` — FastAPI app setup, static mount, lifespan
- `api/routes.py` — all endpoint handlers

**Server setup:**
```python
app = FastAPI(title="Cadence", version="0.3.0")

# CORS
app.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins)

# Static files (webapp)
app.mount("/app", StaticFiles(directory="webapp", html=True), name="webapp")

@app.get("/")
def redirect_to_app():
    return RedirectResponse(url="/app/")

@app.lifespan
async def lifespan(app):
    # Startup: load config, validate vault, check state freshness
    # Shutdown: close resources
    yield
```

**Endpoints in routes.py:**

1. **GET /api/today**
   - Check day_state.json status
   - If draft_pending: return draft from vault/.system/drafts/today_draft.json
   - If active: return approved plan + tasks
   - If completed: return summary
   - Return freshness info (calendar/news age)

2. **POST /api/negotiate**
   - Request: `{ "text": "..." }`
   - Instantiate NegotiationSession (created in Phase 7)
   - Call session.exchange(user_text)
   - Return `{ "message": "...", "draft": { ... }, "decisions": [...] }`

3. **POST /api/approve**
   - No request body
   - Call session.approve()
   - Write Daily/YYYY-MM-DD.md to vault
   - Update day_state to active
   - Return `{ "status": "approved", "tasks": { ... } }`

4. **POST /api/tasks**
   - Request: `{ "text": "...", "priority": "high|normal|low" }`
   - Create new Task with id, source=ad_hoc, status=pending
   - Append to vault/data/tasks/today.md
   - Write vault/.system/state/tasks_today.json
   - Return `{ "task": { ... }, "tasks": { ... } }`

5. **POST /api/tasks/:id**
   - Request: `{ "action": "complete|drop|defer", "reason": "...", "defer_to": "..." }`
   - Load tasks from vault/data/tasks/today.md
   - Update task in memory (DayTasks class handles mutations)
   - Write updated state
   - Return `{ "tasks": { ... } }`
   - If drop without reason: return 422

6. **GET /api/status**
   - Check state file freshness
   - Return `{ "calendar_fresh": bool, "news_fresh": bool, "day_status": "...", "errors": [...] }`

**Tests:**
- `test_api.py`
  - ✓ GET /api/today returns draft when draft_pending
  - ✓ GET /api/today returns active plan when active
  - ✓ POST /api/tasks creates ad-hoc task with correct source
  - ✓ POST /api/tasks/:id complete sets completed_at
  - ✓ POST /api/tasks/:id drop without reason returns 422
  - ✓ GET /api/status returns correct freshness
  - ✓ All endpoints return correct status codes

- `test_task_lifecycle.py`
  - ✓ Task can transition: pending → completed
  - ✓ Task can transition: pending → dropped (with reason)
  - ✓ Task can transition: pending → deferred → tomorrow
  - ✓ Can't complete already-dropped task (raises ValueError)
  - ✓ Task completed_at set to ISO timestamp

- `test_day_lifecycle.py`
  - ✓ Day starts draft_pending
  - ✓ Day transitions draft_pending → negotiating
  - ✓ Day transitions negotiating → active (on approve)
  - ✓ Day transitions active → completed (at day end)
  - ✓ State transitions are atomic (all-or-nothing)

**Deliverables:**
- server.py with FastAPI app
- routes.py with all 6 handlers
- 20+ test assertions
- CORS configured

**Verification:**
```bash
pytest tests/test_api.py tests/test_task_lifecycle.py tests/test_day_lifecycle.py -v
# All tests pass
make serve &  # Start server
curl http://localhost:8420/api/status
# Returns valid JSON
```

---

## Phase 7: Negotiation System (Days 10-12)

**Goal:** Implement interactive negotiation with structured decision extraction.

**Files to create:**
- `api/negotiation.py` — NegotiationSession class
- Update `api/routes.py` — POST /api/negotiate handler

**NegotiationSession class:**
```python
class NegotiationSession:
    def __init__(self, draft: dict, context: str, runtime: AgentRuntime):
        self.draft = draft
        self.context = context
        self.runtime = runtime
        self.history: list[dict] = []  # [{"role": "user", "content": "..."}, ...]
        self.decisions: list[Decision] = []

    def exchange(self, user_message: str) -> NegotiationResponse:
        # Add user message to history
        # Build system prompt from negotiation_template.md
        # Call runtime.call(system + history)
        # Parse response:
        #   - Extract text response
        #   - Extract <changes> XML block
        #   - Parse JSON actions: {"action": "drop_task", "task_id": "t1"}
        #   - Apply mutations to draft
        # Record decisions
        # Return NegotiationResponse(message="...", draft={...}, decisions=[...])

    def approve(self) -> ApprovalResult:
        # Render draft to markdown daily note
        # Write vault/Daily/YYYY-MM-DD.md
        # Write vault/.system/state/decisions.json
        # Update vault/data/tasks/today.md with approved tasks
        # Update day_state to active
        # Return ApprovalResult(note_path, tasks, decisions)
```

**Negotiation agent prompt (`vault/.system/config/negotiation_template.md`):**
```markdown
# Negotiation Agent

You are a planning assistant helping refine the daily plan.

The user describes a change they want. Your job:
1. Accept the change immediately (no arguing)
2. Acknowledge their reason naturally
3. Mention time blocks if relevant
4. Suggest 1 concrete adjustment if helpful
5. Keep response to 2-4 sentences

After your response, output a <changes> block with JSON actions:

<changes>
{"action": "drop_task", "task_id": "t1", "reason": "user request"}
{"action": "add_task", "text": "New task", "priority": "high"}
</changes>

Actions:
- drop_task: Remove task by id
- add_task: Add new task
- move_task: Reschedule (not implemented yet)
- reprioritize_task: Change priority
```

**Decision extraction:**
```python
def _extract_changes(response: str) -> list[dict]:
    # Parse <changes>...</changes> block from response
    # Each line is a JSON action
    # Return list of actions (or empty if no block)
```

**Tests:**
- `test_negotiation.py`
  - ✓ NegotiationSession.exchange() parses agent response correctly
  - ✓ Changes are extracted from <changes> XML block
  - ✓ Draft is mutated correctly (task dropped, added, reprioritized)
  - ✓ Decisions logged with timestamp + action
  - ✓ approve() writes all files and updates day_state
  - ✓ Multiple rounds of negotiation build up history correctly
  - ✓ Conversation log recorded in decisions.json

**Deliverables:**
- negotiation.py with NegotiationSession class
- Negotiation prompt template
- 12+ test assertions
- Change extraction + mutation logic

**Verification:**
```bash
pytest tests/test_negotiation.py -v
# All tests pass
```

---

## Phase 8: Webapp (Days 12-15)

**Goal:** Build mobile-first SPA for morning review and daytime tracking.

**Files to create:**
- `webapp/index.html` — SPA shell
- `webapp/styles.css` — mobile-responsive styles
- `webapp/app.js` — all logic (fetch, render, interact)

**SPA structure:**

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cadence</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div id="app"></div>
    <script src="app.js"></script>
</body>
</html>
```

**Screens and logic (app.js):**

**Morning Review Screen (draft_pending / negotiating):**
- Display news cards (headline, source, link)
- Display schedule (time blocks, X button to tap-to-negotiate)
- Display tomorrow preview
- Display task list (checkboxes, "+ Add task")
- Display training summary
- Chat input area (user message, agent response)
- "Approve Plan" button at bottom

**Active Day Screen (active after approval):**
- Task checklist (✓ to complete, X to drop, → to defer)
- Optional note input on task
- Remaining schedule
- Day stats (completed count, dropped count)

**Interactions:**

```javascript
// Fetch current state
async function loadToday() {
    const res = await fetch("/api/today");
    const data = await res.json();

    if (data.status === "draft" || data.status === "negotiating") {
        renderMorningScreen(data);
    } else if (data.status === "active") {
        renderActiveDayScreen(data);
    }
}

// Morning negotiation
async function negotiate(userText) {
    const res = await fetch("/api/negotiate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userText })
    });
    const result = await res.json();
    appendChatMessage("agent", result.message);
    updateDraftDisplay(result.draft);
}

// Approve plan
async function approvePlan() {
    const res = await fetch("/api/approve", { method: "POST" });
    const result = await res.json();
    renderActiveDayScreen(result);
}

// Complete task
async function completeTask(taskId, notes) {
    const res = await fetch(`/api/tasks/${taskId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "complete", notes })
    });
    const result = await res.json();
    updateTaskList(result.tasks);
}

// Drop task (requires reason)
async function dropTask(taskId, reason) {
    if (!reason) {
        alert("Why are you dropping this?");
        return;
    }
    const res = await fetch(`/api/tasks/${taskId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "drop", reason })
    });
    const result = await res.json();
    updateTaskList(result.tasks);
}

// Defer task
async function deferTask(taskId, deferTo) {
    const res = await fetch(`/api/tasks/${taskId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "defer", defer_to: deferTo })
    });
    const result = await res.json();
    updateTaskList(result.tasks);
}

// Add ad-hoc task
async function addTask(text, priority) {
    const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, priority })
    });
    const result = await res.json();
    updateTaskList(result.tasks);
}
```

**Styling (styles.css):**
- Mobile-first (320px and up)
- Responsive for tablet/laptop (media queries)
- Touch-friendly buttons (44px minimum)
- Card-based layout (news, tasks, schedule)
- Dark-friendly (or light, user preference)

**Manual testing:**
- Test on iPhone/Android (physical phone or dev tools)
- Test all interactions: negotiate, complete, drop, defer, add, approve
- Test offline behavior (graceful degradation)

**Deliverables:**
- index.html (SPA shell)
- styles.css (mobile-responsive, ~500 lines)
- app.js (all logic, ~800 lines)
- Both screens fully functional
- Tested on phone

**Verification:**
```bash
make serve &
# On phone: navigate to http://<vps-ip>:8420/app/
# Test: review → negotiate → approve → mark tasks
```

---

## Phase 9: Automation + Hardening (Days 15-17)

**Goal:** Set up cron, systemd, Syncthing, deployment, and production hardening.

**Tasks:**

1. **Cron setup:**
   - Add to crontab: `0 6 * * * cd /home/shu/cadence && make pipeline`
   - Verify logs go to vault/.system/logs/pipeline.log

2. **Systemd service:**
   - Create `/etc/systemd/system/cadence-api.service`
   - ExecStart: uvicorn api.server:app --host 0.0.0.0 --port 8420
   - ExecRestart: always
   - Enable: systemctl enable cadence-api.service

3. **Syncthing configuration:**
   - Configure on VPS to sync ~/vault/ to laptop/phone
   - Set up to ignore code repo (only data sync)
   - Test bi-directional sync

4. **Tailscale/WireGuard:**
   - Install Tailscale on VPS and client devices
   - Expose API at VPS Tailscale IP:8420
   - Configure firewall rules

5. **Error handling & logging:**
   - Pipeline: log all steps, don't fail if one fetcher fails
   - API: catch all exceptions, return 5xx with error message
   - Webapp: show error overlay if API unreachable

6. **State validation:**
   - On startup, check all state files
   - Log warnings if files missing or stale
   - Auto-initialize missing files with empty/default values

7. **Deployment guide:**
   - Document: git clone → pip install → cadence.toml setup → vault init → cron/systemd setup
   - Include: Google credentials setup, Syncthing config, Tailscale setup

**Deliverables:**
- systemd service file
- Cron entry verified
- Syncthing configured + tested
- Tailscale access working
- Error handling in API
- Deployment guide (in README or separate DEPLOY.md)

**Verification:**
```bash
# VPS
crontab -l | grep pipeline
systemctl status cadence-api
tail -f ~/vault/.system/logs/pipeline.log
# Check Syncthing sync
# Access API via Tailscale IP from phone
```

---

## Phase 10: Stabilization (Days 17-28)

**Goal:** Run MVP daily for 7+ consecutive days, fix issues, declare done.

**Activities:**

1. **Daily runs:**
   - Let pipeline run at 06:00 each morning
   - Review draft, negotiate if needed, approve
   - Track tasks throughout day
   - Check logs for errors

2. **Iterate:**
   - Fix bugs as they appear
   - Tune agent prompts if draft quality poor
   - Adjust task completion/drop reasons if needed
   - Improve error messages

3. **User feedback:**
   - Collect 7 days of notes + decisions
   - Review: Did plan capture your day well?
   - Review: Did agent suggestions help?
   - Review: Did task tracking feel natural?

4. **Polish:**
   - Improve webapp UX based on usage
   - Refine error handling
   - Add missing features (if simple)

5. **Documentation:**
   - Document patterns observed
   - Write user guide
   - Update README with lessons learned

6. **Success criterion:**
   - 7 consecutive days of useful daily plans
   - All decisions captured as JSON
   - No major bugs or crashes
   - Approval of plans comes naturally (not forced)

**Deliverables:**
- 7 days of daily notes in vault/Daily/
- 7 days of decisions in vault/.system/state/decisions.json
- Bug fixes and improvements
- Final documentation
- **MVP declared done**

**Verification:**
```bash
ls ~/vault/Daily/ | wc -l
# Should show 7+ files (daily notes)
cat ~/vault/.system/state/decisions.json | jq '.negotiation_decisions | length'
# Should show decisions captured
```

---

## Summary Timeline

| Phase | Duration | Key Files | Focus |
|---|---|---|---|
| 1 | 1 day | schemas.py, conftest.py, fixtures | Models + testing |
| 2 | 1 day | config.py, build_context.py | Context merge |
| 3 | 2 days | calendar_fetcher.py | Google Calendar |
| 4 | 2 days | news_fetcher.py, fetch_all.py | News + orchestration |
| 5 | 2 days | runtime.py, agent_daily_planner.py, pipeline.py | AI agent + draft |
| 6 | 3 days | server.py, routes.py | FastAPI + endpoints |
| 7 | 2 days | negotiation.py | Negotiation logic |
| 8 | 3 days | index.html, styles.css, app.js | Webapp |
| 9 | 2 days | systemd, cron, docs | Automation |
| 10 | 11 days | (none) | Stabilization |
| **Total** | **28 days** | **All files** | **MVP done** |

---

## Success Metrics

✓ All tests pass (make test-all)
✓ Pipeline runs daily without errors
✓ Draft JSON always valid
✓ Webapp loads and responds
✓ Negotiation extracts decisions correctly
✓ Tasks tracked through day
✓ 7 approved daily plans captured
✓ All decisions logged as JSON
✓ No critical bugs for 7 days
✓ User finds plans useful

---

## Post-MVP Roadmap

After Phase 10 stabilization:

**Phase A (2 weeks):** Weekly reflection agent
- Read 7 days of notes + decisions + outcomes
- Generate Weekly_Patterns.md
- Update user_model.json with patterns (energy, task types, deferrals, acceptance rates)

**Phase B:** Feed user model to agents
- Daily Planner references user patterns in suggestions
- Negotiation agent uses patterns to anticipate pushback

**Phase C (2-3 months):** Proactive features
- Predict deferrals before proposing tasks
- Suggest schedule changes based on energy patterns
- Detect interest shifts
- Training Coach integration
