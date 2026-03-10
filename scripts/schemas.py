"""
Pydantic models for Cadence data structures.

All models track schema_version to enable future migrations.
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# Calendar Models
# ============================================================================

class CalendarEvent(BaseModel):
    """A single calendar event."""
    title: str
    start: str  # ISO 8601 datetime
    end: str  # ISO 8601 datetime
    location: Optional[str] = None
    calendar: Optional[str] = None  # Calendar name
    all_day: bool = False


class CalendarTomorrowEvent(BaseModel):
    """Tomorrow preview event (minimal info)."""
    title: str
    start: str  # ISO 8601 datetime
    all_day: bool = False


class CalendarState(BaseModel):
    """State of today's calendar fetch."""
    schema_version: int = Field(default=1)
    fetched_at: str  # ISO 8601 datetime
    date: str  # YYYY-MM-DD
    events: list[CalendarEvent]
    tomorrow_preview: list[CalendarTomorrowEvent] = Field(default_factory=list)


# ============================================================================
# News Models
# ============================================================================

class NewsItem(BaseModel):
    """A single news item from RSS feeds."""
    title: str
    source: str  # Feed name
    url: str
    summary: str
    topic: str  # AI, Anthropic, etc.
    published: str  # ISO 8601 datetime
    relevance: float = Field(ge=0.0, le=1.0)  # 0-1 score


class NewsState(BaseModel):
    """State of news fetches."""
    schema_version: int = Field(default=1)
    fetched_at: str  # ISO 8601 datetime
    items: list[NewsItem]
    errors: list[str] = Field(default_factory=list)


# ============================================================================
# Task Models
# ============================================================================

class TaskStatus(str, Enum):
    """Task lifecycle status."""
    PENDING = "pending"
    COMPLETED = "completed"
    DROPPED = "dropped"
    DEFERRED = "deferred"


class TaskSource(str, Enum):
    """Where a task originated."""
    TODAY = "today"  # In today.md
    CARRIED_OVER = "carried_over"  # From backlog
    SUGGESTED = "suggested"  # Agent suggestion
    NEGOTIATION = "negotiation"  # User requested during negotiation
    AD_HOC = "ad_hoc"  # User added during day


class Task(BaseModel):
    """A single task."""
    id: str  # Format: t{count}_{timestamp}
    text: str
    source: TaskSource
    priority: str = "normal"  # "high", "normal", "low"
    status: TaskStatus = TaskStatus.PENDING
    created_at: str  # ISO 8601 datetime
    completed_at: Optional[str] = None  # Set when completed
    notes: Optional[str] = None  # User notes
    drop_reason: Optional[str] = None  # Why dropped
    deferred_to: Optional[str] = None  # "tomorrow", "backlog", or ISO date


class DayTasks(BaseModel):
    """All tasks for a day."""
    schema_version: int = Field(default=1)
    date: str  # YYYY-MM-DD
    tasks: list[Task]

    def complete(self, task_id: str, notes: Optional[str] = None) -> None:
        """Mark task as completed."""
        task = self._find(task_id)
        if task.status == TaskStatus.DROPPED:
            raise ValueError(f"Cannot complete dropped task {task_id}")
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now().isoformat() + "Z"
        if notes:
            task.notes = notes

    def drop(self, task_id: str, reason: str) -> None:
        """Mark task as dropped with reason."""
        if not reason:
            raise ValueError(f"Drop reason required for {task_id}")
        task = self._find(task_id)
        task.status = TaskStatus.DROPPED
        task.drop_reason = reason

    def defer(self, task_id: str, defer_to: str) -> None:
        """Defer task to tomorrow, backlog, or date."""
        task = self._find(task_id)
        task.status = TaskStatus.DEFERRED
        task.deferred_to = defer_to

    def add(self, text: str, source: TaskSource, priority: str = "normal") -> Task:
        """Add a new task."""
        import time
        task_id = f"t{len(self.tasks) + 1}_{int(time.time())}"
        task = Task(
            id=task_id,
            text=text,
            source=source,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat() + "Z"
        )
        self.tasks.append(task)
        return task

    def _find(self, task_id: str) -> Task:
        """Find task by id, raise if not found."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise ValueError(f"Task {task_id} not found")


# ============================================================================
# Day Lifecycle Models
# ============================================================================

class DayStatus(str, Enum):
    """Daily lifecycle state."""
    DRAFT_PENDING = "draft_pending"  # Pipeline finished, draft ready
    NEGOTIATING = "negotiating"  # User opened app and started negotiating
    ACTIVE = "active"  # Plan approved, tracking tasks
    COMPLETED = "completed"  # End of day


class DayState(BaseModel):
    """Current day's state machine."""
    schema_version: int = Field(default=1)
    date: str  # YYYY-MM-DD
    status: DayStatus
    draft_generated_at: Optional[str] = None  # ISO 8601
    negotiation_started_at: Optional[str] = None  # ISO 8601
    approved_at: Optional[str] = None  # ISO 8601
    completed_at: Optional[str] = None  # ISO 8601


# ============================================================================
# Decision Models
# ============================================================================

class DecisionAction(str, Enum):
    """Type of decision made."""
    DECLINED = "declined"
    ADDED = "added"
    MOVED = "moved"
    REPRIORITIZED = "reprioritized"
    MODIFIED = "modified"
    ACCEPTED_SUGGESTION = "accepted_suggestion"


class Decision(BaseModel):
    """A single decision made during negotiation or task tracking."""
    timestamp: str  # ISO 8601
    action: DecisionAction
    target: str  # What was changed (task text, event title, etc.)
    reason: Optional[str] = None
    energy_note: Optional[str] = None  # Context about energy
    context_tag: Optional[str] = None  # "morning_negotiation", "during_day"
    agent_suggestion: Optional[str] = None


class DayDecisions(BaseModel):
    """All decisions made in a day."""
    schema_version: int = Field(default=1)
    date: str  # YYYY-MM-DD
    negotiation_decisions: list[Decision] = Field(default_factory=list)
    task_outcomes: list[dict] = Field(default_factory=list)


# ============================================================================
# Draft Schema (for JSON structure validation)
# ============================================================================

class DraftNewsItem(BaseModel):
    """News item in draft."""
    id: str
    topic: str
    headline: str
    summary: str
    url: str
    relevance: float = Field(ge=0.0, le=1.0)


class DraftScheduleItem(BaseModel):
    """Schedule item in draft."""
    id: str
    time_start: str  # HH:MM
    time_end: str  # HH:MM
    title: str
    location: Optional[str] = None
    all_day: bool = False


class DraftTaskItem(BaseModel):
    """Task in draft."""
    id: str
    text: str
    source: TaskSource
    priority: str = "normal"
    status: TaskStatus = TaskStatus.PENDING
    completed_at: Optional[str] = None
    notes: Optional[str] = None


class DraftTraining(BaseModel):
    """Training info in draft."""
    summary: str
    plan_reference: Optional[str] = None


class Draft(BaseModel):
    """Complete daily draft JSON schema."""
    schema_version: int = Field(default=1)
    date: str  # YYYY-MM-DD
    generated_at: str  # ISO 8601
    news: list[DraftNewsItem]
    schedule: list[DraftScheduleItem]
    tomorrow_preview: list[CalendarTomorrowEvent] = Field(default_factory=list)
    tasks: list[DraftTaskItem]
    training: DraftTraining
    agent_suggestions: list[str] = Field(default_factory=list)


# ============================================================================
# Helper Functions
# ============================================================================

def load_state(path: str, model: type[BaseModel]) -> Optional[BaseModel]:
    """
    Load JSON state file and validate against schema.

    Returns None if file missing or validation fails (graceful degradation).
    """
    import json
    from pathlib import Path

    try:
        file_path = Path(path)
        if not file_path.exists():
            return None

        with open(file_path) as f:
            data = json.load(f)

        # Validate schema version matches
        expected_version = {
            "calendar": 1,
            "news": 1,
            "day": 1,
            "draft": 1,
            "decisions": 1,
            "tasks": 1,
        }

        # Parse with Pydantic
        return model.model_validate(data)

    except Exception as e:
        # Log error, return None
        import logging
        logging.error(f"Failed to load state from {path}: {e}")
        return None
