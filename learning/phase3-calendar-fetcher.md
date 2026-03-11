# Phase 3: Google Calendar Fetcher – Learning Guide

Phase 3 introduces external API integration via Google Calendar, OAuth2 authentication, and the fetcher pattern. This guide covers the key concepts, libraries, and patterns used in the implementation.

---

## OAuth2 Authentication with Google Calendar API

### The Three OAuth2 Flows

Google supports three OAuth2 flows depending on your use case:

1. **Server-to-Server (Service Account)** — Used for backend services that don't need user interaction. Requires a private key. Good for cron jobs that have been pre-authorized.
2. **Authorization Code Flow (Web App)** — Standard web app flow where users click "Authorize" and are redirected back. Requires a client secret.
3. **Installed App Flow** — Used by desktop/CLI apps. User is presented a browser authorization URL, clicks "Allow", and the flow receives a code at `localhost:port`. This is what Cadence uses.

**Why Installed App Flow for Cadence?**
- The pipeline runs on a personal VPS (not a shared server).
- Authorization happens once during setup, then tokens auto-refresh.
- No client secret needed in vault (only client ID, which is public).
- Tokens are stored securely in `vault/.system/config/token.json`.

### Token Lifecycle

```
First run (interactive setup):
  1. User runs: python -m scripts.fetch.calendar_fetcher
  2. Browser opens to Google's consent screen
  3. User clicks "Allow"
  4. Code is returned to localhost:8080
  5. Code is exchanged for access_token + refresh_token
  6. Tokens saved to token.json

Subsequent runs (headless cron):
  1. Load token.json (contains both tokens)
  2. Check if token is expired
  3. If expired: call credentials.refresh(Request()) → Google returns new access_token
  4. Save refreshed token back to token.json
  5. Use new credentials to make API calls
```

**Key insight:** The refresh_token never expires (unless user revokes), so the cron process can keep working indefinitely without re-authorization.

### The `google-auth-oauthlib` Library

**Import path:** `from google_auth_oauthlib.flow import InstalledAppFlow`

**The flow object:**
```python
flow = InstalledAppFlow.from_client_secrets_file(
    credentials_json_path,
    scopes=["https://www.googleapis.com/auth/calendar.readonly"]
)
credentials = flow.run_local_server(port=0)  # Opens browser, listens on random port
```

**Credentials object:**
- `.token` — current access token (for API calls)
- `.refresh_token` — long-lived token (survives token expiration)
- `.expired` — boolean, true if token TTL has passed
- `.refresh(Request())` — exchanges refresh_token for new access_token
- `.to_json()` — serializes to JSON for storage
- `.from_authorized_user_file()` — loads from token.json

**Refresh pattern:**
```python
if credentials.expired and credentials.refresh_token:
    credentials.refresh(Request())
    # Save the updated token with new expiration time
```

### Scopes and Permissions

Google Calendar API uses scopes to limit what the app can do:
- `https://www.googleapis.com/auth/calendar` — Read/write access
- `https://www.googleapis.com/auth/calendar.readonly` — Read-only (preferred for security)

In Cadence, we only need read access to fetch events, so use `.readonly`.

---

## Google Calendar API Basics

### Build the Service

```python
from googleapiclient.discovery import build
service = build("calendar", "v3", credentials=credentials)
```

The `build()` function loads the API schema and returns an object that mirrors the REST API structure.

### Fetching Events

```python
events_result = service.events().list(
    calendarId="primary",  # user's default calendar
    timeMin="2025-06-15T00:00:00Z",
    timeMax="2025-06-15T23:59:59Z",
    singleEvents=True,  # expand recurring events
    orderBy="startTime",  # sort by start time
    maxResults=250
).execute()
```

**Arguments:**
- `calendarId="primary"` — special value for the user's main calendar
- `timeMin/timeMax` — RFC 3339 format (ISO 8601 with Z suffix for UTC). Can also use `2025-06-15` for all-day queries.
- `singleEvents=True` — if an event repeats 10 times, return 10 separate items (not 1 recurring event)
- `orderBy="startTime"` — sort by start time (only works with `singleEvents=True`)
- `maxResults` — cap the number of items returned

**Response:**
```python
{
    "items": [
        {
            "id": "...",
            "summary": "Team standup",  # Event title
            "start": {"dateTime": "2025-06-15T09:00:00Z"},  # Timed event
            "end": {"dateTime": "2025-06-15T09:30:00Z"},
            "location": "Google Meet"
        },
        {
            "id": "...",
            "summary": "Vacation",
            "start": {"date": "2025-06-15"},  # All-day event (no time)
            "end": {"date": "2025-06-20"}
        }
    ]
}
```

---

## Timed Events vs All-Day Events

This is a critical detail for parsing:

### Timed Event
```json
{
    "start": {"dateTime": "2025-06-15T09:00:00Z"},
    "end": {"dateTime": "2025-06-15T09:30:00Z"}
}
```
- Uses `dateTime` key with time component
- Format: RFC 3339 with timezone offset (e.g., `+01:00` or `Z` for UTC)
- Can be parsed with `datetime.fromisoformat()` (Python 3.7+)

### All-Day Event
```json
{
    "start": {"date": "2025-06-15"},
    "end": {"date": "2025-06-20"}
}
```
- Uses `date` key with date-only format
- Format: `YYYY-MM-DD`
- End date is exclusive (event on June 15-19 has `end: {"date": "2025-06-20"}`)

**Detection pattern:**
```python
if "date" in item["start"]:
    # All-day
    start = item["start"]["date"]  # "2025-06-15"
    all_day = True
else:
    # Timed
    start = item["start"]["dateTime"]  # "2025-06-15T09:00:00Z"
    all_day = False
```

---

## Error Handling in Calendar Fetcher

### Expected Exceptions

1. **`FileNotFoundError`** — credentials JSON not found (setup not done)
   - Caught during token load → log error → graceful degradation (return empty state)

2. **`HttpError`** — from googleapiclient, raised when API call fails
   - Common: 403 (permission denied), 404 (calendar not found), 429 (rate limit)
   - Caught in outer try/except → attempt stale state fallback

3. **Network errors** — socket timeout, connection refused, etc.
   - Any exception during `.execute()` → outer try/except handles it

### Graceful Degradation Strategy

```
API call fails
  └─ Try to load stale state from vault/.system/state/calendar_state.json
      └─ If stale state exists: return it (old data is better than crash)
          └─ If no stale state: return empty CalendarState (day has no events)
```

This ensures the pipeline never crashes due to calendar issues. The context builder will skip the schedule section if events are empty, and the agent will still generate a plan.

---

## Testing with Mocks

### Why Mock the Service?

- No live API calls during tests → tests run instantly (no flakiness)
- No need for valid credentials file
- Can simulate failures without breaking Google's terms
- Deterministic: same input always gives same output

### Mock Pattern

```python
from unittest.mock import MagicMock, patch

# Mock the build() function
with patch("scripts.fetch.calendar_fetcher.build") as mock_build:
    # Create a fake service object
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    # Configure what the service returns
    mock_service.events().list().execute.return_value = {
        "items": [
            {
                "summary": "Standup",
                "start": {"dateTime": "2025-06-15T09:00:00Z"},
                "end": {"dateTime": "2025-06-15T09:30:00Z"}
            }
        ]
    }

    # Now instantiate and test
    fetcher = CalendarFetcher(config, vault_path)
    state = fetcher.fetch_today()
    assert len(state.events) == 1
```

### Mocking Credentials

Similarly, mock `Credentials.from_authorized_user_file` to avoid needing a real token file:

```python
with patch("scripts.fetch.calendar_fetcher.Credentials.from_authorized_user_file") as mock_creds:
    mock_credentials = MagicMock()
    mock_credentials.expired = False
    mock_creds.return_value = mock_credentials
    # Now the CalendarFetcher can load credentials without a real file
```

---

## The Fetcher Pattern

The `CalendarFetcher` class demonstrates a reusable pattern for external API integrations:

```python
class Fetcher:
    def __init__(self, config: Config, vault_path: str):
        """Initialize: load credentials, set up paths, create service."""

    def fetch(self) -> State:
        """Fetch data, parse to Pydantic model, handle errors gracefully."""

    def write_state(self, state: State) -> bool:
        """Write state to vault, return success."""
```

This pattern is repeated in `NewsFetcher` (Phase 4) and any future integrations. Key principles:
- Configuration comes from Config object
- Vault paths are pre-configured in `__init__`
- Errors never crash; graceful degradation via stale state
- Pydantic models ensure type safety
- Tests mock external services

---

## Key Files

- **`scripts/fetch/calendar_fetcher.py`** — Full implementation (260+ lines)
  - `__init__()` — OAuth2 token setup
  - `fetch_today()` — Query API, parse events
  - `write_state()` — Save JSON to vault
  - `_fetch_events_for_date()` — Helper for batch event parsing
  - `_empty_state()` — Fallback when auth fails
  - `_save_token()` — Persist token after refresh

- **`scripts/config.py`** — New field: `google_credentials_path`
  - Defaults to `vault/.system/config/google_credentials.json`
  - Computed in `load_config()` from `vault.path` config

- **`tests/test_fetchers.py`** — 8 comprehensive tests
  - Mock API responses
  - Test all-day detection
  - Test stale state fallback
  - Test token file I/O
  - Test missing credentials handling

---

## Next: Phase 4 (News Fetcher)

Phase 4 follows the same pattern with RSS feeds instead of Google Calendar:
- New `NewsFetcher` class in `scripts/fetch/news_fetcher.py`
- Fetch RSS feeds → parse to `NewsItem` objects
- Write `news_state.json` to vault
- Wire into `fetch_all.py` alongside calendar

The same graceful degradation and testing patterns apply.

---

## Summary

- **OAuth2 Installed App Flow** enables one-time setup with ongoing auto-refresh
- **Token lifecycle** is managed by `google-auth-oauthlib` (load, refresh, save)
- **All-day vs timed events** require different JSON parsing
- **Graceful degradation** via stale state fallback keeps the pipeline resilient
- **Mocking** makes tests fast and deterministic
- **The fetcher pattern** provides a template for future API integrations
