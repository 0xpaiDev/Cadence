"""
Build daily context markdown from state files.

Merges news, calendar, tasks, and training into a single markdown document
for the AI agent to use as context.
"""

import logging
from datetime import datetime
from pathlib import Path

from scripts.config import Config
from scripts.schemas import (
    CalendarEvent,
    CalendarState,
    CalendarTomorrowEvent,
    NewsItem,
    NewsState,
    load_state,
)

logger = logging.getLogger(__name__)


def _render_news_section(items: list[NewsItem], max_items: int) -> str:
    """
    Render news briefing section.

    Args:
        items: List of news items (assumed pre-sorted by relevance desc)
        max_items: Maximum items to include

    Returns:
        Markdown section (empty string if no items)
    """
    if not items:
        return ""

    capped = items[:max_items]
    lines = ["## News Briefing", ""]
    for item in capped:
        lines.append(f"- [{item.title}]({item.url}) — {item.summary}")
    lines.append("")
    return "\n".join(lines)


def _render_schedule_section(events: list[CalendarEvent]) -> str:
    """
    Render schedule section.

    Args:
        events: List of calendar events (will be sorted chronologically)

    Returns:
        Markdown section (empty string if no events)
    """
    if not events:
        return ""

    # Sort by ISO start string (handles all-day events naturally)
    sorted_events = sorted(events, key=lambda e: e.start)

    lines = ["## Schedule", ""]
    for event in sorted_events:
        if event.all_day:
            lines.append(f"- All day: {event.title}")
        else:
            try:
                start_dt = datetime.fromisoformat(
                    event.start.replace("Z", "+00:00")
                )
                end_dt = datetime.fromisoformat(
                    event.end.replace("Z", "+00:00")
                )
                start_time = start_dt.strftime("%H:%M")
                end_time = end_dt.strftime("%H:%M")
                lines.append(f"- {start_time}–{end_time}: {event.title}")
            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Failed to parse event times for '{event.title}': {e}"
                )
                lines.append(f"- {event.title}")

    lines.append("")
    return "\n".join(lines)


def _render_tomorrow_section(
    events: list[CalendarTomorrowEvent],
) -> str:
    """
    Render tomorrow preview section.

    Args:
        events: List of tomorrow's events (will be sorted chronologically)

    Returns:
        Markdown section (empty string if no events)
    """
    if not events:
        return ""

    # Sort by ISO start string
    sorted_events = sorted(events, key=lambda e: e.start)

    lines = ["## Tomorrow Preview", ""]
    for event in sorted_events:
        if event.all_day:
            lines.append(f"- All day: {event.title}")
        else:
            try:
                start_dt = datetime.fromisoformat(
                    event.start.replace("Z", "+00:00")
                )
                start_time = start_dt.strftime("%H:%M")
                lines.append(f"- {start_time}: {event.title}")
            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Failed to parse tomorrow event time for '{event.title}': {e}"
                )
                lines.append(f"- {event.title}")

    lines.append("")
    return "\n".join(lines)


def build_context_from_vault(vault_path: str, config: Config) -> str:
    """
    Merge all state files into daily context markdown.

    Loads calendar, news, tasks, and training from vault and merges
    into a single markdown document. Missing or invalid sections are
    gracefully skipped.

    Token budget is enforced by trimming news items (lowest relevance
    first) until the document fits.

    Args:
        vault_path: Path to vault directory
        config: Configuration with token_budget and news_max_items

    Returns:
        Markdown context document (never empty, always has header)
    """
    vault = Path(vault_path)
    state_dir = vault / ".system" / "state"

    # Load state files
    calendar_state: CalendarState | None = load_state(
        str(state_dir / "calendar_state.json"), CalendarState
    )
    news_state: NewsState | None = load_state(
        str(state_dir / "news_state.json"), NewsState
    )

    # Read raw text files
    tasks_path = vault / "data" / "tasks" / "today.md"
    training_path = vault / "data" / "training" / "plan.md"

    tasks_content = ""
    if tasks_path.exists():
        try:
            tasks_content = tasks_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read tasks file: {e}")

    training_content = ""
    if training_path.exists():
        try:
            training_content = training_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read training file: {e}")

    # Build sections with full news items (sorted by relevance desc)
    news_items = (
        sorted(news_state.items, key=lambda x: x.relevance, reverse=True)
        if news_state and news_state.items
        else []
    )

    schedule_events = (
        calendar_state.events if calendar_state and calendar_state.events else []
    )
    tomorrow_events = (
        calendar_state.tomorrow_preview
        if calendar_state and calendar_state.tomorrow_preview
        else []
    )

    # Assemble document and apply token budget trimming
    def assemble_doc(news_subset: list[NewsItem]) -> str:
        parts = ["# Daily Context", ""]
        parts.append(_render_news_section(news_subset, config.news_max_items))
        parts.append(_render_schedule_section(schedule_events))
        parts.append(_render_tomorrow_section(tomorrow_events))

        if tasks_content:
            parts.append("## Tasks")
            parts.append("")
            parts.append(tasks_content)
            parts.append("")

        if training_content:
            parts.append("## Training")
            parts.append("")
            parts.append(training_content)
            parts.append("")

        return "\n".join(parts)

    # Initial assembly
    context = assemble_doc(news_items)
    token_count = len(context) // 4

    # Trim news if needed
    while token_count > config.token_budget and news_items:
        news_items.pop()
        context = assemble_doc(news_items)
        token_count = len(context) // 4

    if calendar_state is None:
        logger.warning("Calendar state not found or invalid")
    if news_state is None:
        logger.warning("News state not found or invalid")

    return context
