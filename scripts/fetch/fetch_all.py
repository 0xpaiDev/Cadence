"""
Orchestrate all fetchers.

Cron entry point: fetches news and calendar, writes state files.
"""

import logging
from pathlib import Path
from ..config import Config, load_config

logger = logging.getLogger(__name__)


def fetch_all(config: Config = None) -> bool:
    """
    Run all fetchers: news and calendar.

    Args:
        config: Configuration (default: load from cadence.toml)

    Returns:
        True if successful, False otherwise

    TODO: Implement
    - Load config if not provided
    - Initialize NewsFetcher and CalendarFetcher
    - Call fetch on each
    - Write state files to vault/.system/state/
    - Log all steps
    - Return success (one failure doesn't fail entire fetch)
    """
    if config is None:
        config = load_config()

    logger.info("Fetchers starting")

    # TODO: Implement all fetchers
    logger.info("Fetchers complete")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = fetch_all()
    exit(0 if success else 1)
