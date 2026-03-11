"""Tests for news and calendar fetchers."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

from scripts.fetch.calendar_fetcher import CalendarFetcher
from scripts.schemas import CalendarState, CalendarEvent, CalendarTomorrowEvent


@pytest.fixture
def mock_service():
    """Return a mock Google Calendar service."""
    return MagicMock()


@pytest.fixture
def fake_token(vault_path):
    """Write a fake token.json so CalendarFetcher skips OAuth."""
    token_data = {
        "token": "fake_access_token",
        "refresh_token": "fake_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake_client_id",
        "client_secret": "fake_secret",
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
    }
    token_path = Path(vault_path) / ".system" / "config" / "token.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(token_data))
    return str(token_path)


class TestCalendarFetcherBasics:
    """Test CalendarFetcher basic functionality."""

    @patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file")
    @patch("scripts.fetch.calendar_fetcher.build")
    def test_fetch_returns_valid_calendar_state(self, mock_build, mock_creds, config, vault_path, fake_token):
        """Test fetching valid calendar events returns CalendarState."""
        # Setup mock service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock credentials
        mock_credentials = MagicMock()
        mock_credentials.expired = False
        mock_creds.return_value = mock_credentials

        # Setup mock event data (timed events)
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "summary": "Team standup",
                    "start": {"dateTime": "2025-06-15T09:00:00Z"},
                    "end": {"dateTime": "2025-06-15T09:30:00Z"},
                    "location": "Google Meet",
                },
                {
                    "summary": "Code review",
                    "start": {"dateTime": "2025-06-15T14:00:00Z"},
                    "end": {"dateTime": "2025-06-15T15:00:00Z"},
                    "location": None,
                },
            ]
        }

        # Create fetcher and fetch
        fetcher = CalendarFetcher(config, vault_path)
        state = fetcher.fetch_today()

        # Assertions
        assert isinstance(state, CalendarState)
        assert state.date is not None
        assert len(state.events) == 2
        assert state.events[0].title == "Team standup"
        assert state.events[0].all_day is False
        assert state.events[1].title == "Code review"
        assert state.fetched_at is not None

    @patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file")
    @patch("scripts.fetch.calendar_fetcher.build")
    def test_all_day_events_detected_correctly(self, mock_build, mock_creds, config, vault_path, fake_token):
        """Test all-day events are detected and formatted correctly."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_credentials = MagicMock()
        mock_credentials.expired = False
        mock_creds.return_value = mock_credentials

        # All-day event uses "date" instead of "dateTime"
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "summary": "Vacation",
                    "start": {"date": "2025-06-15"},
                    "end": {"date": "2025-06-20"},
                }
            ]
        }

        fetcher = CalendarFetcher(config, vault_path)
        state = fetcher.fetch_today()

        assert len(state.events) == 1
        assert state.events[0].all_day is True
        assert state.events[0].start == "2025-06-15"
        assert state.events[0].end == "2025-06-20"

    @patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file")
    @patch("scripts.fetch.calendar_fetcher.build")
    def test_tomorrow_preview_populated(self, mock_build, mock_creds, config, vault_path, fake_token):
        """Test tomorrow_preview is populated with tomorrow's events."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_credentials = MagicMock()
        mock_credentials.expired = False
        mock_creds.return_value = mock_credentials

        # Mock two calls: today and tomorrow
        call_count = [0]

        def mock_execute():
            call_count[0] += 1
            if call_count[0] == 1:  # First call is for today
                return {"items": [{"summary": "Today event", "start": {"dateTime": "2025-06-15T09:00:00Z"}, "end": {"dateTime": "2025-06-15T10:00:00Z"}}]}
            else:  # Second call is for tomorrow
                return {
                    "items": [
                        {"summary": "Tomorrow event 1", "start": {"dateTime": "2025-06-16T10:00:00Z"}, "end": {"dateTime": "2025-06-16T11:00:00Z"}},
                        {"summary": "Tomorrow event 2", "start": {"dateTime": "2025-06-16T14:00:00Z"}, "end": {"dateTime": "2025-06-16T15:00:00Z"}},
                    ]
                }

        mock_service.events.return_value.list.return_value.execute = mock_execute

        fetcher = CalendarFetcher(config, vault_path)
        state = fetcher.fetch_today()

        assert len(state.tomorrow_preview) == 2
        assert all(isinstance(e, CalendarTomorrowEvent) for e in state.tomorrow_preview)
        assert state.tomorrow_preview[0].title == "Tomorrow event 1"
        assert state.tomorrow_preview[1].title == "Tomorrow event 2"

    @patch("scripts.fetch.calendar_fetcher.sys.stdin.isatty")
    def test_missing_credentials_returns_empty_state(self, mock_isatty, config, vault_path):
        """Test missing credentials returns empty state without raising."""
        mock_isatty.return_value = False  # Non-interactive mode

        # Don't create token.json
        with patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file") as mock_creds:
            mock_creds.side_effect = FileNotFoundError("No token")
            fetcher = CalendarFetcher(config, vault_path)

            # Should not raise
            assert fetcher is not None
            state = fetcher.fetch_today()
            assert state.events == []
            assert state.tomorrow_preview == []

    @patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file")
    @patch("scripts.fetch.calendar_fetcher.build")
    def test_api_error_falls_back_to_stale_state(self, mock_build, mock_creds, config, vault_path, fake_token):
        """Test API errors fall back to stale state if available."""
        # First, write a stale state file
        stale_state = CalendarState(
            fetched_at="2025-06-14T06:00:00Z",
            date="2025-06-14",
            events=[CalendarEvent(title="Old event", start="2025-06-14T10:00:00Z", end="2025-06-14T11:00:00Z")],
        )
        state_path = Path(vault_path) / ".system" / "state" / "calendar_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(stale_state.model_dump_json())

        # Setup mock to fail
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_credentials = MagicMock()
        mock_credentials.expired = False
        mock_creds.return_value = mock_credentials

        # Make API call raise an exception
        mock_service.events.return_value.list.return_value.execute.side_effect = Exception("Network error")

        fetcher = CalendarFetcher(config, vault_path)
        state = fetcher.fetch_today()

        # Should return stale state
        assert len(state.events) == 1
        assert state.events[0].title == "Old event"

    @patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file")
    @patch("scripts.fetch.calendar_fetcher.build")
    def test_write_state_creates_file_at_correct_path(self, mock_build, mock_creds, config, vault_path, fake_token):
        """Test write_state creates file at correct path."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_credentials = MagicMock()
        mock_credentials.expired = False
        mock_creds.return_value = mock_credentials

        mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        fetcher = CalendarFetcher(config, vault_path)
        state = fetcher.fetch_today()

        # Write state
        success = fetcher.write_state(state)
        assert success is True

        # Check file exists
        state_path = Path(vault_path) / ".system" / "state" / "calendar_state.json"
        assert state_path.exists()

        # Verify content is valid JSON
        with open(state_path) as f:
            saved = json.load(f)
        assert saved["date"] is not None
        assert "events" in saved

    @patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file")
    @patch("scripts.fetch.calendar_fetcher.build")
    def test_write_state_returns_false_on_error(self, mock_build, mock_creds, config, vault_path, fake_token):
        """Test write_state returns False on write error."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_credentials = MagicMock()
        mock_credentials.expired = False
        mock_creds.return_value = mock_credentials

        mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        fetcher = CalendarFetcher(config, vault_path)
        state = fetcher.fetch_today()

        # Mock write failure
        with patch.object(Path, "write_text", side_effect=PermissionError("No access")):
            success = fetcher.write_state(state)
            assert success is False

    @patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file")
    @patch("scripts.fetch.calendar_fetcher.build")
    def test_event_with_no_title_uses_fallback(self, mock_build, mock_creds, config, vault_path, fake_token):
        """Test events without title use fallback text."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_credentials = MagicMock()
        mock_credentials.expired = False
        mock_creds.return_value = mock_credentials

        # Event with no "summary" key
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "start": {"dateTime": "2025-06-15T09:00:00Z"},
                    "end": {"dateTime": "2025-06-15T10:00:00Z"},
                }
            ]
        }

        fetcher = CalendarFetcher(config, vault_path)
        state = fetcher.fetch_today()

        assert len(state.events) == 1
        assert state.events[0].title == "(No title)"
