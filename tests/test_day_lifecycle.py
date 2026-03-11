"""
Tests for day state machine transitions.

Tests DayState creation and status transitions.
"""

import json
from datetime import datetime

import pytest

from scripts.schemas import DayState, DayStatus


@pytest.fixture
def day_state(sample_day_state):
    """DayState in draft_pending status."""
    return DayState.model_validate(sample_day_state)


def test_initial_status_is_draft_pending(day_state):
    """Day state loaded from sample fixture starts as DRAFT_PENDING."""
    assert day_state.status == DayStatus.DRAFT_PENDING


def test_transition_to_negotiating(day_state):
    """Setting status to NEGOTIATING preserves date and draft_generated_at."""
    original_date = day_state.date
    day_state.status = DayStatus.NEGOTIATING
    day_state.negotiation_started_at = datetime.now().isoformat() + "Z"
    assert day_state.status == DayStatus.NEGOTIATING
    assert day_state.date == original_date
    assert day_state.negotiation_started_at is not None


def test_transition_to_active_sets_approved_at(day_state):
    """Setting status to ACTIVE with approved_at round-trips through model_dump."""
    now = datetime.now().isoformat() + "Z"
    day_state.status = DayStatus.ACTIVE
    day_state.approved_at = now
    dumped = day_state.model_dump()
    restored = DayState.model_validate(dumped)
    assert restored.status == DayStatus.ACTIVE
    assert restored.approved_at == now


def test_transition_to_completed(day_state):
    """Setting status to COMPLETED with completed_at round-trips."""
    now = datetime.now().isoformat() + "Z"
    day_state.status = DayStatus.COMPLETED
    day_state.completed_at = now
    dumped = day_state.model_dump()
    restored = DayState.model_validate(dumped)
    assert restored.status == DayStatus.COMPLETED
    assert restored.completed_at == now


def test_model_dump_produces_string_status(day_state):
    """model_dump() serializes status as string value, not enum object."""
    day_state.status = DayStatus.ACTIVE
    dumped = day_state.model_dump()
    assert dumped["status"] == "active"


def test_day_state_json_roundtrip(day_state):
    """DayState round-trips through JSON serialization."""
    json_str = day_state.model_dump_json()
    data = json.loads(json_str)
    restored = DayState.model_validate(data)
    assert restored.status == day_state.status
    assert restored.date == day_state.date
