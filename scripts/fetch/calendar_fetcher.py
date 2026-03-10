"""
Google Calendar fetcher.

Fetches today's and tomorrow's events from Google Calendar API.
"""

import logging
from pathlib import Path
from ..schemas import CalendarState, CalendarEvent, CalendarTomorrowEvent
from ..config import Config

logger = logging.getLogger(__name__)


class CalendarFetcher:
    """Fetch events from Google Calendar."""

    def __init__(self, config: Config, vault_path: str):
        """
        Initialize calendar fetcher.

        Args:
            config: Configuration
            vault_path: Path to vault directory

        TODO: Implement
        - Load google_credentials.json from vault/.system/config/
        - Initialize Google Calendar service
        - Set up token refresh
        """
        self.config = config
        self.vault_path = Path(vault_path)

    def fetch_today(self) -> CalendarState:
        """
        Fetch today's calendar events.

        Returns:
            CalendarState with today's events and tomorrow preview

        TODO: Implement
        - Use Google Calendar API to fetch events
        - Convert to CalendarEvent objects
        - Get first event of tomorrow as preview
        - Return CalendarState
        """
        return CalendarState(
            fetched_at="TODO",
            date="TODO",
            events=[],
            tomorrow_preview=[],
        )

    def write_state(self, state: CalendarState) -> bool:
        """
        Write calendar state to vault.

        Args:
            state: CalendarState to write

        Returns:
            True if successful

        TODO: Implement
        - Write to vault/.system/state/calendar_state.json
        """
        return True
