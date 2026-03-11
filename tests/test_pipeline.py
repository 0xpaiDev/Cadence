"""Tests for full pipeline integration."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from scripts.pipeline import run_pipeline


class TestPipeline:
    """Tests for run_pipeline() function."""

    def test_run_pipeline_succeeds(self, config, vault_path, sample_draft):
        """Test that pipeline succeeds and returns True."""
        config.vault_path = vault_path

        # Create template file
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all") as mock_fetch, \
             patch("scripts.pipeline.build_context_from_vault") as mock_context, \
             patch("scripts.pipeline.generate_draft") as mock_draft:

            mock_context.return_value = "Mock context"
            mock_draft.return_value = sample_draft

            # Set API key
            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            result = run_pipeline()

            assert result is True
            mock_fetch.assert_called_once()
            mock_context.assert_called_once()
            mock_draft.assert_called_once()

    def test_run_pipeline_writes_draft_json(self, config, vault_path, sample_draft):
        """Test that draft JSON is written to vault."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", return_value="Mock context"), \
             patch("scripts.pipeline.generate_draft", return_value=sample_draft):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            run_pipeline()

            # Assert: draft file exists and has correct content
            draft_path = Path(vault_path) / ".system" / "drafts" / "today_draft.json"
            assert draft_path.exists()

            with draft_path.open() as f:
                draft_data = json.load(f)

            assert draft_data["date"] == sample_draft["date"]
            assert draft_data["schema_version"] == sample_draft["schema_version"]

    def test_run_pipeline_writes_day_state(self, config, vault_path, sample_draft):
        """Test that day_state.json is written with DRAFT_PENDING status."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", return_value="Mock context"), \
             patch("scripts.pipeline.generate_draft", return_value=sample_draft):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            run_pipeline()

            # Assert: day_state file exists and has correct status
            state_path = Path(vault_path) / ".system" / "state" / "day_state.json"
            assert state_path.exists()

            with state_path.open() as f:
                state_data = json.load(f)

            assert state_data["status"] == "draft_pending"
            assert "draft_generated_at" in state_data

    def test_run_pipeline_fetch_failure_continues(self, config, vault_path, sample_draft):
        """Test that fetch failure doesn't block pipeline completion."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all", side_effect=Exception("Fetch failed")), \
             patch("scripts.pipeline.build_context_from_vault", return_value="Mock context"), \
             patch("scripts.pipeline.generate_draft", return_value=sample_draft):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            # Should still return True despite fetch failure
            result = run_pipeline()

            assert result is True

            # Draft should still be written
            draft_path = Path(vault_path) / ".system" / "drafts" / "today_draft.json"
            assert draft_path.exists()

    def test_run_pipeline_draft_failure_returns_false(self, config, vault_path):
        """Test that draft generation failure returns False."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", return_value="Mock context"), \
             patch("scripts.pipeline.generate_draft", side_effect=ValueError("Invalid draft")):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            result = run_pipeline()

            assert result is False

    def test_run_pipeline_writes_context_file(self, config, vault_path, sample_draft):
        """Test that daily_context.md is written to vault."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        context_content = "# Daily Context\n\nTest content"

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", return_value=context_content), \
             patch("scripts.pipeline.generate_draft", return_value=sample_draft):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            run_pipeline()

            # Assert: context file exists and has correct content
            context_path = Path(vault_path) / ".system" / "context" / "daily_context.md"
            assert context_path.exists()

            content = context_path.read_text()
            assert content == context_content

    def test_run_pipeline_no_api_key_returns_false(self, config, vault_path):
        """Test that missing ANTHROPIC_API_KEY returns False."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        # Remove API key if it exists
        os.environ.pop("ANTHROPIC_API_KEY", None)

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", return_value="Mock context"):

            result = run_pipeline()

            assert result is False

    def test_run_pipeline_context_failure_returns_false(self, config, vault_path):
        """Test that context building failure returns False."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", side_effect=Exception("Build failed")):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            result = run_pipeline()

            assert result is False

    def test_run_pipeline_creates_directories(self, config, vault_path):
        """Test that pipeline creates necessary vault directories."""
        config.vault_path = vault_path

        # Start with minimal vault
        vault = Path(vault_path)
        (vault / ".system" / "state").rmdir()
        (vault / ".system" / "context").rmdir()
        (vault / ".system" / "drafts").rmdir()

        template_path = vault / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        sample_draft = {
            "schema_version": 1,
            "date": "2025-06-15",
            "generated_at": "2025-06-15T06:00:00Z",
            "news": [],
            "schedule": [],
            "tomorrow_preview": [],
            "tasks": [],
            "training": {"summary": "Test"},
            "agent_suggestions": [],
        }

        with patch("scripts.pipeline.load_config", return_value=config), \
             patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", return_value="Mock context"), \
             patch("scripts.pipeline.generate_draft", return_value=sample_draft):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            run_pipeline()

            # Assert: directories were created
            assert (vault / ".system" / "state").exists()
            assert (vault / ".system" / "context").exists()
            assert (vault / ".system" / "drafts").exists()

    def test_run_pipeline_with_provided_config(self, config, vault_path, sample_draft):
        """Test that pipeline accepts config parameter."""
        config.vault_path = vault_path
        template_path = Path(vault_path) / ".system" / "config" / config.planner_prompt_path
        template_path.write_text("You are a test assistant.")

        with patch("scripts.pipeline.fetch_all"), \
             patch("scripts.pipeline.build_context_from_vault", return_value="Mock context"), \
             patch("scripts.pipeline.generate_draft", return_value=sample_draft):

            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            # Call with explicit config (should not call load_config)
            result = run_pipeline(config=config)

            assert result is True

            draft_path = Path(vault_path) / ".system" / "drafts" / "today_draft.json"
            assert draft_path.exists()
