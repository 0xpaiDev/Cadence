"""
Generate daily draft via AI agent.

Calls Claude with daily context to produce a structured JSON draft plan.
"""

import json
import logging
from .runtime import AgentRuntime
from .schemas import Draft
from .config import Config

logger = logging.getLogger(__name__)


def generate_draft(
    context: str,
    config: Config,
    runtime: AgentRuntime,
) -> dict:
    """
    Generate daily draft JSON from context.

    Args:
        context: Daily context markdown
        config: Configuration
        runtime: Agent runtime instance

    Returns:
        Validated draft dict

    Raises:
        ValueError: If draft JSON invalid

    TODO: Implement
    - Load daily_template.md from vault/.system/config/
    - Build system prompt with template
    - Call runtime.call(system_prompt, context, max_tokens)
    - Parse response as JSON
    - Validate against Draft schema
    - Return dict
    """
    # Placeholder: return empty draft
    return {
        "schema_version": 1,
        "date": "TODO",
        "generated_at": "TODO",
        "news": [],
        "schedule": [],
        "tomorrow_preview": [],
        "tasks": [],
        "training": {"summary": "TODO"},
        "agent_suggestions": [],
    }
