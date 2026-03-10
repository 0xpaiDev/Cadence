# Project Aegis — MVP Spec v3: Daily Intelligence Note

**Version:** 3.0
**Status:** Start-ready
**Scope:** MVP daily intelligence note + interactive webapp for review, negotiation, and task tracking

---

## Objective

Every morning, a draft daily note is ready before you wake up. You open a webapp on your phone or laptop, review the draft, negotiate changes with an AI agent, approve the plan, and go. Throughout the day, you mark tasks done and add notes. Everything — the plan, your decisions, your feedback — is captured as structured data that feeds a long-term user model.

The daily note contains:

1. **News Briefing** — AI industry, Anthropic, Boris Cherny (Claude insights/tweets)
2. **Calendar** — Today's events from Google Calendar
3. **Tasks** — Today's todo list (vault-native, markdown-based)
4. **Training** — Summary pulled from existing training plan context (read-only)

---

## System Overview

```
┌──────────────────────────────────────────────────────────┐
│                    VPS (always running)                    │
│                                                           │
│  cron 06:00 ─► fetch_all.py                              │
│                  ├── news_fetcher.py → news_state.json    │
│                  ├── calendar_fetcher.py → cal_state.json │
│                  └── build_context.py → daily_context.md  │
│               ─► agent_daily_planner.py → draft.json      │
│                                                           │
│  Aegis API (FastAPI) ─────────────────────────────────── │
│    GET  /today          → current draft or approved plan  │
│    POST /negotiate      → agent conversation exchange     │
│    POST /approve        → lock plan, write daily note     │
│    POST /tasks/:id      → update task status + notes      │
│    GET  /tasks          → current task states             │
│    GET  /status         → system health + state freshness │
│                                                           │
│  Syncthing ◄────────────────────────────► Laptop/Phone   │
│  (vault data only, not code)                              │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│              Webapp (phone / laptop browser)               │
│                                                           │
│  Morning:   see draft → negotiate → approve               │
│  Daytime:   check off tasks, add notes                    │
│  Evening:   review completed day (auto-captured)          │
└──────────────────────────────────────────────────────────┘
```

**Key change from v2:** The VPS now runs the full pipeline (fetch → context → draft) *and* serves a lightweight API. This means the draft is ready before you wake up. The webapp talks to this API. No manual script triggering needed.

**Key invariant (preserved):** VPS writes to `.system/` only. User-facing files (`Daily/`, `data/tasks/`) are written only on explicit approval or task updates. Vault sync via Syncthing handles the rest.

---

## Repository Structure

```
~/aegis/                              ← git repo (deployed to VPS via git)
  scripts/
    fetch/
      __init__.py
      fetch_all.py                    ← cron entry point
      news_fetcher.py
      calendar_fetcher.py
    build_context.py
    agent_daily_planner.py
    runtime.py                        ← AgentRuntime base + implementations
    schemas.py                        ← Pydantic models (state + decisions + tasks)
    config.py                         ← loads aegis.toml
  api/
    __init__.py
    server.py                         ← FastAPI app
    routes.py                         ← endpoint handlers
    negotiation.py                    ← conversation session manager
  webapp/
    index.html                        ← single-page app (static, served by API)
    styles.css
    app.js
  tests/
    __init__.py
    conftest.py
    fixtures/
      calendar_state.json
      calendar_state_empty.json
      calendar_state_malformed.json
      calendar_state_v0.json
      news_state.json
      news_state_empty.json
      news_state_malformed.json
      tasks_today.md
      training_plan.md
      sample_daily_note.md
      sample_draft.json
    test_schemas.py
    test_context_builder.py
    test_fetchers.py
    test_agent_output.py
    test_pipeline.py
    test_api.py                       ← API endpoint tests
    test_negotiation.py               ← negotiation session tests
    test_task_lifecycle.py            ← task state transition tests
  aegis.toml
  pyproject.toml
  Makefile
  CLAUDE.md
  README.md
  .gitignore

~/vault/                              ← Syncthing-synced
  Daily/
    2025-06-15.md                     ← approved daily note
  Projects/
  Knowledge/
  data/
    tasks/
      inbox.md
      today.md
      backlog.md
    training/
      plan.md
      log.md
  .system/
    state/
      calendar_state.json
      news_state.json
      day_state.json                  ← current day lifecycle state (NEW)
      decisions.json                  ← negotiation decisions log (NEW)
    context/
      calendar_context.md
      news_context.md
      tasks_context.md
      training_context.md
      daily_context.md
    drafts/
      today_draft.json                ← agent-generated draft (NEW)
    config/
      interests.json
      daily_template.md
      negotiation_template.md         ← negotiation agent prompt (NEW)
      google_credentials.json
    logs/
      fetch.log
      agent.log
      api.log                         ← API request log (NEW)
    model/
      user_model.json                 ← persistent user patterns (NEW, future)
```

---

## Daily Lifecycle

A day in Aegis has a clear state machine. This prevents partial states, duplicate approvals, and lost data.

```
          06:00 cron
              │
              ▼
┌─────────────────────┐
│   DRAFT_PENDING     │  Pipeline ran, draft ready
│   today_draft.json  │  Waiting for user
└─────────┬───────────┘
          │ user opens webapp
          ▼
┌─────────────────────┐
│   NEGOTIATING       │  User reviewing + adjusting
│   conversation[]    │  Agent responds to feedback
└─────────┬───────────┘
          │ user approves
          ▼
┌─────────────────────┐
│   ACTIVE            │  Plan locked, tasks trackable
│   Daily/YYYY-MM-DD  │  Task updates flow in
└─────────┬───────────┘
          │ end of day (auto or manual)
          ▼
┌─────────────────────┐
│   COMPLETED         │  All data captured
│   decisions.json    │  Ready for reflection agent
└─────────────────────┘
```

**State file** (`.system/state/day_state.json`):

```json
{
  "schema_version": 1,
  "date": "2025-06-15",
  "status": "active",
  "draft_generated_at": "2025-06-15T06:02:00Z",
  "negotiation_started_at": "2025-06-15T07:15:00Z",
  "approved_at": "2025-06-15T07:22:00Z",
  "completed_at": null
}
```

---

## Draft Format

The agent produces a structured draft (JSON, not markdown) so the webapp can render and manipulate it:

**`.system/drafts/today_draft.json`:**

```json
{
  "schema_version": 1,
  "date": "2025-06-15",
  "generated_at": "2025-06-15T06:02:00Z",
  "news": [
    {
      "id": "n1",
      "topic": "Anthropic",
      "headline": "Anthropic released Claude 4 with extended context",
      "summary": "New model supports 500k tokens with improved reasoning.",
      "url": "https://...",
      "relevance": 0.95
    },
    {
      "id": "n2",
      "topic": "Boris Cherny",
      "headline": "Thread on Claude Code workflows for monorepos",
      "summary": "Boris shared patterns for multi-package repos with Claude Code.",
      "url": "https://twitter.com/...",
      "relevance": 0.88
    }
  ],
  "schedule": [
    {
      "id": "s1",
      "time_start": "09:00",
      "time_end": "09:30",
      "title": "Team standup",
      "location": "Google Meet",
      "all_day": false
    },
    {
      "id": "s2",
      "time_start": "14:00",
      "time_end": "15:00",
      "title": "Architecture review",
      "location": null,
      "all_day": false
    }
  ],
  "tomorrow_preview": [
    {
      "title": "Dentist",
      "time_start": "14:00"
    }
  ],
  "tasks": [
    {
      "id": "t1",
      "text": "Review PR for auth module",
      "source": "carried_over",
      "priority": "normal",
      "status": "pending",
      "completed_at": null,
      "notes": null
    },
    {
      "id": "t2",
      "text": "Send status update to team",
      "source": "today",
      "priority": "normal",
      "status": "pending",
      "completed_at": null,
      "notes": null
    },
    {
      "id": "t3",
      "text": "Write integration tests",
      "source": "carried_over",
      "priority": "low",
      "status": "pending",
      "completed_at": null,
      "notes": null
    }
  ],
  "training": {
    "summary": "Week progress: 20/100km. Long ride needed before Sunday.",
    "plan_reference": "data/training/plan.md"
  },
  "agent_suggestions": [
    "Light task day — consider tackling the backlog integration tests.",
    "Architecture review is 2 hours after standup — good focus block between them."
  ]
}
```

**Why JSON instead of markdown for the draft?** The webapp needs structured data to render interactive task checkboxes, negotiation controls, and status updates. The final approved plan gets written as markdown to `Daily/YYYY-MM-DD.md` for Obsidian.

---

## Task Lifecycle

Tasks flow through clear states. Every transition is captured with timestamp and optional notes.

```
                ┌─► completed (with optional note)
                │
pending ────────┤
                │
                ├─► dropped (with reason)
                │
                └─► deferred (moved to tomorrow/backlog)

Added during negotiation:
  negotiation_add ──► pending ──► completed/dropped/deferred

Added during the day:
  ad_hoc_add ──► pending ──► completed/dropped/deferred
```

**Task state schema** (in `schemas.py`):

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    DROPPED = "dropped"
    DEFERRED = "deferred"

class TaskSource(str, Enum):
    TODAY = "today"              # from today.md
    CARRIED_OVER = "carried_over"  # from previous day
    SUGGESTED = "suggested"      # agent suggestion
    NEGOTIATION = "negotiation"  # added during morning review
    AD_HOC = "ad_hoc"           # added during the day via webapp

class Task(BaseModel):
    id: str
    text: str
    source: TaskSource
    priority: str = "normal"     # "high", "normal", "low"
    status: TaskStatus = TaskStatus.PENDING
    created_at: str
    completed_at: str | None = None
    notes: str | None = None     # user feedback on completion/drop
    drop_reason: str | None = None
    deferred_to: str | None = None  # "tomorrow", "backlog", or specific date

class DayTasks(BaseModel):
    schema_version: int = 1
    date: str
    tasks: list[Task]
    
    def complete(self, task_id: str, notes: str | None = None):
        task = self._find(task_id)
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC).isoformat()
        task.notes = notes
    
    def drop(self, task_id: str, reason: str):
        task = self._find(task_id)
        task.status = TaskStatus.DROPPED
        task.drop_reason = reason
    
    def defer(self, task_id: str, to: str):
        task = self._find(task_id)
        task.status = TaskStatus.DEFERRED
        task.deferred_to = to
    
    def add(self, text: str, source: TaskSource, priority: str = "normal") -> Task:
        task = Task(
            id=f"t{len(self.tasks) + 1}_{int(time.time())}",
            text=text,
            source=source,
            priority=priority,
            created_at=datetime.now(UTC).isoformat(),
        )
        self.tasks.append(task)
        return task
    
    def _find(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise ValueError(f"Task not found: {task_id}")
```

**Task completion with notes — the key feedback signal:**

When you check off a task in the webapp, you get an optional text field for a note. This is low-friction — you can skip it for routine completions, but when you want to capture context, it's there:

```
✅ Review PR for auth module
   Note: "took longer than expected, auth logic needs refactoring" [optional]

❌ Architecture review  →  dropped
   Reason: "low energy, postponing to thursday" [required for drops]

➡️ Write integration tests  →  deferred to tomorrow
```

These notes are the richest signal for the user model. "Low energy" repeated on certain days/times builds the energy pattern. "Took longer than expected" on certain task types reveals estimation patterns.

---

## Negotiation System

### How It Works

Morning negotiation is a conversation between you and the agent via the webapp. The agent has the full daily context plus (eventually) the user model.

**Example interaction:**

```
[Webapp shows draft with all sections]

You: "Drop the architecture review, I'm not in the mood for meetings today"

Aegis: "Removed architecture review. That opens 14:00-15:00.
        You've got a focus block between 09:30 and 14:00 now —
        want to move the PR review there?"

You: "Yes. Also add 'write Aegis reflection agent spec' as top priority"

Aegis: "Added as priority task. Updated plan:

        Tasks:
        ⭐ Write Aegis reflection agent spec
        📋 Review PR for auth module (moved to morning block)
        📋 Send status update to team
        
        Dropped: Architecture review (reason: not in mood for meetings)"

You: [taps Approve]
```

### Negotiation Session Manager

```python
# api/negotiation.py

class NegotiationSession:
    def __init__(self, draft: dict, context: str, runtime: AgentRuntime):
        self.draft = draft
        self.context = context
        self.runtime = runtime
        self.history: list[dict] = []
        self.decisions: list[Decision] = []
        self.task_mutations: list[dict] = []  # track all task changes

    def exchange(self, user_message: str) -> NegotiationResponse:
        """One round of negotiation. Returns agent response + updated draft."""
        self.history.append({"role": "user", "content": user_message})

        response = self.runtime.run_conversation(
            system_prompt=self._load_negotiation_prompt(),
            messages=self._build_messages(),
        )

        self.history.append({"role": "assistant", "content": response.text})
        
        # Extract structured mutations from agent response
        if response.draft_changes:
            self._apply_changes(response.draft_changes)
            self._record_decisions(user_message, response)

        return NegotiationResponse(
            message=response.text,
            updated_draft=self.draft,
            decisions=self.decisions[-3:],  # show recent decisions
        )

    def approve(self) -> ApprovalResult:
        """Lock the plan. Write daily note + decision log."""
        return ApprovalResult(
            daily_note=self._render_markdown(),
            decisions=self.decisions,
            task_mutations=self.task_mutations,
            conversation_log=self.history,
        )

    def _build_messages(self) -> list[dict]:
        """Build conversation with draft + context as system knowledge."""
        return [
            {"role": "user", "content": f"Today's draft:\n{json.dumps(self.draft, indent=2)}"},
            {"role": "assistant", "content": "I have your daily plan ready. What adjustments would you like?"},
            *self.history,
        ]
```

### Decision Schema

```python
class DecisionAction(str, Enum):
    DECLINED = "declined"           # removed event or task
    ADDED = "added"                 # added new task
    MOVED = "moved"                 # rescheduled
    REPRIORITIZED = "reprioritized" # changed priority
    MODIFIED = "modified"           # changed task description
    ACCEPTED_SUGGESTION = "accepted_suggestion"

class Decision(BaseModel):
    timestamp: str
    action: DecisionAction
    target: str                     # what was affected
    reason: str | None = None       # user's stated reason
    energy_note: str | None = None  # if user mentioned energy/mood/state
    context_tag: str | None = None  # "morning_negotiation" or "during_day"
    agent_suggestion: str | None = None
```

**Decision log** (`.system/state/decisions.json`):

```json
{
  "schema_version": 1,
  "date": "2025-06-15",
  "negotiation_decisions": [
    {
      "timestamp": "2025-06-15T07:16:00Z",
      "action": "declined",
      "target": "Architecture review meeting",
      "reason": "not in mood for meetings",
      "energy_note": "low meeting energy",
      "context_tag": "morning_negotiation",
      "agent_suggestion": "Opened focus block 14:00-15:00"
    },
    {
      "timestamp": "2025-06-15T07:17:00Z",
      "action": "added",
      "target": "Write Aegis reflection agent spec",
      "reason": null,
      "energy_note": null,
      "context_tag": "morning_negotiation",
      "agent_suggestion": null
    }
  ],
  "task_outcomes": [
    {
      "task_id": "t1",
      "text": "Review PR for auth module",
      "status": "completed",
      "completed_at": "2025-06-15T11:45:00Z",
      "notes": "took longer than expected, auth logic needs refactoring",
      "duration_estimate": null
    },
    {
      "task_id": "t2",
      "text": "Send status update to team",
      "status": "completed",
      "completed_at": "2025-06-15T16:00:00Z",
      "notes": null,
      "duration_estimate": null
    }
  ]
}
```

### Negotiation Agent Prompt (`.system/config/negotiation_template.md`)

```markdown
You are Aegis — a personal planning assistant in a morning review session.

You have:
- Today's draft plan (calendar, news, tasks, training)
- Full daily context
- (Future: user model with behavioral patterns)

## Behavior

When the user pushes back on something:
1. Accept immediately — never argue or persuade
2. Acknowledge their reason naturally
3. If the change opens/closes time, mention it briefly
4. Suggest one concrete adjustment if obvious — don't redesign the whole day

When the user adds something:
1. Add it, confirm priority relative to existing tasks
2. If day looks overloaded (>6 tasks), flag it — suggest what to deprioritize

When the user says "approve", "lock it", "good", or similar:
1. Confirm the final plan concisely

## Response Format

Keep responses short — 2-4 sentences max. You're a morning assistant, not a therapist.

Always respond with both:
1. A natural language message
2. A structured changes block (the API extracts this):

<changes>
{"action": "drop_task", "task_id": "t3", "reason": "user declined"}
{"action": "add_task", "text": "Write reflection spec", "priority": "high"}
{"action": "move_task", "task_id": "t1", "note": "moved to morning block"}
</changes>

## Rules
- Never invent events or tasks not discussed
- Never push back on energy/mood assessments
- Keep suggestions to 1 per response
- If user just says "approve" with no changes, don't summarize — just confirm
```

---

## API Design

Lightweight FastAPI server running on the VPS. Serves the webapp and handles all interactions.

```python
# api/server.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Aegis", version="0.1.0")
app.mount("/app", StaticFiles(directory="webapp", html=True), name="webapp")

# --- Routes ---

@app.get("/api/today")
async def get_today():
    """Return current day state: draft, approved plan, or task list."""
    day = load_day_state()
    if day.status == "draft_pending":
        return {"status": "draft", "draft": load_draft(), "freshness": check_freshness()}
    elif day.status in ("negotiating", "active"):
        return {"status": day.status, "plan": load_approved_plan(), "tasks": load_tasks()}
    elif day.status == "completed":
        return {"status": "completed", "summary": load_day_summary()}

@app.post("/api/negotiate")
async def negotiate(message: NegotiateRequest):
    """One round of conversation. Returns agent response + updated draft."""
    session = get_or_create_session()
    response = session.exchange(message.text)
    return {"message": response.message, "draft": response.updated_draft}

@app.post("/api/approve")
async def approve():
    """Lock the plan. Write daily note to vault. Start task tracking."""
    session = get_current_session()
    result = session.approve()
    write_daily_note(result.daily_note)
    write_decisions(result.decisions)
    init_task_tracking(result.daily_note)
    update_day_state("active")
    return {"status": "approved", "tasks": load_tasks()}

@app.post("/api/tasks/{task_id}")
async def update_task(task_id: str, update: TaskUpdate):
    """Update a task: complete, drop, defer, or add notes."""
    tasks = load_tasks()
    if update.action == "complete":
        tasks.complete(task_id, notes=update.notes)
    elif update.action == "drop":
        tasks.drop(task_id, reason=update.reason)
    elif update.action == "defer":
        tasks.defer(task_id, to=update.defer_to)
    save_tasks(tasks)
    record_task_outcome(task_id, update)
    return {"tasks": tasks}

@app.post("/api/tasks")
async def add_task(new_task: NewTaskRequest):
    """Add a task during the day."""
    tasks = load_tasks()
    task = tasks.add(new_task.text, source=TaskSource.AD_HOC, priority=new_task.priority)
    save_tasks(tasks)
    return {"task": task, "tasks": tasks}

@app.get("/api/status")
async def system_status():
    """Health check: state freshness, pipeline status, errors."""
    return {
        "calendar_fresh": not is_stale("calendar_state.json"),
        "news_fresh": not is_stale("news_state.json"),
        "day_status": load_day_state().status,
        "last_fetch": get_last_fetch_time(),
        "errors": get_recent_errors(),
    }
```

**Authentication:** For MVP, the API is only accessible from local network or via Tailscale/WireGuard. No public exposure. Add auth tokens later if needed.

**Tech choice:** FastAPI because it's Python (matches the rest of the stack), has built-in async, auto-generates OpenAPI docs, and is easy to test with `TestClient`.

---

## Webapp Design

Single-page app. No framework — vanilla HTML/CSS/JS. The VPS serves it as static files. Mobile-first since the primary use case is phone-in-bed morning review.

### Screens

**Morning Review (draft_pending / negotiating)**

```
┌────────────────────────────────┐
│  ☀️ Good morning               │
│  Sunday, June 15               │
│                                │
│  ┌──────────────────────────┐  │
│  │ 📰 News                  │  │
│  │ • Anthropic: Claude 4... │  │
│  │ • Boris: monorepo work.. │  │
│  │ • EU AI Act enforcement  │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ 📅 Schedule              │  │
│  │ 09:00 Team standup       │  │
│  │ 14:00 Architecture rev ✕ │  │  ← tap ✕ to negotiate removal
│  │                          │  │
│  │ Tomorrow: Dentist 14:00  │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ ✅ Tasks                  │  │
│  │ ☐ Review PR for auth     │  │
│  │ ☐ Send status update     │  │
│  │ ☐ Write integration test │  │
│  │ + Add task               │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ 🏋️ Training              │  │
│  │ 20/100km this week       │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ 💬 [type to negotiate..] │  │
│  │ Agent: "Ready when you   │  │
│  │ are. Any changes?"       │  │
│  └──────────────────────────┘  │
│                                │
│  [ ✓ Approve Plan ]           │
└────────────────────────────────┘
```

**Active Day (after approval)**

```
┌────────────────────────────────┐
│  Sunday, June 15        active │
│                                │
│  ┌──────────────────────────┐  │
│  │ ✅ Tasks                  │  │
│  │ ☑ Review PR for auth     │  │  ← completed, tap to add note
│  │   "auth needs refactor"  │  │  ← captured note
│  │ ☐ Send status update     │  │
│  │ ☐ Write integration test │  │
│  │ + Add task               │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ 📅 Remaining             │  │
│  │ 14:00 (dropped)          │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ 📊 Day Stats             │  │
│  │ Completed: 1/3           │  │
│  │ Dropped: 1 (arch review) │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

### Task Interactions

**Completing a task:** Tap the checkbox → task marked complete. A small text field slides down for an optional note. Tap away to dismiss without a note.

**Dropping a task:** Swipe left (or tap ✕) → "Why?" prompt appears. Short text input required. This captures the reason.

**Deferring a task:** Swipe right (or tap →) → options: "Tomorrow", "Backlog", or pick a date.

**Adding a task:** Tap "+ Add task" → text input + priority selector (high/normal/low).

All interactions hit the API immediately. No save button. State is always current.

---

## Schema Definitions

Building on v2 schemas, adding new models:

```python
# scripts/schemas.py
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional

CURRENT_SCHEMAS = {
    "calendar": 1,
    "news": 1,
    "day": 1,
    "draft": 1,
    "decisions": 1,
    "tasks": 1,
}

# --- Calendar (unchanged from v2) ---

class CalendarEvent(BaseModel):
    title: str
    start: str
    end: str
    location: str | None = None
    calendar: str | None = None
    all_day: bool = False

class CalendarTomorrowEvent(BaseModel):
    title: str
    start: str
    all_day: bool = False

class CalendarState(BaseModel):
    schema_version: int = Field(default=1)
    fetched_at: str
    date: str
    events: list[CalendarEvent]
    tomorrow_preview: list[CalendarTomorrowEvent] = []

# --- News (unchanged from v2) ---

class NewsItem(BaseModel):
    title: str
    source: str
    url: str
    summary: str
    topic: str
    published: str
    relevance: float = Field(ge=0.0, le=1.0)

class NewsState(BaseModel):
    schema_version: int = Field(default=1)
    fetched_at: str
    items: list[NewsItem]
    errors: list[str] = []

# --- Day Lifecycle (NEW) ---

class DayStatus(str, Enum):
    DRAFT_PENDING = "draft_pending"
    NEGOTIATING = "negotiating"
    ACTIVE = "active"
    COMPLETED = "completed"

class DayState(BaseModel):
    schema_version: int = Field(default=1)
    date: str
    status: DayStatus
    draft_generated_at: str | None = None
    negotiation_started_at: str | None = None
    approved_at: str | None = None
    completed_at: str | None = None

# --- Tasks (NEW) ---

class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    DROPPED = "dropped"
    DEFERRED = "deferred"

class TaskSource(str, Enum):
    TODAY = "today"
    CARRIED_OVER = "carried_over"
    SUGGESTED = "suggested"
    NEGOTIATION = "negotiation"
    AD_HOC = "ad_hoc"

class Task(BaseModel):
    id: str
    text: str
    source: TaskSource
    priority: str = "normal"
    status: TaskStatus = TaskStatus.PENDING
    created_at: str
    completed_at: str | None = None
    notes: str | None = None
    drop_reason: str | None = None
    deferred_to: str | None = None

# --- Decisions (NEW) ---

class DecisionAction(str, Enum):
    DECLINED = "declined"
    ADDED = "added"
    MOVED = "moved"
    REPRIORITIZED = "reprioritized"
    MODIFIED = "modified"
    ACCEPTED_SUGGESTION = "accepted_suggestion"

class Decision(BaseModel):
    timestamp: str
    action: DecisionAction
    target: str
    reason: str | None = None
    energy_note: str | None = None
    context_tag: str | None = None
    agent_suggestion: str | None = None

class DayDecisions(BaseModel):
    schema_version: int = Field(default=1)
    date: str
    negotiation_decisions: list[Decision] = []
    task_outcomes: list[dict] = []

# --- Validation helper (unchanged from v2) ---

def load_state(path: str, model: type[BaseModel]) -> BaseModel | None:
    import json, logging
    log = logging.getLogger("aegis.schema")
    try:
        with open(path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.error(f"Cannot read {path}: {e}")
        return None
    file_version = data.get("schema_version", 1)
    expected = CURRENT_SCHEMAS.get(
        model.__name__.lower().replace("state", "").replace("day", "day"), 1
    )
    if file_version != expected:
        log.warning(f"Schema version mismatch in {path}: "
                    f"got {file_version}, expected {expected}")
        return None
    try:
        return model.model_validate(data)
    except Exception as e:
        log.error(f"Validation failed for {path}: {e}")
        return None
```

---

## Component Specs (Pipeline — unchanged core)

### News Fetcher, Calendar Fetcher, Context Builder

These remain exactly as specified in v2. The pipeline still runs:

```
fetch (cron) → state files → build_context → daily_context.md → agent → draft
```

The only change: the agent now outputs `today_draft.json` (structured) instead of directly writing markdown.

### Daily Planner Agent (modified output)

The agent now produces JSON instead of markdown. The system prompt is updated:

```markdown
You are Aegis Daily Planner.

You receive a daily context briefing and produce a structured daily plan as JSON.

Output ONLY valid JSON matching this structure (no markdown, no explanation):

{
  "news": [{"id": "n1", "topic": "...", "headline": "...", "summary": "...", "url": "...", "relevance": 0.0}],
  "schedule": [{"id": "s1", "time_start": "HH:MM", "time_end": "HH:MM", "title": "...", "location": "...", "all_day": false}],
  "tomorrow_preview": [{"title": "...", "time_start": "HH:MM"}],
  "tasks": [{"id": "t1", "text": "...", "source": "today|carried_over|suggested", "priority": "high|normal|low", "status": "pending"}],
  "training": {"summary": "one line status"},
  "agent_suggestions": ["optional suggestion 1", "optional suggestion 2"]
}

Rules:
- News: 3-5 items, highest relevance first
- Schedule: chronological
- Tasks: from context, suggest 1-2 if light day (mark source: "suggested")
- Training: one-line summary, no coaching
- Never invent events not in the context
```

---

## Cron Pipeline (updated)

The VPS cron now runs the full pipeline including draft generation:

```bash
# crontab
0 6 * * * cd /home/user/aegis && python3 scripts/pipeline.py >> /home/user/vault/.system/logs/pipeline.log 2>&1
```

```python
# scripts/pipeline.py
"""Full morning pipeline: fetch → context → draft. Runs on cron."""

from config import load_config
from fetch.fetch_all import run_fetchers
from build_context import build_context_from_vault
from agent_daily_planner import generate_draft
from schemas import DayState, DayStatus
import json, logging
from datetime import datetime, UTC

log = logging.getLogger("aegis.pipeline")

def main():
    config = load_config()
    vault = config.vault_path

    # 1. Fetch
    run_fetchers(config)

    # 2. Build context
    build_context_from_vault(vault, config)

    # 3. Generate draft
    context = (vault / ".system/context/daily_context.md").read_text()
    draft = generate_draft(context, config)
    (vault / ".system/drafts/today_draft.json").write_text(
        json.dumps(draft, indent=2)
    )

    # 4. Update day state
    day = DayState(
        date=datetime.now().strftime("%Y-%m-%d"),
        status=DayStatus.DRAFT_PENDING,
        draft_generated_at=datetime.now(UTC).isoformat(),
    )
    (vault / ".system/state/day_state.json").write_text(
        day.model_dump_json(indent=2)
    )

    log.info(f"Pipeline complete. Draft ready for {day.date}")

if __name__ == "__main__":
    main()
```

---

## Writing Back to Vault

When the plan is approved, the API writes two things:

**1. `Daily/YYYY-MM-DD.md`** — the human-readable daily note for Obsidian:

```python
def render_daily_note(draft: dict, decisions: list[Decision]) -> str:
    """Convert approved draft + decisions into Obsidian-ready markdown."""
    lines = [
        "---",
        f"date: {draft['date']}",
        "type: daily",
        "generated: true",
        "---",
        "",
        f"# {format_weekday(draft['date'])}",
        "",
        "## News",
    ]
    for item in draft["news"]:
        lines.append(f"- **{item['topic']}** {item['headline']} — [link]({item['url']})")
    
    lines.extend(["", "## Schedule"])
    for event in draft["schedule"]:
        lines.append(f"- {event['time_start']}–{event['time_end']} — {event['title']}")
    
    if draft.get("tomorrow_preview"):
        tomorrow = draft["tomorrow_preview"]
        lines.append(f"\n**Tomorrow:** {tomorrow[0]['title']} at {tomorrow[0]['time_start']}")
    
    lines.extend(["", "## Tasks"])
    for task in draft["tasks"]:
        prefix = "⭐ " if task["priority"] == "high" else ""
        lines.append(f"- [ ] {prefix}{task['text']}")
    
    lines.extend(["", "## Training", draft["training"]["summary"]])
    
    if decisions:
        lines.extend(["", "## Morning Decisions"])
        for d in decisions:
            lines.append(f"- {d.action.value}: {d.target}" +
                        (f" — {d.reason}" if d.reason else ""))
    
    lines.extend(["", "---", f"*Generated by Aegis at {format_time_now()}*"])
    return "\n".join(lines)
```

**2. Task file sync** — approved tasks update `data/tasks/today.md` so Obsidian reflects the current plan. Completed/dropped/deferred tasks are written back at end of day.

---

## Configuration (updated)

```toml
# aegis.toml

[vault]
path = "/home/user/vault"

[fetch]
cron_hour = 6
max_state_age_hours = 2

[context]
token_budget = 2000
news_max_items = 10

[agent]
runtime = "claude_api"
model = "claude-sonnet-4-20250514"
max_tokens = 1500
planner_prompt_path = ".system/config/daily_template.md"
negotiation_prompt_path = ".system/config/negotiation_template.md"

[api]
host = "0.0.0.0"
port = 8420
allowed_origins = ["http://localhost:8420"]  # add tailscale IP later

[logging]
level = "INFO"
```

---

## Testing Strategy (updated from v2)

### New Test Files

```
tests/
  ... (all v2 tests unchanged) ...
  test_api.py                  ← API endpoint tests
  test_negotiation.py          ← negotiation session tests
  test_task_lifecycle.py       ← task state transitions
  test_day_lifecycle.py        ← day state machine
  test_draft_format.py         ← draft JSON structure
```

### API Tests (`test_api.py`)

```python
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)

class TestTodayEndpoint:
    def test_returns_draft_when_pending(self, mock_draft_state):
        response = client.get("/api/today")
        assert response.status_code == 200
        assert response.json()["status"] == "draft"
        assert "news" in response.json()["draft"]

    def test_returns_tasks_when_active(self, mock_active_state):
        response = client.get("/api/today")
        assert response.json()["status"] == "active"
        assert "tasks" in response.json()

class TestNegotiation:
    def test_exchange_returns_response(self, mock_draft_state):
        response = client.post("/api/negotiate", json={"text": "drop the standup"})
        assert response.status_code == 200
        assert "message" in response.json()
        assert "draft" in response.json()

    def test_approve_writes_daily_note(self, mock_negotiating_state, tmp_vault):
        response = client.post("/api/approve")
        assert response.status_code == 200
        assert (tmp_vault / "Daily" / today_filename()).exists()

class TestTaskUpdates:
    def test_complete_task(self, mock_active_state):
        response = client.post("/api/tasks/t1", json={
            "action": "complete",
            "notes": "done, needs followup"
        })
        assert response.status_code == 200
        tasks = response.json()["tasks"]
        t1 = next(t for t in tasks["tasks"] if t["id"] == "t1")
        assert t1["status"] == "completed"
        assert t1["notes"] == "done, needs followup"

    def test_drop_requires_reason(self, mock_active_state):
        response = client.post("/api/tasks/t1", json={"action": "drop"})
        assert response.status_code == 422  # missing reason

    def test_add_task_during_day(self, mock_active_state):
        response = client.post("/api/tasks", json={
            "text": "urgent bug fix",
            "priority": "high"
        })
        assert response.status_code == 200
        new_task = response.json()["task"]
        assert new_task["source"] == "ad_hoc"
```

### Task Lifecycle Tests (`test_task_lifecycle.py`)

```python
from schemas import DayTasks, Task, TaskStatus, TaskSource

class TestTaskTransitions:
    def test_complete_with_notes(self):
        tasks = make_sample_tasks()
        tasks.complete("t1", notes="went well")
        assert tasks.tasks[0].status == TaskStatus.COMPLETED
        assert tasks.tasks[0].notes == "went well"
        assert tasks.tasks[0].completed_at is not None

    def test_drop_requires_reason(self):
        tasks = make_sample_tasks()
        tasks.drop("t1", reason="not relevant anymore")
        assert tasks.tasks[0].status == TaskStatus.DROPPED
        assert tasks.tasks[0].drop_reason == "not relevant anymore"

    def test_defer_sets_target(self):
        tasks = make_sample_tasks()
        tasks.defer("t1", to="tomorrow")
        assert tasks.tasks[0].status == TaskStatus.DEFERRED
        assert tasks.tasks[0].deferred_to == "tomorrow"

    def test_cannot_complete_dropped_task(self):
        tasks = make_sample_tasks()
        tasks.drop("t1", reason="nope")
        with pytest.raises(ValueError):
            tasks.complete("t1")

    def test_add_ad_hoc_task(self):
        tasks = make_sample_tasks()
        new = tasks.add("urgent fix", source=TaskSource.AD_HOC, priority="high")
        assert new.source == TaskSource.AD_HOC
        assert new.status == TaskStatus.PENDING
        assert len(tasks.tasks) == 4  # 3 original + 1 new
```

### Negotiation Tests (`test_negotiation.py`)

```python
class TestNegotiationSession:
    def test_exchange_updates_draft(self, mock_runtime):
        session = NegotiationSession(
            draft=sample_draft(),
            context="...",
            runtime=mock_runtime,
        )
        mock_runtime.set_response("Removed architecture review.", 
            changes=[{"action": "drop_task", "task_id": "t3"}])
        
        response = session.exchange("drop the architecture review")
        assert "t3" not in [t["id"] for t in response.updated_draft["tasks"] 
                           if t["status"] == "pending"]

    def test_decisions_captured(self, mock_runtime):
        session = NegotiationSession(draft=sample_draft(), context="...", runtime=mock_runtime)
        mock_runtime.set_response("Done.", changes=[{"action": "drop_task", "task_id": "t1"}])
        session.exchange("drop PR review, too tired")
        assert len(session.decisions) == 1
        assert session.decisions[0].action == DecisionAction.DECLINED

    def test_approve_returns_all_data(self, mock_runtime):
        session = NegotiationSession(draft=sample_draft(), context="...", runtime=mock_runtime)
        result = session.approve()
        assert result.daily_note  # markdown string
        assert isinstance(result.decisions, list)
        assert isinstance(result.conversation_log, list)
```

### When to Run What (updated)

| Trigger | Command | Needs network? |
|---------|---------|---------------|
| Edited context template | `make test-context` | No |
| Edited a fetcher | `make test-fetch` | No (mocked) |
| Changed agent prompt | `make test-agent` | No (fixture) |
| Edited API routes | `make test-api` | No |
| Edited negotiation logic | `make test-negotiate` | No |
| Edited task logic | `make test-tasks` | No |
| Before pushing to git | `make test` | No |
| Weekly sanity | `make test-all` | Yes |

---

## Makefile (updated)

```makefile
.PHONY: test test-all test-schema test-context test-fetch test-agent \
        test-api test-negotiate test-tasks \
        fetch start-day serve lint check-state

# --- Testing ---
test:                              ## All fast tests (no API calls)
	cd scripts && python -m pytest tests/ -v -k "not slow"

test-all:                          ## All tests including slow agent tests
	cd scripts && python -m pytest tests/ -v

test-schema:
	cd scripts && python -m pytest tests/test_schemas.py -v

test-context:
	cd scripts && python -m pytest tests/test_context_builder.py -v

test-fetch:
	cd scripts && python -m pytest tests/test_fetchers.py -v

test-agent:
	cd scripts && python -m pytest tests/test_agent_output.py -v

test-api:                          ## API endpoint tests
	cd scripts && python -m pytest tests/test_api.py -v

test-negotiate:                    ## Negotiation session tests
	cd scripts && python -m pytest tests/test_negotiation.py -v

test-tasks:                        ## Task lifecycle tests
	cd scripts && python -m pytest tests/test_task_lifecycle.py tests/test_day_lifecycle.py -v

# --- Operations ---
fetch:                             ## Run all fetchers now
	cd scripts && python -m fetch.fetch_all

pipeline:                          ## Run full pipeline (fetch → context → draft)
	cd scripts && python pipeline.py

serve:                             ## Start API server
	cd scripts && uvicorn api.server:app --host 0.0.0.0 --port 8420 --reload

serve-prod:                        ## Start API server (production)
	cd scripts && uvicorn api.server:app --host 0.0.0.0 --port 8420

check-state:                       ## Check state file freshness
	cd scripts && python build_context.py --check-only

# --- Code quality ---
lint:
	cd scripts && python -m mypy *.py fetch/ api/ --ignore-missing-imports
	cd scripts && ruff check .

help:
	@grep -E '^[a-zA-Z_-]+:.*##' Makefile | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
```

---

## `pyproject.toml` (updated)

```toml
[project]
name = "aegis"
version = "0.3.0"
description = "Personal intelligence system — daily note pipeline with interactive review"
requires-python = ">=3.11"

dependencies = [
    "anthropic>=0.40.0",
    "pydantic>=2.0",
    "feedparser>=6.0",
    "google-api-python-client>=2.0",
    "google-auth-oauthlib>=1.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27.0",          # for FastAPI TestClient
    "ruff>=0.5",
    "mypy>=1.10",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: tests that call real APIs (deselect with -k 'not slow')",
]

[tool.ruff]
line-length = 100

[tool.mypy]
python_version = "3.11"
warn_return_any = true
```

---

## `CLAUDE.md` (updated)

```markdown
# Aegis — Claude Code Context

## What is this?
Personal intelligence system. Fetches news + calendar, builds context,
generates a daily plan draft. User reviews and negotiates via webapp.
Tasks are tracked throughout the day with feedback notes.
All decisions and outcomes feed a future user model.

## Architecture (5 sentences)
VPS cron runs pipeline at 06:00: fetch → context → agent draft.
FastAPI server on VPS serves webapp + API.
User opens webapp, reviews draft, negotiates via chat, approves.
During the day, user marks tasks complete/dropped with notes via webapp.
All data (drafts, decisions, task outcomes) stored as versioned JSON in vault/.system/.

## Key invariants — DO NOT BREAK
- Pipeline writes to .system/ only (state, context, drafts)
- Daily/ written only on explicit user approval via API
- data/tasks/ synced on approval and end-of-day
- All state files validated by Pydantic before use
- Invalid/missing state = graceful skip, never crash
- Task drops require a reason (never skip this validation)
- Day has a lifecycle: draft_pending → negotiating → active → completed
- Config in aegis.toml, no hardcoded paths

## Code layout
- Pipeline scripts: ~/aegis/scripts/
- API server: ~/aegis/api/
- Webapp: ~/aegis/webapp/
- Tests: ~/aegis/tests/
- Config: ~/aegis/aegis.toml
- Vault: ~/vault/ (syncthing-synced, separate)

## Before finishing a session
1. `make test` — all fast tests must pass
2. If schema changed → `make test-schema`
3. If API changed → `make test-api`
4. If negotiation changed → `make test-negotiate`
5. If task logic changed → `make test-tasks`

## Tech stack
Python 3.11+, FastAPI, Pydantic, anthropic SDK, feedparser, Google Calendar API
Frontend: vanilla HTML/CSS/JS (no framework)
Testing: pytest + httpx. Linting: ruff + mypy.
```

---

## Failure Handling (updated)

| Failure | Detection | Behavior |
|---------|-----------|----------|
| Pipeline fails at 06:00 | No draft file, day_state missing | Webapp shows "Draft not ready" + system status |
| News fetch fails | `errors` in news_state.json | Draft generated without news section |
| Calendar fetch fails | State missing/stale | Draft says "Calendar unavailable" |
| State file invalid schema | Pydantic validation | Section skipped, error logged |
| Agent produces bad JSON | try/except + JSON parse | Fallback: raw context shown as draft text |
| API server down | Webapp can't reach /api/today | Webapp shows offline message + retry button |
| Negotiation agent fails | try/except in /api/negotiate | Return error message, keep draft as-is |
| Task update fails | API returns error | Webapp shows retry, state preserved |
| Syncthing lag | State files stale | Draft shows staleness warning |
| Daily note write fails | try/except in /api/approve | Return error, don't update day_state |

---

## Future-Proofing (updated)

| Future feature | How current architecture preserves the path |
|---------------|---------------------------------------------|
| New data source | Add fetcher + schema + context template. Pipeline unchanged. |
| New agent | Add agent script + prompt file. Runtime interface reused. |
| Event-driven triggers | Replace cron with file watchers. State file format unchanged. |
| Patch proposals | Add new output mode to agents. API gets new endpoint. |
| SQLite migration | Pydantic models define schemas. Swap JSON for ORM mechanically. |
| User model / second brain | Decision + task outcome data already captured. See roadmap below. |
| Push notifications | API already knows day state. Add webhook/push on draft ready. |
| Multiple users | Config is per-vault. API adds auth layer. |

---

## Second Brain Roadmap

This section documents the path from "daily planner" to "system that understands how you work." Not built in MVP, but every design decision above is made with this in mind.

### What's already being captured in MVP

From day one, the system accumulates:

1. **Daily plans** — what was planned each day (`Daily/YYYY-MM-DD.md`)
2. **Negotiation decisions** — what you changed and why (`decisions.json`)
3. **Task outcomes** — completed/dropped/deferred with notes and timestamps
4. **Task sources** — which tasks came from you vs. agent suggestions
5. **Energy/mood signals** — extracted from negotiation reasons ("too tired", "low energy")
6. **Timing patterns** — when you approve, when you complete tasks, when you defer

This is already a rich behavioral dataset after 30 days.

### Phase A: Reflection Agent (post-MVP, ~2 weeks after stabilization)

A weekly agent that reads the last 7 days of:
- Daily notes
- Decision logs
- Task outcome data

Produces:
- `Weekly_Patterns.md` — what happened this week
- Updates to `user_model.json` — persistent pattern database

Example patterns it would detect:
- "Declined 8/12 afternoon meetings — cites energy 6 times"
- "Task completion rate drops on Wednesdays"
- "Always defers documentation tasks — completed 2/15 in past month"
- "Adds ad-hoc tasks 3x/week, usually current side project"
- "Accepts agent task suggestions 70% of the time"

### Phase B: User Model Integration

The user model becomes additional context for the Daily Planner and Negotiation agents:

```json
{
  "schema_version": 1,
  "updated_at": "2025-07-20T20:00:00Z",
  "patterns": {
    "energy": {
      "high_windows": ["Tue 08:00-12:00", "Wed 09:00-11:00"],
      "low_windows": ["daily after 15:00", "Mon morning"],
      "meeting_tolerance": "2 per day max, prefers morning"
    },
    "tasks": {
      "completion_rate_4w": 0.68,
      "chronic_deferrals": ["documentation", "finance review"],
      "preferred_types": ["coding", "architecture", "research"],
      "estimation_bias": "underestimates by ~30%"
    },
    "decisions": {
      "decline_triggers": ["energy", "competing priority", "mood"],
      "suggestion_acceptance_rate": 0.72,
      "most_added_categories": ["current side project", "urgent fixes"]
    },
    "training": {
      "stated_preference": "morning rides",
      "actual_pattern": "evening rides 70%",
      "weekly_adherence": 0.6
    }
  }
}
```

The Daily Planner then uses this:

```
"Light meeting day. Based on your patterns, your focus block is 
08:00-12:00 — I've placed the complex PR review there. Documentation 
task carried over 3 weeks — consider dropping or committing this week."
```

### Phase C: Proactive Suggestions

Once the model is mature (2-3 months of data), agents can:
- Predict which tasks you'll defer (and suggest dropping them upfront)
- Recommend schedule changes based on energy patterns
- Detect when interests shift and adjust news briefing topics
- Notice when you're overloaded and suggest lighter days
- Flag when stated goals diverge from actual behavior (training, finance)

### What MVP must do to enable this

Everything above works because MVP captures structured decisions and outcomes. The critical design choices that enable the second brain:

1. **Task drops require reasons** — this captures decision logic, not just outcomes
2. **Negotiation is structured** — decisions are logged as typed data, not buried in chat
3. **Task notes are optional but available** — friction-free when you want to skip, valuable when you don't
4. **Everything has timestamps** — enables time-of-day pattern detection
5. **Draft is JSON, not markdown** — structured data from the start, not parsing markdown later

---

## Implementation Order (final)

### Phase 1 — Skeleton + Test Infrastructure (day 1)

- [ ] Init `aegis/` git repo
- [ ] Create `pyproject.toml`, install deps
- [ ] Create `aegis.toml` with paths
- [ ] Create vault folder structure (`~/vault/...`)
- [ ] Write `schemas.py` with all Pydantic models
- [ ] Create all fixture files in `tests/fixtures/`
- [ ] Write `conftest.py`
- [ ] Write + pass `test_schemas.py`
- [ ] Write `config.py` + `test_config.py`
- [ ] Write `CLAUDE.md` and `Makefile`
- [ ] Confirm: `make test` passes

### Phase 2 — Context Builder (day 2)

- [ ] Implement `build_context.py` (all four context templates + merge)
- [ ] Write + pass `test_context_builder.py`
- [ ] Manually verify `daily_context.md` output looks right
- [ ] Confirm: `make test-context` passes

### Phase 3 — Calendar Pipeline (day 3-4)

- [ ] Set up Google Calendar API credentials
- [ ] Implement `calendar_fetcher.py`
- [ ] Write + pass `test_fetchers.py::TestCalendarFetcher`
- [ ] Run fetcher for real, inspect `calendar_state.json`
- [ ] Confirm: real calendar context in `daily_context.md`

### Phase 4 — News Pipeline (day 4-6)

- [ ] Find RSS feeds (Anthropic blog, AI news aggregators)
- [ ] Implement `news_fetcher.py` with `RSSNewsFetcher`
- [ ] Write + pass `test_fetchers.py::TestRSSNewsFetcher`
- [ ] Run fetcher for real, inspect `news_state.json`
- [ ] Confirm: real news context in `daily_context.md`

### Phase 5 — Agent + Draft Generation (day 6-7)

- [ ] Implement `runtime.py` with chosen implementation
- [ ] Write `daily_template.md` (JSON output prompt)
- [ ] Write `agent_daily_planner.py` (outputs `today_draft.json`)
- [ ] Generate first real draft
- [ ] Save as `tests/fixtures/sample_draft.json`
- [ ] Write + pass `test_draft_format.py`
- [ ] Write `pipeline.py` (full fetch → context → draft)

### Phase 6 — API Server (day 8-10)

- [ ] Set up FastAPI project in `api/`
- [ ] Implement `/api/today` endpoint
- [ ] Implement `/api/approve` endpoint (writes daily note)
- [ ] Implement `/api/tasks` endpoints (CRUD + status updates)
- [ ] Write + pass `test_api.py`
- [ ] Write + pass `test_task_lifecycle.py`
- [ ] Write + pass `test_day_lifecycle.py`

### Phase 7 — Negotiation (day 10-12)

- [ ] Write `negotiation_template.md`
- [ ] Implement `negotiation.py` session manager
- [ ] Implement `/api/negotiate` endpoint
- [ ] Write + pass `test_negotiation.py`
- [ ] Test full loop: draft → negotiate → approve → daily note

### Phase 8 — Webapp (day 12-15)

- [ ] Build morning review screen (shows draft, negotiate input, approve button)
- [ ] Build active day screen (task list with complete/drop/defer)
- [ ] Build task note input (slide-down on completion)
- [ ] Mobile-responsive layout
- [ ] Connect all screens to API endpoints
- [ ] Test on phone

### Phase 9 — Automation + Hardening (day 15-17)

- [ ] Set up cron for `pipeline.py` on VPS
- [ ] Set up `uvicorn` as systemd service on VPS
- [ ] Set up Syncthing (vault data only)
- [ ] Deploy `aegis/` to VPS via git
- [ ] Configure Tailscale/WireGuard for remote access
- [ ] Write + pass `test_pipeline.py`
- [ ] Confirm: `make test` passes on both laptop and VPS

### Phase 10 — Stabilization (day 17-28)

- [ ] Run full morning loop daily for 7+ days
- [ ] Fix prompt issues as they surface
- [ ] Fix webapp UX friction points
- [ ] Update fixture files after prompts stabilize
- [ ] Run `make test-all` (including real agent tests)
- [ ] Declare MVP done when 7 consecutive days produce useful, approved plans
- [ ] Review accumulated decision data — confirm it's structured enough for future reflection agent

---

## What This Spec Deliberately Excludes

- Voice capture pipeline
- Patch proposal system
- Knowledge Distiller / weekly summaries (see Second Brain Roadmap Phase A)
- Project Monitor agent
- Training Coach agent
- Event-driven architecture (MVP uses cron)
- SQLite (JSON sufficient at this scale)
- Push notifications (check webapp manually for now)
- User model / reflection agent (data capture is in place; processing comes later)

---

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Repo vs vault | Separate (`aegis/` + `vault/`) | Bad code can't propagate via Syncthing |
| Interface | Webapp (FastAPI + vanilla JS) | Works on phone + laptop, no manual script running |
| Draft format | JSON (not markdown) | Webapp needs structured data; markdown rendered on approve |
| Task lifecycle | Explicit state machine with reasons | Captures decision logic for user model |
| Task drop | Requires reason | Most valuable signal for pattern detection |
| Task notes | Optional on complete/defer | Low friction but available when useful |
| Negotiation | Chat in webapp via API | Natural language, structured decisions extracted |
| VPS role | Full pipeline + API server | Draft ready before waking up, no manual triggers |
| Context building | Deterministic Python templates | Free, fast, predictable |
| Agent runtime | Abstract interface | Decide implementation later |
| News sources | Abstract interface | Start with RSS, add later |
| State validation | Pydantic models with schema_version | Catches regressions, supports migration |
| Webapp tech | Vanilla HTML/CSS/JS | No build step, easy to iterate |
| Second brain | Data capture now, processing later | MVP decisions/outcomes feed future reflection agent |
| Testing | Layered pytest (schema → context → fetch → api → negotiate → task → pipeline) | Each layer catches different failures |
| Config | Single `aegis.toml` | One place for all settings |
| MVP success | 7 consecutive useful days | Must actually use it, not just build it |
