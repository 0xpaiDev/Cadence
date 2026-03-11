"""
Tests for task lifecycle state transitions.

Tests DayTasks mutation methods: complete, drop, defer, add.
"""

import pytest

from scripts.schemas import DayTasks, TaskSource, TaskStatus


@pytest.fixture
def day_tasks(sample_day_tasks):
    """DayTasks with one pending and one completed task."""
    return DayTasks.model_validate(sample_day_tasks)


PENDING_ID = "t1_1234567890"


def test_complete_task_sets_status(day_tasks):
    """complete() sets task status to COMPLETED and completed_at."""
    day_tasks.complete(PENDING_ID)
    task = day_tasks._find(PENDING_ID)
    assert task.status == TaskStatus.COMPLETED
    assert task.completed_at is not None


def test_complete_task_timestamp_format(day_tasks):
    """complete() sets completed_at as ISO datetime ending with Z."""
    day_tasks.complete(PENDING_ID)
    task = day_tasks._find(PENDING_ID)
    assert task.completed_at.endswith("Z")


def test_drop_task_without_reason_raises(day_tasks):
    """drop() with empty reason raises ValueError."""
    with pytest.raises(ValueError, match="Drop reason required"):
        day_tasks.drop(PENDING_ID, "")


def test_drop_task_records_reason(day_tasks):
    """drop() records the provided reason."""
    day_tasks.drop(PENDING_ID, "Not needed today")
    task = day_tasks._find(PENDING_ID)
    assert task.status == TaskStatus.DROPPED
    assert task.drop_reason == "Not needed today"


def test_defer_task_to_tomorrow(day_tasks):
    """defer() sets status to DEFERRED and deferred_to."""
    day_tasks.defer(PENDING_ID, "tomorrow")
    task = day_tasks._find(PENDING_ID)
    assert task.status == TaskStatus.DEFERRED
    assert task.deferred_to == "tomorrow"


def test_complete_dropped_task_raises(day_tasks):
    """complete() on a DROPPED task raises ValueError."""
    day_tasks.drop(PENDING_ID, "Not needed")
    with pytest.raises(ValueError, match="Cannot complete dropped task"):
        day_tasks.complete(PENDING_ID)


def test_add_adhoc_task(day_tasks):
    """add() creates a new AD_HOC PENDING task and appends it."""
    initial_count = len(day_tasks.tasks)
    task = day_tasks.add("Buy milk", TaskSource.AD_HOC, "low")
    assert task.source == TaskSource.AD_HOC
    assert task.status == TaskStatus.PENDING
    assert len(day_tasks.tasks) == initial_count + 1
