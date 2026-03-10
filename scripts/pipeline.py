"""
Main pipeline orchestration.

Fetch → Context → Draft generation pipeline.
"""

import logging
from pathlib import Path
from .config import load_config
from .runtime import ClaudeRuntime
from .build_context import build_context_from_vault
from .agent_daily_planner import generate_draft

logger = logging.getLogger(__name__)


def run_pipeline(config: Config = None) -> bool:
    """
    Run full pipeline: fetch → context → draft.

    Args:
        config: Configuration (default: load from cadence.toml)

    Returns:
        True if successful, False otherwise

    TODO: Implement
    - Load config if not provided
    - Initialize AgentRuntime
    - Call fetch_all() (not yet implemented)
    - Call build_context_from_vault()
    - Call generate_draft()
    - Write to vault/.system/drafts/today_draft.json
    - Update vault/.system/state/day_state.json
    - Log steps and errors
    """
    if config is None:
        config = load_config()

    logger.info("Pipeline starting")

    # TODO: Implement full pipeline
    logger.info("Pipeline complete")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = run_pipeline()
    exit(0 if success else 1)
