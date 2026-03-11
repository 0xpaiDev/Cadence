"""
RSS news fetcher.

Fetches news from configured RSS feeds and scores by relevance.
"""

import logging
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import feedparser

from scripts.schemas import NewsState, NewsItem
from scripts.config import Config

logger = logging.getLogger(__name__)

# Hardcoded news sources
NEWS_SOURCES: list[tuple[str, str]] = [
    ("Anthropic Blog", "https://www.anthropic.com/rss.xml"),
    ("AI Safety Institute", "https://www.gov.uk/government/organisations/ai-safety-institute.atom"),
    ("MIT Tech Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/"),
    ("Hacker News", "https://news.ycombinator.com/rss"),
]

# Keywords for relevance scoring
RELEVANCE_KEYWORDS: list[str] = [
    "anthropic", "claude", "ai", "llm", "machine learning",
    "safety", "alignment", "model", "gpt",
]

# Topic classification
TOPIC_MAP: dict[str, str] = {
    "anthropic": "Anthropic",
    "claude": "Anthropic",
    "safety": "AI Safety",
    "alignment": "AI Safety",
    "llm": "AI",
    "gpt": "AI",
    "model": "AI",
    "machine learning": "AI",
    "ai": "AI",
}


class NewsFetcher:
    """Fetch news from RSS feeds."""

    def __init__(self, config: Config):
        """
        Initialize news fetcher.

        Args:
            config: Configuration with vault path
        """
        self.config = config
        self._sources = NEWS_SOURCES
        self._state_path = (
            Path(config.vault_path) / ".system" / "state" / "news_state.json"
        )

    def _score_relevance(self, title: str, summary: str) -> float:
        """
        Score item relevance based on keyword matches.

        Args:
            title: Article title
            summary: Article summary

        Returns:
            Relevance score from 0.0 to 1.0
        """
        text = (title + " " + summary).lower()
        matches = 0
        for kw in RELEVANCE_KEYWORDS:
            # Use word boundaries to avoid substring matches (e.g., "ai" in "rain")
            if re.search(rf"\b{kw}\b", text):
                matches += 1
        return round(min(1.0, matches / len(RELEVANCE_KEYWORDS)), 2)

    def _infer_topic(self, title: str, source: str) -> str:
        """
        Infer topic from title and source.

        Args:
            title: Article title
            source: Source name

        Returns:
            Topic string
        """
        combined = (title + " " + source).lower()
        for keyword, topic in TOPIC_MAP.items():
            if keyword in combined:
                return topic
        return "Tech"


    def _parse_entry(self, entry: dict, source_name: str) -> NewsItem | None:
        """
        Parse a single feedparser entry into NewsItem.

        Args:
            entry: feedparser entry dict
            source_name: Name of news source

        Returns:
            NewsItem or None if parsing failed
        """
        try:
            url = entry.get("link", "")
            if not url:
                return None

            title = entry.get("title", "").strip() or "(No title)"
            summary = entry.get("summary", "").strip()

            # Strip HTML tags from summary
            summary = re.sub(r"<[^>]+>", "", summary).strip()

            # Convert published_parsed (9-tuple) to ISO 8601
            pp = entry.get("published_parsed")
            if pp:
                published = (
                    datetime(*pp[:6], tzinfo=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
            else:
                published = (
                    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                )

            return NewsItem(
                title=title,
                source=source_name,
                url=url,
                summary=summary[:500],  # Cap at 500 chars
                topic=self._infer_topic(title, source_name),
                published=published,
                relevance=self._score_relevance(title, summary),
            )
        except Exception as e:
            logger.warning(f"Failed to parse entry from {source_name}: {e}")
            return None

    def fetch(self) -> NewsState:
        """
        Fetch news from all sources.

        Returns:
            NewsState with fetched items, sorted by relevance descending.
        """
        all_items: list[NewsItem] = []
        errors: list[str] = []
        seen_urls: set[str] = set()

        for source_name, url in self._sources:
            try:
                feed = feedparser.parse(url)

                # Bozo flag indicates malformed XML; still parse if entries exist
                if feed.get("bozo") and not feed.get("entries"):
                    err = f"{source_name}: feed parse error"
                    logger.warning(err)
                    errors.append(err)
                    continue

                for entry in feed.get("entries", []):
                    item = self._parse_entry(entry, source_name)
                    if item and item.url not in seen_urls:
                        seen_urls.add(item.url)
                        all_items.append(item)

            except Exception as e:
                err = f"{source_name}: {e}"
                logger.error(err)
                errors.append(err)

        # Sort by relevance descending, cap at max items
        all_items.sort(key=lambda x: x.relevance, reverse=True)
        capped = all_items[: self.config.news_max_items]

        return NewsState(
            fetched_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            items=capped,
            errors=errors,
        )

    def write_state(self, state: NewsState) -> bool:
        """
        Write news state to vault.

        Args:
            state: NewsState to write

        Returns:
            True if successful, False otherwise
        """
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                state.model_dump_json(indent=2), encoding="utf-8"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to write news state: {e}")
            return False


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO)
    from scripts.config import load_config

    cfg = load_config()
    fetcher = NewsFetcher(cfg)
    state = fetcher.fetch()
    print(f"Fetched {len(state.items)} news items, {len(state.errors)} errors")
    if fetcher.write_state(state):
        print(f"State saved to {fetcher._state_path}")
    else:
        print("Failed to save state")
