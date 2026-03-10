"""
Pytest configuration and fixtures.

Provides config, vault paths, mock runtime, and sample data.
"""

import pytest
from pathlib import Path
import json
from scripts.config import Config
from scripts.runtime import MockRuntime


@pytest.fixture
def config():
    """Provide test configuration."""
    return Config(
        vault_path="/tmp/test_vault",
        cron_hour=6,
        max_state_age_hours=2,
        token_budget=2000,
        news_max_items=10,
        agent_runtime="mock",
        agent_model="mock",
        agent_max_tokens=1500,
        planner_prompt_path="daily_template.md",
        negotiation_prompt_path="negotiation_template.md",
        api_host="0.0.0.0",
        api_port=8420,
        allowed_origins=["http://localhost:8420"],
        log_level="INFO",
    )


@pytest.fixture
def vault_path(tmp_path):
    """Provide temporary vault directory."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".system" / "state").mkdir(parents=True)
    (vault / ".system" / "drafts").mkdir(parents=True)
    (vault / ".system" / "config").mkdir(parents=True)
    (vault / ".system" / "logs").mkdir(parents=True)
    (vault / ".system" / "context").mkdir(parents=True)
    (vault / "Daily").mkdir()
    (vault / "data" / "tasks").mkdir(parents=True)
    (vault / "data" / "training").mkdir(parents=True)
    return str(vault)


@pytest.fixture
def mock_runtime():
    """Provide mock agent runtime."""
    return MockRuntime(response='{"status": "ok"}')


@pytest.fixture
def sample_calendar_state():
    """Provide sample calendar state."""
    return {
        "schema_version": 1,
        "fetched_at": "2025-06-15T06:00:00Z",
        "date": "2025-06-15",
        "events": [
            {
                "title": "Team standup",
                "start": "2025-06-15T09:00:00Z",
                "end": "2025-06-15T09:30:00Z",
                "location": "Google Meet",
                "calendar": "Work",
                "all_day": False,
            }
        ],
        "tomorrow_preview": [
            {
                "title": "Conference",
                "start": "2025-06-16T10:00:00Z",
                "all_day": False,
            }
        ],
    }


@pytest.fixture
def sample_news_state():
    """Provide sample news state."""
    return {
        "schema_version": 1,
        "fetched_at": "2025-06-15T06:00:00Z",
        "items": [
            {
                "title": "Claude 4 Released",
                "source": "Anthropic Blog",
                "url": "https://anthropic.com/news/claude-4",
                "summary": "New model with extended context",
                "topic": "Anthropic",
                "published": "2025-06-15T00:00:00Z",
                "relevance": 0.95,
            }
        ],
        "errors": [],
    }


@pytest.fixture
def sample_draft():
    """Provide sample daily draft."""
    return {
        "schema_version": 1,
        "date": "2025-06-15",
        "generated_at": "2025-06-15T06:02:00Z",
        "news": [
            {
                "id": "n1",
                "topic": "Anthropic",
                "headline": "Claude 4 Released",
                "summary": "New model with extended context",
                "url": "https://anthropic.com/news/claude-4",
                "relevance": 0.95,
            }
        ],
        "schedule": [
            {
                "id": "s1",
                "time_start": "09:00",
                "time_end": "09:30",
                "title": "Team standup",
                "location": "Google Meet",
                "all_day": False,
            }
        ],
        "tomorrow_preview": [],
        "tasks": [
            {
                "id": "t1_1234567890",
                "text": "Review PR for auth module",
                "source": "today",
                "priority": "normal",
                "status": "pending",
                "completed_at": None,
                "notes": None,
            }
        ],
        "training": {
            "summary": "Week progress: 20/100km. Long ride needed before Sunday.",
            "plan_reference": None,
        },
        "agent_suggestions": [
            "Light task day — consider tackling the backlog integration tests."
        ],
    }


# TODO: Add more fixtures
# - sample_day_state
# - sample_day_tasks
# - sample_decisions
# - malformed JSON files
# - old schema version files
