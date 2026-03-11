"""Tests for news and calendar fetchers."""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.fetch.calendar_fetcher import CalendarFetcher
from scripts.fetch.news_fetcher import NewsFetcher
from scripts.schemas import (
    CalendarEvent,
    CalendarState,
    CalendarTomorrowEvent,
    NewsItem,
    NewsState,
)


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


class TestNewsFetcherBasics:
    """Test NewsFetcher basic functionality."""

    @patch("scripts.fetch.news_fetcher.feedparser.parse")
    def test_fetch_returns_valid_news_state(self, mock_parse, config):
        """Test fetching valid news returns NewsState with items."""
        # Setup mock feed data
        mock_feed = MagicMock()
        mock_feed.get.side_effect = lambda k, d=None: {
            "bozo": False,
            "entries": [
                {
                    "title": "Claude 4 Released",
                    "link": "https://anthropic.com/claude-4",
                    "summary": "New Claude model with AI safety features",
                    "published_parsed": (2025, 6, 15, 10, 0, 0, 0, 166, 0),
                },
            ],
        }.get(k, d)

        mock_parse.return_value = mock_feed

        fetcher = NewsFetcher(config)
        state = fetcher.fetch()

        assert isinstance(state, NewsState)
        assert len(state.items) > 0
        assert all(isinstance(item, NewsItem) for item in state.items)
        assert state.fetched_at is not None

    def test_relevance_scoring_high_for_ai_keywords(self, config):
        """Test relevance scoring is high for AI-related keywords."""
        fetcher = NewsFetcher(config)
        score = fetcher._score_relevance(
            "Claude AI safety model",
            "Anthropic alignment research",
        )
        assert score >= 0.4

    def test_relevance_scoring_zero_for_irrelevant(self, config):
        """Test relevance scoring is zero for unrelated content."""
        fetcher = NewsFetcher(config)
        score = fetcher._score_relevance(
            "Weather in London tomorrow",
            "Rain expected on Friday",
        )
        assert score == 0.0

    @patch("scripts.fetch.news_fetcher.feedparser.parse")
    def test_items_sorted_by_relevance_descending(self, mock_parse, config):
        """Test items are sorted by relevance descending."""
        mock_feed = MagicMock()

        def get_side_effect(k, d=None):
            data = {
                "bozo": False,
                "entries": [
                    {
                        "title": "Unrelated weather",
                        "link": "https://news.com/weather",
                        "summary": "Rain tomorrow",
                        "published_parsed": (2025, 6, 15, 10, 0, 0, 0, 166, 0),
                    },
                    {
                        "title": "Claude AI breakthrough",
                        "link": "https://anthropic.com/claude",
                        "summary": "Anthropic releases new model",
                        "published_parsed": (2025, 6, 15, 10, 0, 0, 0, 166, 0),
                    },
                ],
            }
            return data.get(k, d)

        mock_feed.get = get_side_effect
        mock_parse.return_value = mock_feed

        fetcher = NewsFetcher(config)
        state = fetcher.fetch()

        assert len(state.items) == 2
        assert state.items[0].relevance >= state.items[1].relevance

    @patch("scripts.fetch.news_fetcher.feedparser.parse")
    def test_items_capped_at_news_max_items(self, mock_parse, config):
        """Test items are capped at config.news_max_items."""
        # Create 15 mock entries
        entries = [
            {
                "title": f"News item {i}",
                "link": f"https://news.com/item{i}",
                "summary": f"Summary for item {i}",
                "published_parsed": (2025, 6, 15, 10, 0, 0, 0, 166, 0),
            }
            for i in range(15)
        ]

        mock_feed = MagicMock()
        mock_feed.get.side_effect = lambda k, d=None: {"bozo": False, "entries": entries}.get(k, d)
        mock_parse.return_value = mock_feed

        fetcher = NewsFetcher(config)
        state = fetcher.fetch()

        assert len(state.items) <= config.news_max_items

    @patch("scripts.fetch.news_fetcher.feedparser.parse")
    def test_feed_error_logged_in_errors(self, mock_parse, config):
        """Test feed errors are logged in state.errors."""
        mock_parse.side_effect = Exception("Connection timeout")

        fetcher = NewsFetcher(config)
        state = fetcher.fetch()

        # Should return valid state without crashing
        assert isinstance(state, NewsState)
        assert len(state.errors) > 0
        assert len(state.items) == 0

    @patch("scripts.fetch.news_fetcher.feedparser.parse")
    def test_bozo_feed_with_entries_still_parsed(self, mock_parse, config):
        """Test bozo=True feeds with entries are still parsed."""
        mock_feed = MagicMock()
        mock_feed.get.side_effect = lambda k, d=None: {
            "bozo": True,
            "entries": [
                {
                    "title": "Malformed but parseable",
                    "link": "https://news.com/item",
                    "summary": "Still valid entry",
                    "published_parsed": (2025, 6, 15, 10, 0, 0, 0, 166, 0),
                },
            ],
        }.get(k, d)

        mock_parse.return_value = mock_feed

        fetcher = NewsFetcher(config)
        state = fetcher.fetch()

        # Should still parse entries despite bozo=True
        assert len(state.items) >= 1

    def test_write_state_creates_file_at_correct_path(self, config, vault_path):
        """Test write_state creates file at correct vault path."""
        # Create config with test vault path
        test_config = dataclasses.replace(config, vault_path=vault_path)

        # Create state
        state = NewsState(
            fetched_at="2025-06-15T06:00:00Z",
            items=[],
            errors=[],
        )

        fetcher = NewsFetcher(test_config)
        success = fetcher.write_state(state)

        assert success is True

        # Check file exists
        state_path = Path(vault_path) / ".system" / "state" / "news_state.json"
        assert state_path.exists()

        # Verify content
        with open(state_path) as f:
            saved = json.load(f)
        assert "items" in saved
        assert "fetched_at" in saved

    def test_write_state_returns_false_on_error(self, config):
        """Test write_state returns False on write error."""
        state = NewsState(
            fetched_at="2025-06-15T06:00:00Z",
            items=[],
            errors=[],
        )

        fetcher = NewsFetcher(config)

        # Mock write failure
        with patch.object(Path, "write_text", side_effect=PermissionError("No access")):
            success = fetcher.write_state(state)
            assert success is False

    @patch("scripts.fetch.news_fetcher.feedparser.parse")
    def test_duplicate_urls_deduplicated(self, mock_parse, config):
        """Test duplicate URLs across feeds are deduplicated."""
        # Both feeds return the same URL
        def parse_side_effect(url):
            mock_feed = MagicMock()
            mock_feed.get.side_effect = lambda k, d=None: {
                "bozo": False,
                "entries": [
                    {
                        "title": "Shared article",
                        "link": "https://news.com/shared",
                        "summary": "Claude AI news",
                        "published_parsed": (2025, 6, 15, 10, 0, 0, 0, 166, 0),
                    },
                ],
            }.get(k, d)
            return mock_feed

        mock_parse.side_effect = parse_side_effect

        fetcher = NewsFetcher(config)
        state = fetcher.fetch()

        # Should have only 1 item despite 4 sources
        assert len(state.items) == 1
