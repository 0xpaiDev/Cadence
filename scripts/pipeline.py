"""
Main pipeline orchestration.

Fetch → Context → Draft generation pipeline.
"""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from scripts.agent_daily_planner import generate_draft
from scripts.build_context import build_context_from_vault
from scripts.config import Config, load_config
from scripts.fetch.fetch_all import fetch_all
from scripts.runtime import ClaudeRuntime
from scripts.schemas import DayState, DayStatus

logger = logging.getLogger(__name__)


def run_pipeline(config: Optional[Config] = None) -> bool:
    """
    Run full pipeline: fetch → context → draft.

    Args:
        config: Configuration (default: load from cadence.toml)

    Returns:
        True if successful, False otherwise
    """
    try:
        # 1. Load config if not provided
        if config is None:
            config = load_config()

        logger.info("Pipeline starting")

        # Ensure vault directories exist
        vault = Path(config.vault_path)
        state_dir = vault / ".system" / "state"
        context_dir = vault / ".system" / "context"
        drafts_dir = vault / ".system" / "drafts"

        state_dir.mkdir(parents=True, exist_ok=True)
        context_dir.mkdir(parents=True, exist_ok=True)
        drafts_dir.mkdir(parents=True, exist_ok=True)

        # 2. Initialize ClaudeRuntime
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set")
            return False

        runtime = ClaudeRuntime(model=config.agent_model, api_key=api_key)
        logger.info("Agent runtime initialized")

        # 3. Fetch all (calendar + news) — graceful failure
        try:
            logger.info("Starting fetchers")
            fetch_all(config)
            logger.info("Fetch completed")
        except Exception as e:
            logger.warning(f"Fetch failed (continuing): {e}")

        # 4. Build context from vault state files
        try:
            logger.info("Building context")
            context = build_context_from_vault(vault, config)

            context_path = context_dir / "daily_context.md"
            context_path.write_text(context)
            logger.info(f"Context written to {context_path}")
        except Exception as e:
            logger.error(f"Context building failed: {e}")
            return False

        # 5. Generate draft from context
        try:
            logger.info("Generating draft")
            draft_dict = generate_draft(context, config, runtime)

            draft_path = drafts_dir / "today_draft.json"
            with draft_path.open("w") as f:
                json.dump(draft_dict, f, indent=2)
            logger.info(f"Draft written to {draft_path}")
        except Exception as e:
            logger.error(f"Draft generation failed: {e}")
            return False

        # 6. Write day state
        try:
            today = date.today().isoformat()
            day_state = DayState(
                date=today,
                status=DayStatus.DRAFT_PENDING,
                draft_generated_at=datetime.now().isoformat(),
            )

            state_path = state_dir / "day_state.json"
            with state_path.open("w") as f:
                json.dump(day_state.model_dump(), f, indent=2)
            logger.info(f"Day state written to {state_path}")
        except Exception as e:
            logger.error(f"Day state write failed: {e}")
            return False

        logger.info("Pipeline complete")
        return True

    except Exception as e:
        logger.error(f"Pipeline failed with unexpected error: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = run_pipeline()
    exit(0 if success else 1)
