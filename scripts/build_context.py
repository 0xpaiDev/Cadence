"""
Build daily context markdown from state files.

Merges news, calendar, tasks, and training into a single markdown document
for the AI agent to use as context.
"""

from pathlib import Path
from .schemas import CalendarState, NewsState, DayTasks
from .config import Config


def build_context_from_vault(vault_path: str, config: Config) -> str:
    """
    Merge all state files into daily context markdown.

    Args:
        vault_path: Path to vault directory
        config: Configuration with token budget

    Returns:
        Markdown context document

    TODO: Implement context building
    - Load calendar_state.json
    - Load news_state.json
    - Read data/tasks/today.md
    - Read data/training/plan.md
    - Merge into markdown
    - Respect token_budget (trim if needed)
    """
    # Placeholder: return empty context
    return "# Daily Context\n\nTODO: Implement context builder\n"
