"""Tests for context builder."""

import json
from pathlib import Path

from scripts.build_context import build_context_from_vault

FIXTURES = Path(__file__).parent / "fixtures"


class TestContextBuilderBasics:
    """Test basic context builder functionality."""

    def test_all_sections_render_with_valid_state(self, vault_path, config):
        """All five sections render when state files are present."""
        # Copy fixture files into temp vault
        state_dir = Path(vault_path) / ".system" / "state"
        (FIXTURES / "calendar_state.json").write_text(
            (FIXTURES / "calendar_state.json").read_text()
        )
        state_dir.mkdir(parents=True, exist_ok=True)
        state_dir.joinpath("calendar_state.json").write_text(
            (FIXTURES / "calendar_state.json").read_text()
        )
        state_dir.joinpath("news_state.json").write_text(
            (FIXTURES / "news_state.json").read_text()
        )

        # Write task and training files
        tasks_file = Path(vault_path) / "data" / "tasks" / "today.md"
        tasks_file.parent.mkdir(parents=True, exist_ok=True)
        tasks_file.write_text((FIXTURES / "tasks_today.md").read_text())

        training_file = Path(vault_path) / "data" / "training" / "plan.md"
        training_file.parent.mkdir(parents=True, exist_ok=True)
        training_file.write_text((FIXTURES / "training_plan.md").read_text())

        # Override config vault path
        config.vault_path = vault_path

        result = build_context_from_vault(vault_path, config)

        assert "# Daily Context" in result
        assert "## News Briefing" in result
        assert "## Schedule" in result
        assert "## Tomorrow Preview" in result
        assert "## Tasks" in result
        assert "## Training" in result

    def test_news_section_has_markdown_link_format(self, vault_path, config):
        """News items are formatted as [title](url)."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_dir.joinpath("news_state.json").write_text(
            (FIXTURES / "news_state.json").read_text()
        )

        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        assert (
            "[Claude 4 Released with Extended Context]"
            "(https://anthropic.com/news/claude-4)"
        ) in result

    def test_news_sorted_by_relevance_descending(self, vault_path, config):
        """News items are sorted by relevance descending."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create news state with items at different relevances
        news_data = {
            "schema_version": 1,
            "fetched_at": "2025-06-15T06:00:00Z",
            "items": [
                {
                    "title": "Low Relevance Item",
                    "source": "Test",
                    "url": "https://example.com/low",
                    "summary": "This has lower relevance.",
                    "topic": "Test",
                    "published": "2025-06-15T00:00:00Z",
                    "relevance": 0.4,
                },
                {
                    "title": "High Relevance Item",
                    "source": "Test",
                    "url": "https://example.com/high",
                    "summary": "This has higher relevance.",
                    "topic": "Test",
                    "published": "2025-06-15T00:00:00Z",
                    "relevance": 0.95,
                },
            ],
            "errors": [],
        }
        state_dir.joinpath("news_state.json").write_text(
            json.dumps(news_data)
        )

        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        # High relevance item should appear before low relevance
        high_pos = result.find("High Relevance Item")
        low_pos = result.find("Low Relevance Item")
        assert high_pos < low_pos, "High relevance item should come first"

    def test_missing_calendar_state_skips_schedule_section(self, vault_path, config):
        """Schedule section is omitted when calendar_state.json is missing."""
        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        assert "## Schedule" not in result
        assert "## Tomorrow Preview" not in result

    def test_missing_news_state_skips_news_section(self, vault_path, config):
        """News section is omitted when news_state.json is missing."""
        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        assert "## News Briefing" not in result

    def test_missing_tasks_file_skips_tasks_section(self, vault_path, config):
        """Tasks section is omitted when tasks file is missing."""
        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        assert "## Tasks" not in result

    def test_missing_training_file_skips_training_section(self, vault_path, config):
        """Training section is omitted when training file is missing."""
        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        assert "## Training" not in result

    def test_malformed_calendar_state_skips_schedule_section(
        self, vault_path, config
    ):
        """Schedule section is skipped when calendar state is malformed."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        # calendar_state_malformed.json is missing required "date" field
        state_dir.joinpath("calendar_state.json").write_text(
            (FIXTURES / "calendar_state_malformed.json").read_text()
        )

        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        # Should not crash, and schedule section should be absent
        assert "## Schedule" not in result
        assert "# Daily Context" in result  # Document header still present

    def test_all_day_event_shows_all_day_label(self, vault_path, config):
        """All-day events are labeled 'All day:' instead of time."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create calendar state with an all-day event
        cal_data = {
            "schema_version": 1,
            "fetched_at": "2025-06-15T06:00:00Z",
            "date": "2025-06-15",
            "events": [
                {
                    "title": "Sprint planning day",
                    "start": "2025-06-15T00:00:00Z",
                    "end": "2025-06-15T23:59:59Z",
                    "location": None,
                    "calendar": "Work",
                    "all_day": True,
                }
            ],
            "tomorrow_preview": [],
        }
        state_dir.joinpath("calendar_state.json").write_text(
            json.dumps(cal_data)
        )

        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        assert "- All day: Sprint planning day" in result
        # Should NOT contain time format for this event
        assert "00:00–23:59" not in result

    def test_token_budget_trims_news(self, vault_path, config):
        """News items are trimmed when token budget is tight."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create news state with multiple items
        news_data = {
            "schema_version": 1,
            "fetched_at": "2025-06-15T06:00:00Z",
            "items": [
                {
                    "title": f"News Item {i}",
                    "source": "Test",
                    "url": f"https://example.com/{i}",
                    "summary": "Item description.",
                    "topic": "Test",
                    "published": "2025-06-15T00:00:00Z",
                    "relevance": 0.9 - (i * 0.1),  # Descending relevance
                }
                for i in range(5)
            ],
            "errors": [],
        }
        state_dir.joinpath("news_state.json").write_text(
            json.dumps(news_data)
        )

        # Use a very tight token budget
        config.vault_path = vault_path
        config.token_budget = 50

        result = build_context_from_vault(vault_path, config)

        # Count news items in output (look for markdown link patterns)
        link_count = result.count("- [News Item")
        # Should have fewer items than the 5 we provided
        assert link_count < 5

    def test_news_capped_at_news_max_items(self, vault_path, config):
        """News items are capped at news_max_items."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create news state with 15 items
        news_data = {
            "schema_version": 1,
            "fetched_at": "2025-06-15T06:00:00Z",
            "items": [
                {
                    "title": f"News Item {i}",
                    "source": "Test",
                    "url": f"https://example.com/{i}",
                    "summary": "Item description.",
                    "topic": "Test",
                    "published": "2025-06-15T00:00:00Z",
                    "relevance": 0.95 - (i * 0.05),  # Descending relevance
                }
                for i in range(15)
            ],
            "errors": [],
        }
        state_dir.joinpath("news_state.json").write_text(
            json.dumps(news_data)
        )

        config.vault_path = vault_path
        config.news_max_items = 10

        result = build_context_from_vault(vault_path, config)

        # Count news items in output
        link_count = result.count("- [News Item")
        # Should not exceed news_max_items
        assert link_count <= 10

    def test_tomorrow_preview_section_renders(self, vault_path, config):
        """Tomorrow preview section renders when events are present."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create calendar state with tomorrow preview
        cal_data = {
            "schema_version": 1,
            "fetched_at": "2025-06-15T06:00:00Z",
            "date": "2025-06-15",
            "events": [],
            "tomorrow_preview": [
                {
                    "title": "Conference",
                    "start": "2025-06-16T10:00:00Z",
                    "all_day": False,
                }
            ],
        }
        state_dir.joinpath("calendar_state.json").write_text(
            json.dumps(cal_data)
        )

        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        assert "## Tomorrow Preview" in result
        assert "Conference" in result
        assert "10:00" in result

    def test_schedule_sorted_chronologically(self, vault_path, config):
        """Schedule events are sorted by start time."""
        state_dir = Path(vault_path) / ".system" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        # Create calendar state with events in reverse time order
        cal_data = {
            "schema_version": 1,
            "fetched_at": "2025-06-15T06:00:00Z",
            "date": "2025-06-15",
            "events": [
                {
                    "title": "Late meeting",
                    "start": "2025-06-15T15:00:00Z",
                    "end": "2025-06-15T16:00:00Z",
                    "location": None,
                    "calendar": "Work",
                    "all_day": False,
                },
                {
                    "title": "Early meeting",
                    "start": "2025-06-15T09:00:00Z",
                    "end": "2025-06-15T10:00:00Z",
                    "location": None,
                    "calendar": "Work",
                    "all_day": False,
                },
            ],
            "tomorrow_preview": [],
        }
        state_dir.joinpath("calendar_state.json").write_text(
            json.dumps(cal_data)
        )

        config.vault_path = vault_path
        result = build_context_from_vault(vault_path, config)

        # Early meeting should appear before late meeting
        early_pos = result.find("Early meeting")
        late_pos = result.find("Late meeting")
        assert early_pos < late_pos, "Events should be sorted chronologically"
