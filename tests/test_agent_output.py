"""Tests for agent draft generation."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.agent_daily_planner import generate_draft
from scripts.runtime import MockRuntime
from scripts.schemas import Draft


class TestGenerateDraft:
    """Tests for generate_draft() function."""

    def test_generate_draft_returns_valid_draft(self, config, vault_path, sample_draft):
        """Test that generate_draft returns dict with correct structure."""
        # Setup: create template file and MockRuntime
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        # Mock runtime returns sample_draft JSON
        runtime = MockRuntime(response=json.dumps(sample_draft))

        # Update config to use our test vault
        config.vault_path = vault_path

        # Execute
        result = generate_draft("test context", config, runtime)

        # Assert: result is dict with expected keys
        assert isinstance(result, dict)
        assert "schema_version" in result
        assert "date" in result
        assert "generated_at" in result
        assert "news" in result
        assert "schedule" in result
        assert "tomorrow_preview" in result
        assert "tasks" in result
        assert "training" in result
        assert "agent_suggestions" in result

    def test_generate_draft_validates_schema(self, config, vault_path, sample_draft):
        """Test that returned draft passes Pydantic validation."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        runtime = MockRuntime(response=json.dumps(sample_draft))
        config.vault_path = vault_path

        result = generate_draft("test context", config, runtime)

        # Assert: Pydantic can validate the result
        draft = Draft.model_validate(result)
        assert draft.date == sample_draft["date"]
        assert draft.schema_version == sample_draft["schema_version"]

    def test_generate_draft_invalid_json(self, config, vault_path):
        """Test that invalid JSON raises ValueError."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        # Mock runtime returns garbage
        runtime = MockRuntime(response="not valid json {{{")
        config.vault_path = vault_path

        with pytest.raises(ValueError, match="not valid JSON"):
            generate_draft("test context", config, runtime)

    def test_generate_draft_missing_template(self, config, vault_path):
        """Test that missing template file raises FileNotFoundError."""
        # Don't create template file
        config.vault_path = vault_path
        runtime = MockRuntime(response='{"status": "ok"}')

        with pytest.raises(FileNotFoundError, match="Prompt template not found"):
            generate_draft("test context", config, runtime)

    def test_generate_draft_invalid_draft_schema(self, config, vault_path):
        """Test that invalid draft schema raises ValidationError."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        # Valid JSON but missing required fields
        bad_draft = {"schema_version": 1}
        runtime = MockRuntime(response=json.dumps(bad_draft))
        config.vault_path = vault_path

        with pytest.raises(ValueError, match="doesn't match Draft schema"):
            generate_draft("test context", config, runtime)

    def test_generate_draft_uses_context(self, config, vault_path, sample_draft):
        """Test that runtime is called with context as user_message."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_text = "You are a test assistant."
        template_path.write_text(template_text)

        runtime = MockRuntime(response=json.dumps(sample_draft))
        config.vault_path = vault_path

        context = "Daily context with calendar and news"
        result = generate_draft(context, config, runtime)

        # Assert: result is valid
        assert result["date"] == sample_draft["date"]

    def test_draft_news_items_have_required_fields(self, config, vault_path, sample_draft):
        """Test that each news item in draft has required fields."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        runtime = MockRuntime(response=json.dumps(sample_draft))
        config.vault_path = vault_path

        result = generate_draft("test context", config, runtime)

        for news in result.get("news", []):
            assert "headline" in news
            assert "url" in news
            assert "id" in news
            assert "topic" in news

    def test_draft_tasks_have_required_fields(self, config, vault_path, sample_draft):
        """Test that each task in draft has required fields."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        runtime = MockRuntime(response=json.dumps(sample_draft))
        config.vault_path = vault_path

        result = generate_draft("test context", config, runtime)

        for task in result.get("tasks", []):
            assert "id" in task
            assert "text" in task
            assert "status" in task

    def test_generate_draft_runtime_error_handling(self, config, vault_path):
        """Test that runtime errors are caught and re-raised."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        # Mock runtime that raises error
        runtime = Mock()
        runtime.call.side_effect = RuntimeError("API failure")
        config.vault_path = vault_path

        with pytest.raises(RuntimeError, match="Failed to call agent"):
            generate_draft("test context", config, runtime)

    def test_generate_draft_with_empty_news_list(self, config, vault_path):
        """Test that draft with no news items is valid."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        draft = {
            "schema_version": 1,
            "date": "2025-06-15",
            "generated_at": "2025-06-15T06:00:00Z",
            "news": [],
            "schedule": [],
            "tomorrow_preview": [],
            "tasks": [],
            "training": {"summary": "Rest day"},
            "agent_suggestions": [],
        }

        runtime = MockRuntime(response=json.dumps(draft))
        config.vault_path = vault_path

        result = generate_draft("test context", config, runtime)
        assert result["news"] == []
        assert result["tasks"] == []

    def test_generate_draft_preserves_all_fields(self, config, vault_path, sample_draft):
        """Test that all draft fields are preserved in output."""
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        runtime = MockRuntime(response=json.dumps(sample_draft))
        config.vault_path = vault_path

        result = generate_draft("test context", config, runtime)

        # Check all top-level keys match
        assert set(result.keys()) == set(sample_draft.keys())
