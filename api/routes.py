"""
API route handlers.

All 6 endpoints for daily review, negotiation, approval, and task tracking.
"""

import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional, Type, TypeVar, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.negotiation import NegotiationSession
from scripts.config import Config, load_config
from scripts.runtime import ClaudeRuntime
from scripts.schemas import (
    DayState,
    DayStatus,
    DayTasks,
    Draft,
    Task,
    TaskSource,
    TaskStatus,
)
from scripts.schemas import (
    load_state as _load_state,
)

_T = TypeVar("_T", bound=BaseModel)


def _load(path: Path, model: Type[_T]) -> Optional[_T]:
    """Typed wrapper around load_state for mypy compatibility."""
    return cast(Optional[_T], _load_state(str(path), model))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cadence"])


# ============================================================================
# Config injection (monkeypatch-friendly for tests)
# ============================================================================

@lru_cache(maxsize=1)
def get_config() -> Config:
    """Load and cache config. Clear cache in tests with get_config.cache_clear()."""
    return load_config()


# ============================================================================
# Vault path helpers
# ============================================================================

def _vault(config: Config) -> Path:
    return Path(config.vault_path)


def _state(config: Config, filename: str) -> Path:
    return _vault(config) / ".system" / "state" / filename


def _drafts_path(config: Config) -> Path:
    return _vault(config) / ".system" / "drafts" / "today_draft.json"


def _is_fresh(path: Path, max_age_hours: int) -> bool:
    """Return True if file exists and was written within max_age_hours."""
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age.total_seconds() < max_age_hours * 3600


def _write_json(path: Path, data: dict) -> None:
    """Write dict to JSON file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)


# ============================================================================
# Daily note renderer
# ============================================================================

def _render_daily_note(draft: Draft) -> str:
    """Render draft as Obsidian-friendly markdown daily note."""
    lines = [f"# {draft.date}", ""]

    if draft.news:
        lines.append("## News")
        for item in draft.news:
            lines.append(f"- [{item.headline}]({item.url}) — {item.summary}")
        lines.append("")

    if draft.schedule:
        lines.append("## Schedule")
        for event in draft.schedule:
            if event.all_day:
                lines.append(f"- All day: {event.title}")
            else:
                loc = f" ({event.location})" if event.location else ""
                lines.append(f"- {event.time_start}–{event.time_end}: {event.title}{loc}")
        lines.append("")

    if draft.tasks:
        lines.append("## Tasks")
        for task in draft.tasks:
            lines.append(f"- [ ] {task.text} ({task.priority})")
        lines.append("")

    lines.append("## Training")
    lines.append(draft.training.summary)
    lines.append("")

    if draft.agent_suggestions:
        lines.append("## Suggestions")
        for suggestion in draft.agent_suggestions:
            lines.append(f"- {suggestion}")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Request/Response Models
# ============================================================================

class NegotiateRequest(BaseModel):
    """Negotiate endpoint request."""
    text: str


class TaskUpdateRequest(BaseModel):
    """Task update endpoint request."""
    action: str  # "complete", "drop", "defer"
    reason: Optional[str] = None
    defer_to: Optional[str] = None
    notes: Optional[str] = None


class TaskCreateRequest(BaseModel):
    """Task creation endpoint request."""
    text: str
    priority: str = "normal"  # "high", "normal", "low"


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/today")
async def get_today() -> dict:
    """
    Get current day state: draft, active plan, or completed.

    Returns JSON with status and content based on day_state.json.
    """
    config = get_config()

    day_state = _load(_state(config, "day_state.json"), DayState)
    if day_state is None:
        return {"status": "no_draft"}

    cal_fresh = _is_fresh(_state(config, "calendar_state.json"), config.max_state_age_hours)
    news_fresh = _is_fresh(_state(config, "news_state.json"), config.max_state_age_hours)

    if day_state.status in (DayStatus.DRAFT_PENDING, DayStatus.NEGOTIATING):
        draft = _load(_drafts_path(config), Draft)
        draft_dict = draft.model_dump() if draft else None
        return {
            "status": "draft",
            "draft": draft_dict,
            "freshness": {"calendar": cal_fresh, "news": news_fresh},
        }

    if day_state.status == DayStatus.ACTIVE:
        draft = _load(_drafts_path(config), Draft)
        tasks = _load(_state(config, "tasks_today.json"), DayTasks)

        # Calculate day stats
        stats = {
            "completed": 0,
            "remaining": 0,
            "deferred": 0,
            "dropped": 0,
        }
        if tasks:
            for task in tasks.tasks:
                if task.status == TaskStatus.COMPLETED:
                    stats["completed"] += 1
                elif task.status == TaskStatus.DROPPED:
                    stats["dropped"] += 1
                elif task.status == TaskStatus.DEFERRED:
                    stats["deferred"] += 1
                else:
                    stats["remaining"] += 1

        return {
            "status": "active",
            "plan": draft.model_dump() if draft else None,
            "schedule": draft.schedule if draft else [],
            "tasks": tasks.model_dump() if tasks else None,
            "stats": stats,
        }

    # COMPLETED
    return {"status": "completed"}


@router.post("/negotiate")
async def negotiate(req: NegotiateRequest) -> dict:
    """
    One round of negotiation with agent.

    Accepts user feedback, calls negotiation agent with current draft,
    applies mutations, persists history and updated draft.
    """
    config = get_config()
    vault = _vault(config)

    # Load current draft
    draft = _load(_drafts_path(config), Draft)
    if draft is None:
        raise HTTPException(status_code=404, detail="No draft available")

    # Load or create day_state; advance to NEGOTIATING
    day_state = _load(_state(config, "day_state.json"), DayState)
    if day_state and day_state.status == DayStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Day already approved")
    if day_state and day_state.status == DayStatus.DRAFT_PENDING:
        day_state.status = DayStatus.NEGOTIATING
        day_state.negotiation_started_at = datetime.now().isoformat() + "Z"
        _write_json(_state(config, "day_state.json"), day_state.model_dump())

    # Load context
    context_path = vault / ".system" / "context" / "daily_context.md"
    context = context_path.read_text() if context_path.exists() else ""

    # Load conversation history
    history_path = _state(config, "negotiation_history.json")
    history: list[dict] = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text())
        except Exception as e:
            logger.warning(f"Failed to load negotiation history: {e}")
            history = []

    # Run exchange
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    runtime = ClaudeRuntime(model=config.agent_model, api_key=api_key)
    session = NegotiationSession(
        draft=draft.model_dump(),
        context=context,
        runtime=runtime,
        vault_path=str(vault),
        history=history,
    )
    result = session.exchange(req.text)

    # Persist updated draft and history
    _write_json(_drafts_path(config), result["draft"])
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(session.history))

    return result


@router.post("/approve")
async def approve() -> dict:
    """
    Approve the plan.

    Locks draft, writes daily note, initializes task tracking, updates day_state to active.
    """
    config = get_config()

    day_state = _load(_state(config, "day_state.json"), DayState)
    if day_state and day_state.status == DayStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Day already approved")

    draft = _load(_drafts_path(config), Draft)
    if draft is None:
        raise HTTPException(
            status_code=503, detail="Draft not available — pipeline may not have run"
        )

    # Build DayTasks from draft
    now = datetime.now().isoformat() + "Z"
    tasks = [
        Task(
            id=dt.id,
            text=dt.text,
            source=dt.source,
            priority=dt.priority,
            status=TaskStatus.PENDING,
            created_at=now,
        )
        for dt in draft.tasks
    ]
    day_tasks = DayTasks(date=draft.date, tasks=tasks)
    _write_json(_state(config, "tasks_today.json"), day_tasks.model_dump())

    # Write daily note
    note_content = _render_daily_note(draft)
    note_path = _vault(config) / "Daily" / f"{draft.date}.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note_content)

    # Update day state to active
    if day_state is None:
        day_state = DayState(date=draft.date, status=DayStatus.ACTIVE, approved_at=now)
    else:
        day_state.status = DayStatus.ACTIVE
        day_state.approved_at = now
    _write_json(_state(config, "day_state.json"), day_state.model_dump())

    return {
        "status": "approved",
        "note_path": f"Daily/{draft.date}.md",
        "tasks": day_tasks.model_dump(),
    }


@router.post("/tasks")
async def create_task(req: TaskCreateRequest) -> dict:
    """
    Create ad-hoc task during the day.

    Returns new task + updated task list.
    """
    config = get_config()

    if req.priority not in ("high", "normal", "low"):
        raise HTTPException(status_code=422, detail="Priority must be high, normal, or low")

    day_tasks = _load(_state(config, "tasks_today.json"), DayTasks)
    if day_tasks is None:
        raise HTTPException(status_code=409, detail="Day not yet approved — no active task list")

    task = day_tasks.add(req.text, TaskSource.AD_HOC, req.priority)
    _write_json(_state(config, "tasks_today.json"), day_tasks.model_dump())

    return {"task": task.model_dump(), "tasks": day_tasks.model_dump()}


@router.post("/tasks/{task_id}")
async def update_task(task_id: str, req: TaskUpdateRequest) -> dict:
    """
    Update task status: complete, drop, or defer.

    Returns updated task list.
    Raises 422 if drop without reason, 404 if task not found.
    """
    if req.action not in ("complete", "drop", "defer"):
        raise HTTPException(status_code=422, detail="Action must be complete, drop, or defer")

    if req.action == "drop" and not req.reason:
        raise HTTPException(status_code=422, detail="Drop reason required")

    if req.action == "defer" and not req.defer_to:
        raise HTTPException(status_code=422, detail="defer_to required for defer action")

    config = get_config()
    day_tasks = _load(_state(config, "tasks_today.json"), DayTasks)
    if day_tasks is None:
        raise HTTPException(status_code=404, detail="No active task list found")

    try:
        if req.action == "complete":
            day_tasks.complete(task_id, notes=req.notes)
        elif req.action == "drop":
            assert req.reason  # validated above (not req.reason raises 422)
            day_tasks.drop(task_id, req.reason)
        elif req.action == "defer":
            assert req.defer_to  # validated above
            day_tasks.defer(task_id, req.defer_to)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)

    _write_json(_state(config, "tasks_today.json"), day_tasks.model_dump())
    return {"tasks": day_tasks.model_dump()}


@router.get("/status")
async def get_status() -> dict:
    """
    System health check.

    Returns freshness of state files, day status, and errors.
    """
    config = get_config()

    cal_path = _state(config, "calendar_state.json")
    news_path = _state(config, "news_state.json")

    cal_fresh = _is_fresh(cal_path, config.max_state_age_hours)
    news_fresh = _is_fresh(news_path, config.max_state_age_hours)

    day_state = _load(_state(config, "day_state.json"), DayState)
    day_status = day_state.status.value if day_state else "unknown"

    last_fetch = None
    if news_path.exists():
        mtime = datetime.fromtimestamp(news_path.stat().st_mtime)
        last_fetch = mtime.isoformat() + "Z"

    return {
        "calendar_fresh": cal_fresh,
        "news_fresh": news_fresh,
        "day_status": day_status,
        "last_fetch": last_fetch,
        "errors": [],
    }
