"""Tests for Pydantic data schemas."""

import json

import pytest
from pydantic import ValidationError

from scripts.schemas import (
    CalendarEvent,
    CalendarState,
    DayDecisions,
    DayState,
    DayStatus,
    DayTasks,
    Decision,
    DecisionAction,
    Draft,
    NewsItem,
    NewsState,
    Task,
    TaskSource,
    TaskStatus,
    load_state,
)

# ============================================================================
# CalendarEvent & CalendarState Tests
# ============================================================================

class TestCalendarEvent:
    """Test CalendarEvent model."""

    def test_valid_event_parses(self):
        """Valid event with all required fields parses."""
        event = CalendarEvent(
            title="Team Standup",
            start="2026-03-11T09:00:00Z",
            end="2026-03-11T09:30:00Z",
        )
        assert event.title == "Team Standup"
        assert event.location is None

    def test_all_day_defaults_to_false(self):
        """all_day field defaults to False."""
        event = CalendarEvent(
            title="Team Standup",
            start="2026-03-11T09:00:00Z",
            end="2026-03-11T09:30:00Z",
        )
        assert event.all_day is False

    def test_event_with_optional_fields(self):
        """Event with optional fields (location, calendar) parses."""
        event = CalendarEvent(
            title="Team Standup",
            start="2026-03-11T09:00:00Z",
            end="2026-03-11T09:30:00Z",
            location="Conference Room A",
            calendar="Work",
        )
        assert event.location == "Conference Room A"
        assert event.calendar == "Work"

    def test_missing_title_raises_validation_error(self):
        """Missing required field (title) raises ValidationError."""
        with pytest.raises(ValidationError):
            CalendarEvent(
                start="2026-03-11T09:00:00Z",
                end="2026-03-11T09:30:00Z",
            )

    def test_missing_start_raises_validation_error(self):
        """Missing required field (start) raises ValidationError."""
        with pytest.raises(ValidationError):
            CalendarEvent(
                title="Team Standup",
                end="2026-03-11T09:30:00Z",
            )


class TestCalendarState:
    """Test CalendarState model."""

    def test_valid_calendar_state_parses(self, sample_calendar_state):
        """Valid CalendarState with events parses."""
        state = CalendarState(**sample_calendar_state)
        assert state.date == "2025-06-15"
        assert len(state.events) == 1
        assert state.events[0].title == "Team standup"

    def test_schema_version_defaults_to_1(self):
        """schema_version defaults to 1."""
        state = CalendarState(
            fetched_at="2026-03-11T06:00:00Z",
            date="2026-03-11",
            events=[],
        )
        assert state.schema_version == 1

    def test_empty_events_list(self):
        """CalendarState with empty events list is valid."""
        state = CalendarState(
            fetched_at="2026-03-11T06:00:00Z",
            date="2026-03-11",
            events=[],
        )
        assert len(state.events) == 0

    def test_tomorrow_preview_defaults_to_empty_list(self):
        """tomorrow_preview defaults to empty list."""
        state = CalendarState(
            fetched_at="2026-03-11T06:00:00Z",
            date="2026-03-11",
            events=[],
        )
        assert state.tomorrow_preview == []

    def test_missing_date_raises_validation_error(self):
        """Missing required field (date) raises ValidationError."""
        with pytest.raises(ValidationError):
            CalendarState(
                fetched_at="2026-03-11T06:00:00Z",
                events=[],
            )


# ============================================================================
# NewsItem & NewsState Tests
# ============================================================================

class TestNewsItem:
    """Test NewsItem model."""

    def test_valid_news_item_parses(self):
        """Valid NewsItem with all required fields parses."""
        item = NewsItem(
            title="Claude 4.5 Released",
            source="Anthropic Blog",
            url="https://anthropic.com/news",
            summary="New Claude model available",
            topic="Anthropic",
            published="2026-03-10T15:00:00Z",
            relevance=0.95,
        )
        assert item.title == "Claude 4.5 Released"
        assert item.relevance == 0.95

    def test_relevance_0_0_accepts(self):
        """relevance=0.0 is valid."""
        item = NewsItem(
            title="Article",
            source="Blog",
            url="https://example.com",
            summary="Summary",
            topic="General",
            published="2026-03-10T15:00:00Z",
            relevance=0.0,
        )
        assert item.relevance == 0.0

    def test_relevance_1_0_accepts(self):
        """relevance=1.0 is valid."""
        item = NewsItem(
            title="Article",
            source="Blog",
            url="https://example.com",
            summary="Summary",
            topic="General",
            published="2026-03-10T15:00:00Z",
            relevance=1.0,
        )
        assert item.relevance == 1.0

    def test_relevance_1_5_raises_validation_error(self):
        """relevance > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            NewsItem(
                title="Article",
                source="Blog",
                url="https://example.com",
                summary="Summary",
                topic="General",
                published="2026-03-10T15:00:00Z",
                relevance=1.5,
            )

    def test_relevance_minus_0_1_raises_validation_error(self):
        """relevance < 0.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            NewsItem(
                title="Article",
                source="Blog",
                url="https://example.com",
                summary="Summary",
                topic="General",
                published="2026-03-10T15:00:00Z",
                relevance=-0.1,
            )

    def test_missing_url_raises_validation_error(self):
        """Missing required field (url) raises ValidationError."""
        with pytest.raises(ValidationError):
            NewsItem(
                title="Article",
                source="Blog",
                summary="Summary",
                topic="General",
                published="2026-03-10T15:00:00Z",
                relevance=0.5,
            )


class TestNewsState:
    """Test NewsState model."""

    def test_valid_news_state_parses(self, sample_news_state):
        """Valid NewsState with items parses."""
        state = NewsState(**sample_news_state)
        assert len(state.items) == 1
        assert state.items[0].title == "Claude 4 Released"

    def test_schema_version_defaults_to_1(self):
        """schema_version defaults to 1."""
        state = NewsState(
            fetched_at="2026-03-11T06:00:00Z",
            items=[],
        )
        assert state.schema_version == 1

    def test_errors_list_defaults_to_empty(self):
        """errors field defaults to empty list."""
        state = NewsState(
            fetched_at="2026-03-11T06:00:00Z",
            items=[],
        )
        assert state.errors == []


# ============================================================================
# Task, TaskStatus, TaskSource Tests
# ============================================================================

class TestTask:
    """Test Task model."""

    def test_task_with_required_fields_parses(self):
        """Task with all required fields parses."""
        task = Task(
            id="t1_1234567890",
            text="Review PR",
            source=TaskSource.TODAY,
            created_at="2026-03-11T06:00:00Z",
        )
        assert task.id == "t1_1234567890"
        assert task.text == "Review PR"

    def test_status_defaults_to_pending(self):
        """status field defaults to PENDING."""
        task = Task(
            id="t1_1234567890",
            text="Review PR",
            source=TaskSource.TODAY,
            created_at="2026-03-11T06:00:00Z",
        )
        assert task.status == TaskStatus.PENDING

    def test_priority_defaults_to_normal(self):
        """priority field defaults to 'normal'."""
        task = Task(
            id="t1_1234567890",
            text="Review PR",
            source=TaskSource.TODAY,
            created_at="2026-03-11T06:00:00Z",
        )
        assert task.priority == "normal"

    def test_task_with_all_optional_fields(self):
        """Task with optional fields parses."""
        task = Task(
            id="t1_1234567890",
            text="Review PR",
            source=TaskSource.TODAY,
            priority="high",
            status=TaskStatus.COMPLETED,
            created_at="2026-03-11T06:00:00Z",
            completed_at="2026-03-11T14:00:00Z",
            notes="Done quickly",
            drop_reason=None,
            deferred_to=None,
        )
        assert task.priority == "high"
        assert task.completed_at == "2026-03-11T14:00:00Z"
        assert task.notes == "Done quickly"

    def test_missing_id_raises_validation_error(self):
        """Missing required field (id) raises ValidationError."""
        with pytest.raises(ValidationError):
            Task(
                text="Review PR",
                source=TaskSource.TODAY,
                created_at="2026-03-11T06:00:00Z",
            )

    def test_missing_text_raises_validation_error(self):
        """Missing required field (text) raises ValidationError."""
        with pytest.raises(ValidationError):
            Task(
                id="t1_1234567890",
                source=TaskSource.TODAY,
                created_at="2026-03-11T06:00:00Z",
            )


# ============================================================================
# DayTasks Mutation Tests
# ============================================================================

class TestDayTasksMutations:
    """Test DayTasks mutation methods."""

    def test_complete_sets_status_and_timestamp(self, sample_day_tasks):
        """complete() sets status to COMPLETED and sets completed_at."""
        day_tasks = DayTasks(**sample_day_tasks)
        task_id = "t1_1234567890"

        day_tasks.complete(task_id)
        task = day_tasks._find(task_id)

        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None

    def test_complete_with_notes(self, sample_day_tasks):
        """complete() with notes parameter sets notes."""
        day_tasks = DayTasks(**sample_day_tasks)
        task_id = "t1_1234567890"

        day_tasks.complete(task_id, notes="Finished on time")
        task = day_tasks._find(task_id)

        assert task.notes == "Finished on time"

    def test_complete_dropped_task_raises_error(self, sample_day_tasks):
        """complete() on a dropped task raises ValueError."""
        day_tasks = DayTasks(**sample_day_tasks)
        task_id = "t1_1234567890"

        day_tasks.drop(task_id, reason="Out of scope")

        with pytest.raises(ValueError):
            day_tasks.complete(task_id)

    def test_drop_without_reason_raises_error(self, sample_day_tasks):
        """drop() without reason raises ValueError."""
        day_tasks = DayTasks(**sample_day_tasks)
        task_id = "t1_1234567890"

        with pytest.raises(ValueError):
            day_tasks.drop(task_id, reason="")

    def test_drop_sets_status_and_reason(self, sample_day_tasks):
        """drop() sets status to DROPPED and sets drop_reason."""
        day_tasks = DayTasks(**sample_day_tasks)
        task_id = "t1_1234567890"

        day_tasks.drop(task_id, reason="Out of scope")
        task = day_tasks._find(task_id)

        assert task.status == TaskStatus.DROPPED
        assert task.drop_reason == "Out of scope"

    def test_defer_sets_status_and_target(self, sample_day_tasks):
        """defer() sets status to DEFERRED and sets deferred_to."""
        day_tasks = DayTasks(**sample_day_tasks)
        task_id = "t1_1234567890"

        day_tasks.defer(task_id, defer_to="tomorrow")
        task = day_tasks._find(task_id)

        assert task.status == TaskStatus.DEFERRED
        assert task.deferred_to == "tomorrow"

    def test_add_creates_new_task(self, sample_day_tasks):
        """add() creates new task with correct source and priority."""
        day_tasks = DayTasks(**sample_day_tasks)
        initial_count = len(day_tasks.tasks)

        new_task = day_tasks.add("New task", TaskSource.AD_HOC, priority="high")

        assert len(day_tasks.tasks) == initial_count + 1
        assert new_task.text == "New task"
        assert new_task.source == TaskSource.AD_HOC
        assert new_task.priority == "high"
        assert new_task.status == TaskStatus.PENDING

    def test_find_nonexistent_task_raises_error(self, sample_day_tasks):
        """_find() with non-existent task_id raises ValueError."""
        day_tasks = DayTasks(**sample_day_tasks)

        with pytest.raises(ValueError):
            day_tasks._find("nonexistent_id")


# ============================================================================
# DayState Tests
# ============================================================================

class TestDayState:
    """Test DayState model."""

    def test_valid_day_state_parses(self, sample_day_state):
        """Valid DayState with draft_pending status parses."""
        state = DayState(**sample_day_state)
        assert state.date == "2025-06-15"
        assert state.status == DayStatus.DRAFT_PENDING

    def test_all_status_values_parse(self):
        """All DayStatus enum values parse correctly."""
        for status in DayStatus:
            state = DayState(
                date="2026-03-11",
                status=status,
            )
            assert state.status == status

    def test_invalid_status_raises_validation_error(self):
        """Invalid status value raises ValidationError."""
        with pytest.raises(ValidationError):
            DayState(
                date="2026-03-11",
                status="invalid_status",
            )

    def test_optional_timestamp_fields_default_to_none(self):
        """Optional timestamp fields default to None."""
        state = DayState(
            date="2026-03-11",
            status=DayStatus.DRAFT_PENDING,
        )
        assert state.draft_generated_at is None
        assert state.negotiation_started_at is None
        assert state.approved_at is None
        assert state.completed_at is None


# ============================================================================
# Draft Tests
# ============================================================================

class TestDraft:
    """Test Draft model."""

    def test_valid_draft_parses(self, sample_draft):
        """Valid Draft parses."""
        draft = Draft(**sample_draft)
        assert draft.date == "2025-06-15"
        assert len(draft.news) == 1
        assert len(draft.schedule) == 1
        assert len(draft.tasks) == 1

    def test_schema_version_defaults_to_1(self):
        """schema_version defaults to 1."""
        draft = Draft(
            date="2026-03-11",
            generated_at="2026-03-11T06:00:00Z",
            news=[],
            schedule=[],
            tasks=[],
            training={"summary": "Test"},
        )
        assert draft.schema_version == 1

    def test_agent_suggestions_defaults_to_empty_list(self):
        """agent_suggestions defaults to empty list."""
        draft = Draft(
            date="2026-03-11",
            generated_at="2026-03-11T06:00:00Z",
            news=[],
            schedule=[],
            tasks=[],
            training={"summary": "Test"},
        )
        assert draft.agent_suggestions == []


# ============================================================================
# DayDecisions Tests
# ============================================================================

class TestDayDecisions:
    """Test DayDecisions and Decision models."""

    def test_valid_decision_parses(self):
        """Valid Decision with required and optional fields parses."""
        decision = Decision(
            timestamp="2026-03-11T06:30:00Z",
            action=DecisionAction.DECLINED,
            target="Suggested task: write docs",
        )
        assert decision.action == DecisionAction.DECLINED

    def test_decision_with_optional_fields(self):
        """Decision with optional fields parses."""
        decision = Decision(
            timestamp="2026-03-11T06:30:00Z",
            action=DecisionAction.DECLINED,
            target="Suggested task: write docs",
            reason="Not enough context",
            energy_note="Low energy",
            context_tag="morning_negotiation",
            agent_suggestion="write docs",
        )
        assert decision.reason == "Not enough context"
        assert decision.energy_note == "Low energy"

    def test_valid_day_decisions_parses(self, sample_decisions):
        """Valid DayDecisions with negotiation_decisions and task_outcomes parses."""
        decisions = DayDecisions(**sample_decisions)
        assert decisions.date == "2025-06-15"
        assert len(decisions.negotiation_decisions) == 1
        assert len(decisions.task_outcomes) == 1

    def test_day_decisions_defaults_to_empty_lists(self):
        """DayDecisions defaults to empty lists for decisions and outcomes."""
        decisions = DayDecisions(date="2026-03-11")
        assert decisions.negotiation_decisions == []
        assert decisions.task_outcomes == []


# ============================================================================
# load_state() Helper Tests
# ============================================================================

class TestLoadState:
    """Test load_state() helper function."""

    def test_load_state_returns_none_for_missing_file(self, tmp_path):
        """load_state() returns None for missing file."""
        result = load_state(str(tmp_path / "nonexistent.json"), CalendarState)
        assert result is None

    def test_load_state_returns_none_for_invalid_json(self, tmp_path):
        """load_state() returns None for invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json}")

        result = load_state(str(bad_file), CalendarState)
        assert result is None

    def test_load_state_returns_valid_model_for_correct_json(
        self, tmp_path, sample_calendar_state
    ):
        """load_state() returns valid model for correct JSON."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(sample_calendar_state))

        result = load_state(str(state_file), CalendarState)
        assert result is not None
        assert isinstance(result, CalendarState)
        assert result.date == "2025-06-15"

    def test_load_state_returns_none_for_validation_failure(self, tmp_path):
        """load_state() returns None when Pydantic validation fails."""
        bad_state = {
            "schema_version": 1,
            "fetched_at": "2026-03-11T06:00:00Z",
            "date": "2026-03-11",
            "items": [
                {
                    "title": "Article",
                    "source": "Blog",
                    "url": "https://example.com",
                    "summary": "Summary",
                    "topic": "General",
                    "published": "2026-03-10T15:00:00Z",
                    "relevance": 1.5,  # OUT OF BOUNDS
                }
            ],
            "errors": [],
        }
        bad_file = tmp_path / "bad_state.json"
        bad_file.write_text(json.dumps(bad_state))

        result = load_state(str(bad_file), NewsState)
        assert result is None

    def test_load_state_with_old_schema_version_still_loads(self, tmp_path):
        """load_state() loads schema_version=0 (version check not enforced yet)."""
        old_state = {
            "schema_version": 0,
            "fetched_at": "2026-03-11T06:00:00Z",
            "date": "2026-03-11",
            "events": [],
            "tomorrow_preview": [],
        }
        old_file = tmp_path / "old_state.json"
        old_file.write_text(json.dumps(old_state))

        result = load_state(str(old_file), CalendarState)
        # NOTE: Currently, Pydantic accepts schema_version=0 because
        # load_state() builds expected_version dict but never enforces it.
        # This test documents the current behavior. Future phase should
        # add version validation.
        assert result is not None
        assert result.schema_version == 0
