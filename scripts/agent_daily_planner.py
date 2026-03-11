"""
Generate daily draft via AI agent.

Calls Claude with daily context to produce a structured JSON draft plan.
"""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from scripts.config import Config
from scripts.runtime import AgentRuntime
from scripts.schemas import Draft

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
        FileNotFoundError: If template file not found
        ValueError: If draft JSON parsing fails
        ValidationError: If draft doesn't match schema
    """
    # 1. Load system prompt template
    template_path = Path(config.vault_path) / ".system" / "config" / config.planner_prompt_path
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    try:
        system_prompt = template_path.read_text()
    except Exception as e:
        logger.error(f"Failed to read template: {e}")
        raise FileNotFoundError(f"Could not read template: {template_path}") from e

    # 2. Call agent runtime with system prompt and context
    try:
        response = runtime.call(
            system_prompt=system_prompt,
            user_message=context,
            max_tokens=config.agent_max_tokens,
        )
    except Exception as e:
        logger.error(f"Agent runtime call failed: {e}")
        raise RuntimeError(f"Failed to call agent: {e}") from e

    # 3. Strip markdown code blocks if present
    response = response.strip()
    if response.startswith("```"):
        # Remove ```json or ``` prefix
        response = response.split("\n", 1)[1] if "\n" in response else response[3:]
    if response.endswith("```"):
        # Remove trailing ```
        response = response.rsplit("\n", 1)[0] if "\n" in response else response[:-3]
    response = response.strip()

    # 4. Parse response as JSON
    logger.debug(f"Agent response (first 500 chars): {response[:500]}")
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent response as JSON: {e}")
        logger.error(f"Full response was: {response}")
        raise ValueError(f"Agent response is not valid JSON: {e}") from e

    # 5. Validate against Draft schema
    try:
        draft = Draft.model_validate(parsed)
    except ValidationError as e:
        logger.error(f"Draft schema validation failed: {e}")
        raise ValueError(f"Agent response doesn't match Draft schema: {e}") from e

    # 6. Return as dict
    return draft.model_dump()
