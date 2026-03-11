"""
Orchestrate all fetchers.

Cron entry point: fetches news and calendar, writes state files.
"""

import logging
from pathlib import Path
from scripts.config import Config, load_config
from scripts.fetch.calendar_fetcher import CalendarFetcher

logger = logging.getLogger(__name__)


def fetch_all(config: Config = None) -> bool:
    """
    Run all fetchers: news and calendar.

    Args:
        config: Configuration (default: load from cadence.toml)

    Returns:
        True if successful, False otherwise
    """
    if config is None:
        config = load_config()

    logger.info("Fetchers starting")
    all_success = True

    # Calendar fetcher
    try:
        logger.info("Fetching calendar events")
        calendar_fetcher = CalendarFetcher(config, config.vault_path)
        calendar_state = calendar_fetcher.fetch_today()
        if calendar_fetcher.write_state(calendar_state):
            logger.info(f"Calendar state written: {len(calendar_state.events)} events for {calendar_state.date}")
        else:
            logger.error("Failed to write calendar state")
            all_success = False
    except Exception as e:
        logger.error(f"Calendar fetch failed: {e}")
        all_success = False

    # NewsFetcher will be implemented in Phase 4
    # TODO: Implement NewsFetcher and wire it in here

    logger.info("Fetchers complete")
    return all_success


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = fetch_all()
    exit(0 if success else 1)
