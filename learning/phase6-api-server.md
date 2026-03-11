# Phase 6: FastAPI Server + Endpoints

## Overview

Phase 6 implements the API layer that connects the vault state files (written by the pipeline) to the webapp (built in Phase 8). It introduces FastAPI, TestClient testing, config injection patterns, and vault I/O.

---

## FastAPI App Factory Pattern

Instead of creating the app at module level and hoping config is ready, use a factory function:

```python
def create_app() -> FastAPI:
    config = get_config()
    app = FastAPI(title="Cadence", version="0.3.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins, ...)
    app.include_router(router)
    return app

app = create_app()  # Still create a module-level app for uvicorn
```

**Why:** The factory makes the app testable — you can call `create_app()` fresh in each test without leftover state.

---

## Lifespan Handler

FastAPI 0.93+ uses `@asynccontextmanager` for startup/shutdown:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic here
    logger.info("Starting up...")
    yield
    # Shutdown logic here (after yield)
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)
```

The lifespan runs once when the server starts, unlike `@app.on_event("startup")` which is deprecated.

---

## CORS Middleware

Required for the webapp (running at the same origin) to call the API. Add it early:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8420"],  # From config
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, `allow_origins` should be a specific list, never `["*"]`.

---

## Static File Mount (try/except)

Mounting static files fails if the directory doesn't exist:

```python
try:
    app.mount("/app", StaticFiles(directory="webapp", html=True), name="webapp")
except RuntimeError:
    logger.warning("webapp/ not found — static serving disabled")
```

The `html=True` flag makes FastAPI serve `index.html` for directory requests (SPA routing).

---

## `@lru_cache` Config Injection

For a personal tool, a module-level cached config is clean and testable:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()
```

**Why lru_cache over just a global:** `lru_cache` can be cleared between test runs with `get_config.cache_clear()`, preventing test pollution.

**In tests:**
```python
import api.routes as routes_module

@pytest.fixture
def api_client(vault_path, config, monkeypatch):
    cfg = dataclasses.replace(config, vault_path=vault_path)
    routes_module.get_config.cache_clear()
    monkeypatch.setattr(routes_module, "get_config", lambda: cfg)
    return TestClient(create_app())
```

`monkeypatch.setattr` replaces the entire function (not the cached value), so the lambda is called directly — no cache issues. `monkeypatch` automatically undoes the setattr after each test.

---

## FastAPI TestClient

FastAPI's `TestClient` wraps `httpx` and runs the app synchronously in tests:

```python
from fastapi.testclient import TestClient

client = TestClient(app)
response = client.get("/api/today")
assert response.status_code == 200
assert response.json()["status"] == "no_draft"
```

**Writing state files for tests:** Since routes read real files from disk, write state JSON to `vault_path` (a `tmp_path` directory) before calling the endpoint:

```python
def test_get_today_returns_draft(api_client, vault_path, sample_draft, sample_day_state):
    vault = Path(vault_path)
    (vault / ".system" / "state" / "day_state.json").write_text(json.dumps(sample_day_state))
    (vault / ".system" / "drafts" / "today_draft.json").write_text(json.dumps(sample_draft))
    response = api_client.get("/api/today")
    assert response.json()["status"] == "draft"
```

This approach tests the actual file-reading code path without over-mocking.

---

## Vault State File Read/Write Pattern

**Reading:** Use `load_state()` from `scripts/schemas.py`:

```python
from scripts.schemas import load_state, DayState

day_state = load_state(str(state_path), DayState)
# Returns None if file missing, invalid JSON, or schema mismatch
if day_state is None:
    return {"status": "no_draft"}
```

**Writing:** Use a private helper that creates parent dirs:

```python
def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)

_write_json(_state(config, "tasks_today.json"), day_tasks.model_dump())
```

**Note:** `model_dump()` serializes enums to their string values (e.g., `"pending"` not `TaskStatus.PENDING`) because Pydantic v2 enums are `str, Enum` subclasses.

---

## HTTP Status Code Semantics

| Code | Meaning | Used for |
|---|---|---|
| 200 | OK | Successful read or mutation |
| 409 | Conflict | Business rule violation (day already approved, task list not active) |
| 422 | Unprocessable Entity | Validation failure (drop without reason, invalid action) |
| 404 | Not Found | Task not found in the list |
| 503 | Service Unavailable | Pipeline hasn't run yet (draft missing) |

**Key distinction:** 404 = "we looked but couldn't find it"; 409 = "state machine won't allow this operation right now".

---

## Day Lifecycle State Machine

```
[pipeline runs]
      ↓
DRAFT_PENDING  ─── POST /api/negotiate ──→  NEGOTIATING
      │                                          │
      └──────── POST /api/approve ───────────────┘
                        ↓
                     ACTIVE  ─── POST /api/tasks/:id ──→ (same ACTIVE)
                        ↓
                  COMPLETED  (manual or end-of-day cron)
```

**State is stored in:** `vault/.system/state/day_state.json`

**Each transition writes the new `day_state.json`** with a timestamp (negotiation_started_at, approved_at, completed_at).

---

## Approve Endpoint: DraftTaskItem → Task Conversion

The draft stores tasks as `DraftTaskItem` (minimal schema). On approval, convert to full `Task` objects:

```python
tasks = [
    Task(
        id=dt.id,
        text=dt.text,
        source=dt.source,        # TaskSource enum from draft
        priority=dt.priority,
        status=TaskStatus.PENDING,  # Always reset to pending on approve
        created_at=datetime.now().isoformat() + "Z",
    )
    for dt in draft.tasks
]
day_tasks = DayTasks(date=draft.date, tasks=tasks)
```

**Why reset to PENDING:** The draft may have stale statuses from a previous run. On approval, all tasks start fresh.

---

## Freshness Check via File mtime

Instead of parsing `fetched_at` from inside the JSON (fragile), use file modification time:

```python
def _is_fresh(path: Path, max_age_hours: int) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age.total_seconds() < max_age_hours * 3600
```

**Tradeoff:** If someone manually edits the file, mtime changes even without new data. But for a cron-driven pipeline, mtime == fetch time is a safe assumption.

---

## Key Files

| File | Purpose |
|---|---|
| `api/server.py` | App factory, CORS, static mount, lifespan |
| `api/routes.py` | All 6 endpoints + vault helpers + config injection |
| `api/negotiation.py` | NegotiationSession stub (Phase 7 implements) |
| `tests/conftest.py` | `api_client` fixture (TestClient + monkeypatching) |
| `tests/test_api.py` | HTTP-level endpoint tests |
| `tests/test_task_lifecycle.py` | DayTasks mutation tests (no HTTP) |
| `tests/test_day_lifecycle.py` | DayState transition tests (no HTTP) |
