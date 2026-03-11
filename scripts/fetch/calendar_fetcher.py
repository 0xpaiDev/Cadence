"""
Google Calendar fetcher.

Fetches today's and tomorrow's events from Google Calendar API.
"""

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from scripts.config import Config
from scripts.schemas import CalendarEvent, CalendarState, CalendarTomorrowEvent, load_state

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class CalendarFetcher:
    """Fetch events from Google Calendar."""

    def __init__(self, config: Config, vault_path: str):
        """
        Initialize calendar fetcher.

        Args:
            config: Configuration
            vault_path: Path to vault directory
        """
        self._credentials_path = config.google_credentials_path
        self._token_path = Path(vault_path) / ".system" / "config" / "token.json"
        self._state_path = Path(vault_path) / ".system" / "state" / "calendar_state.json"
        self._service = None

        # Try to load existing token
        credentials = None
        if self._token_path.exists():
            try:
                credentials = Credentials.from_authorized_user_file(self._token_path, SCOPES)
                # Refresh if expired
                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                    self._save_token(credentials)
            except Exception as e:
                logger.error(f"Failed to load existing token: {e}")
                credentials = None

        # If no token, try interactive auth or set service to None
        if not credentials:
            if sys.stdin.isatty():
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self._credentials_path, SCOPES
                    )
                    credentials = flow.run_local_server(port=8080, open_browser=True)
                    self._save_token(credentials)
                except Exception as e:
                    logger.error(f"Interactive authorization failed: {e}")
                    self._service = None
                    return
            else:
                logger.error(
                    "No token found and not in interactive mode. "
                    "Run calendar_fetcher.py interactively to authorize."
                )
                self._service = None
                return

        # Build the service
        try:
            self._service = build("calendar", "v3", credentials=credentials)
        except Exception as e:
            logger.error(f"Failed to build calendar service: {e}")
            self._service = None

    def fetch_today(self) -> CalendarState:
        """
        Fetch today's calendar events.

        Returns:
            CalendarState with today's events and tomorrow preview
        """
        if self._service is None:
            today = datetime.now().date()
            return self._empty_state(today.isoformat())

        try:
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            day_after = tomorrow + timedelta(days=1)

            today_str = today.isoformat()
            tomorrow_str = tomorrow.isoformat()
            day_after_str = day_after.isoformat()

            # Fetch today's events
            today_events = self._fetch_events_for_date(today_str)

            # Fetch tomorrow's preview
            tomorrow_events = self._fetch_events_for_date(tomorrow_str, max_results=5)

            return CalendarState(
                fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                date=today_str,
                events=today_events,
                tomorrow_preview=tomorrow_events,
            )
        except Exception as e:
            logger.error(f"Error fetching calendar: {e}")
            # Try to return stale state
            stale_state = load_state(self._state_path, CalendarState)
            if stale_state:
                return stale_state
            today = datetime.now().date()
            return self._empty_state(today.isoformat())

    def write_state(self, state: CalendarState) -> bool:
        """
        Write calendar state to vault.

        Args:
            state: CalendarState to write

        Returns:
            True if successful
        """
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Failed to write calendar state: {e}")
            return False

    def _fetch_events_for_date(self, date_str: str, max_results: int = 250) -> list:
        """
        Fetch events for a specific date from all calendars.

        Args:
            date_str: ISO date string (YYYY-MM-DD)
            max_results: Maximum results to return

        Returns:
            List of CalendarEvent or CalendarTomorrowEvent

        Raises:
            Exception: If API call fails
        """
        if self._service is None:
            return []

        # Time range for the day in UTC
        time_min = f"{date_str}T00:00:00Z"
        time_max = f"{date_str}T23:59:59Z"

        events = []

        # Get list of all calendars
        try:
            calendars_result = self._service.calendarList().list().execute()
            calendar_ids = [cal["id"] for cal in calendars_result.get("items", [])]
        except Exception as e:
            logger.warning(f"Failed to list calendars, falling back to primary: {e}")
            calendar_ids = ["primary"]

        # Fetch events from each calendar
        for calendar_id in calendar_ids:
            try:
                events_result = (
                    self._service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        singleEvents=True,
                        orderBy="startTime",
                        maxResults=max_results,
                    )
                    .execute()
                )

                for item in events_result.get("items", []):
                    # Detect all-day event
                    if "date" in item.get("start", {}):
                        # All-day event
                        start = item["start"]["date"]
                        end = item["end"]["date"]
                        all_day = True
                    else:
                        # Timed event
                        start = item.get("start", {}).get("dateTime", "")
                        end = item.get("end", {}).get("dateTime", "")
                        all_day = False

                    title = item.get("summary", "(No title)")
                    location = item.get("location")

                    # Determine if this is for tomorrow preview (max 5 items)
                    if max_results == 5:
                        # Create as CalendarTomorrowEvent
                        event = CalendarTomorrowEvent(
                            title=title, start=start, all_day=all_day
                        )
                    else:
                        # Create as CalendarEvent
                        event = CalendarEvent(
                            title=title,
                            start=start,
                            end=end,
                            location=location,
                            calendar=calendar_id,
                            all_day=all_day,
                        )

                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to fetch events from calendar {calendar_id}: {e}")
                continue

        return events

    def _empty_state(self, date: str) -> CalendarState:
        """
        Return an empty calendar state.

        Args:
            date: ISO date string (YYYY-MM-DD)

        Returns:
            CalendarState with no events
        """
        return CalendarState(
            fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            date=date,
            events=[],
            tomorrow_preview=[],
        )

    def _save_token(self, credentials: Credentials) -> None:
        """
        Save credentials to token.json.

        Args:
            credentials: Google credentials to save
        """
        try:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(
                credentials.to_json(), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save token: {e}")


if __name__ == "__main__":
    # Interactive authorization and test fetch
    import sys

    logging.basicConfig(level=logging.INFO)

    from scripts.config import load_config

    cfg = load_config()
    fetcher = CalendarFetcher(cfg, cfg.vault_path)
    state = fetcher.fetch_today()
    print(f"Fetched {len(state.events)} events for {state.date}")
    if fetcher.write_state(state):
        print(f"State saved to {fetcher._state_path}")
    else:
        print("Failed to save state")
