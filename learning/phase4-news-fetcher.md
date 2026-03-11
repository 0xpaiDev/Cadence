# Phase 4: News RSS Fetcher — Implementation & Patterns

This guide captures the patterns, gotchas, and learning from implementing the news fetcher in Phase 4. It's designed for future developers or to refresh memory between sessions.

## Overview

The news fetcher retrieves articles from 4 RSS feeds, scores them by keyword relevance, deduplicates by URL, and writes a ranked list to `vault/.system/state/news_state.json`. It completes the fetch layer before the AI agent uses the merged context.

---

## 1. feedparser Basics

### Installation
`feedparser` is already in `pyproject.toml` (version 6.0.12). No additional setup needed. It parses RSS and Atom feeds into a standard dict-like structure.

### Core API
```python
import feedparser

feed = feedparser.parse(url_or_path)
# Returns FeedParserDict (acts like a dict with .get() method)
```

### Feed Structure
```python
feed.get("bozo")         # bool: True if XML is malformed
feed.get("bozo_exception")  # Exception detail if bozo=True
feed.get("entries")      # list[dict]: parsed items/articles
```

### Entry Attributes (from each entry dict)
```python
entry.get("title")              # str
entry.get("link")               # str (article URL)
entry.get("summary")            # str (may contain HTML)
entry.get("published_parsed")   # time.struct_time 9-tuple: (year, month, day, hour, min, sec, weekday, yearday, isdst)
```

### Key Gotcha: Bozo Flag
- **Malformed XML** sets `bozo=True` AND still populates `entries` (partial parse)
- **Empty feeds** may have `bozo=True` and NO entries
- **Correct logic:** Check `if feed.get("bozo") and not feed.get("entries")` — only skip if bozo AND empty

---

## 2. Converting `published_parsed` to ISO 8601

`feedparser` provides timestamps as Python 9-tuples (time.struct_time), not strings. Always convert to ISO 8601 for JSON storage.

### Conversion Pattern
```python
from datetime import datetime, timezone

pp = entry.get("published_parsed")  # (2025, 6, 15, 10, 0, 0, 0, 166, 0)

if pp:
    iso_str = datetime(*pp[:6], tzinfo=timezone.utc).isoformat()
    # Result: "2025-06-15T10:00:00+00:00"

    # Remove "+00:00" suffix for consistency:
    iso_str = iso_str.replace("+00:00", "Z")
    # Result: "2025-06-15T10:00:00Z"
else:
    # Fallback if feed omits publish date
    iso_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
```

---

## 3. Relevance Scoring Design

Scoring is **keyword-count normalized** (not TF-IDF or complex NLP). The design is simple and MVP-appropriate.

### Algorithm
```
1. Define 9 keywords: anthropic, claude, ai, llm, machine learning, safety, alignment, model, gpt
2. Join title + summary into lowercase text
3. Count how many keywords appear (using word boundaries: \bkeyword\b)
4. Divide matches by total keywords (9)
5. Clamp to [0.0, 1.0] and round to 2 decimals
```

### Why Word Boundaries?
**Without:** `"ai"` substring matches `"Rain"` → false positive
**With:** `\bai\b` only matches standalone `"ai"` word → no false matches

```python
import re

# WRONG: "ai" in "Rain" → True
if "ai" in text.lower():  # Catches "rain"

# RIGHT: \bai\b only matches whole word
if re.search(r"\bai\b", text):  # Only matches "ai"
```

### Score Interpretation
- **0.0** = no keywords (irrelevant)
- **0.11** = 1 keyword match out of 9 (borderline)
- **0.44** = 4 keyword matches (high relevance)
- **1.0** = all 9 keywords present (extremely relevant, rare)

### Why This Works
Articles about Claude/Anthropic naturally accumulate keyword density. A weather article never has "anthropic", "claude", or "safety". A LLM safety paper hits 4-5 keywords. Simple, effective, debuggable.

---

## 4. Topic Classification

Topic is inferred from title + source name, not a separate feed field. Used later for UI filtering (optional feature).

### Mapping Strategy
```python
TOPIC_MAP = {
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
```

- First keyword match wins (order matters in iteration)
- Fallback: `"Tech"` if no keywords match
- Maps multiple keywords to fewer topic buckets (Anthropic, AI Safety, AI, Tech)

---

## 5. HTML Stripping in Summaries

Some feeds (especially MIT Tech Review) return raw HTML in the `summary` field instead of plain text.

### Simple Regex Approach
```python
import re

summary = entry.get("summary", "").strip()
summary = re.sub(r"<[^>]+>", "", summary).strip()  # Remove all <...> tags
summary = summary[:500]  # Cap at 500 chars to avoid bloated state
```

**Why regex?**
- Fast for MVP (no external HTML parser needed)
- Catches `<p>`, `<a href="...">`, `<br>`, etc.
- Won't break on malformed HTML (regex is forgiving)

**Limitation:** Doesn't handle entities like `&nbsp;` or `&amp;`. For MVP, acceptable. Post-MVP, use `html.unescape()`.

---

## 6. Deduplication by URL

Multiple feeds often republish the same article. Must deduplicate to avoid duplicates in the final state.

### Implementation
```python
seen_urls: set[str] = set()

for source_name, feed_url in SOURCES:
    feed = feedparser.parse(feed_url)
    for entry in feed.get("entries", []):
        item = parse_entry(entry, source_name)
        if item and item.url not in seen_urls:
            seen_urls.add(item.url)
            all_items.append(item)
```

### Why URL, Not ID?
- **NewsItem schema doesn't have `id` field** (learned hard way!)
- URLs are unique and stable (same article = same URL)
- ID would be artificial, duplicate effort

---

## 7. Graceful Degradation Pattern

The fetcher must **never crash the entire pipeline** if one feed fails. Log errors and keep going.

### Pattern
```python
all_items = []
errors = []

for source_name, url in SOURCES:
    try:
        feed = feedparser.parse(url)
        # ... parse entries ...
    except Exception as e:
        errors.append(f"{source_name}: {e}")  # Log, don't raise
        continue  # Skip to next feed

return NewsState(items=all_items, errors=errors)
```

### Result Semantics
- **items:** Articles successfully parsed
- **errors:** List of failed feeds (plain text, informational, never blocks user)
- **Empty items, non-empty errors:** Feed is down/malformed, user sees no fresh news but app doesn't crash

---

## 8. Hardcoded vs Configurable News Sources

Phase 4 hardcodes 4 news sources as module-level constants:

```python
NEWS_SOURCES: list[tuple[str, str]] = [
    ("Anthropic Blog", "https://www.anthropic.com/rss.xml"),
    ("AI Safety Institute", "https://www.gov.uk/government/organisations/ai-safety-institute.atom"),
    ("MIT Tech Review AI", "https://www.technologyreview.com/topic/artificial-intelligence/feed/"),
    ("Hacker News", "https://news.ycombinator.com/rss"),
]
```

**Why hardcoded?**
- MVP scope: no user feed configuration
- Simpler testing (can patch at module level)
- Fast iteration

**Post-MVP:** Move to `cadence.toml` or database for user customization.

---

## 9. Mocking `feedparser.parse` in Tests

Tests should NOT make real HTTP calls. Mock `feedparser.parse` at the module level where it's imported.

### Correct Patch Target
```python
@patch("scripts.fetch.news_fetcher.feedparser.parse")
def test_something(mock_parse, config):
    mock_feed = MagicMock()
    mock_feed.get.side_effect = lambda k, d=None: {
        "bozo": False,
        "entries": [...]
    }.get(k, d)
    mock_parse.return_value = mock_feed
    # Test runs with mocked parse, no real HTTP
```

### Why `scripts.fetch.news_fetcher.feedparser`?
- `feedparser` is imported at the **module top level** in `news_fetcher.py`
- Patch must target the **location where it's used**, not the original module
- If patched at `feedparser.parse`, the local import finds the already-loaded module in `sys.modules`, which is already patched — works but less explicit

### MagicMock `.get()` Pattern
`feedparser.parse()` returns a FeedParserDict. To mock it:
```python
mock_feed.get.side_effect = lambda k, d=None: dict_data.get(k, d)
```
This makes `.get("bozo")`, `.get("entries")`, etc. return what you want.

---

## 10. dataclasses.replace Pattern for Tests

Test configs need customized vault paths. Use `dataclasses.replace()` to create modified copies.

### Pattern
```python
import dataclasses

def test_write_state(config, vault_path):
    # config.vault_path is hardcoded "/tmp/test_vault"
    # Create a test-specific version:
    test_config = dataclasses.replace(config, vault_path=vault_path)

    fetcher = NewsFetcher(test_config)
    state = NewsState(...)
    fetcher.write_state(state)

    # Now state is written to the actual tmp_path, not hardcoded /tmp/test_vault
    assert (vault_path / ".system" / "state" / "news_state.json").exists()
```

### Why Not Modify In-Place?
- Config is a frozen dataclass (immutable by convention)
- Tests shouldn't modify shared fixtures
- `replace()` creates a new instance, preserving original

---

## 11. Summary: Fetcher Lifecycle

1. **Instantiate** `NewsFetcher(config)` → stores vault path and sources
2. **fetch()** iterates over sources:
   - `feedparser.parse(url)` → dict
   - Check bozo/entries logic
   - Parse each entry → NewsItem (with scoring, topic, summary prep)
   - Deduplicate by URL
   - Sort by relevance descending
   - Cap at `config.news_max_items` (default 10)
   - Return NewsState with items + errors
3. **write_state(state)** → creates vault directory, writes JSON, returns bool
4. **fetch_all()** orchestrates calendar + news, logs results

---

## 12. Key Files & Patterns to Mirror

| Phase | Pattern Source |
|-------|---|
| Imports | `scripts/fetch/calendar_fetcher.py` (absolute imports) |
| write_state | `scripts/fetch/calendar_fetcher.py` (mkdir, write_text, except/return False) |
| fetch_all orchestration | `scripts/fetch/fetch_all.py` (try/except, log counts, all_success flag) |
| Test structure | `tests/test_fetchers.py` (TestCalendarFetcherBasics class) |
| Mock targets | `@patch("scripts.fetch.news_fetcher.feedparser.parse")` |

---

## 13. Test Coverage

10 tests verify:
1. Basic fetch returns valid NewsState
2. Relevance scoring high for AI keywords
3. Relevance scoring zero (word boundary check) for irrelevant text
4. Items sorted by relevance descending
5. Items capped at news_max_items
6. Feed errors logged in state.errors (no crash)
7. Bozo feeds with entries still parsed
8. write_state creates file at correct vault path
9. write_state returns False on PermissionError
10. Duplicate URLs deduplicated across feeds

---

## Troubleshooting

### Tests fail: `'NewsItem' object has no attribute 'id'`
**Issue:** Trying to access `.id` on NewsItem but schema doesn't have that field.
**Solution:** Check schema in `scripts/schemas.py`. NewsItem has: title, source, url, summary, topic, published, relevance. No id field.
**Use:** URL for deduplication, not id.

### Relevance always 0.0 for normal articles
**Issue:** Keywords don't match because of word boundary issues or keyword list is too narrow.
**Solution:** Test with `fetcher._score_relevance("some text", "more text")` directly. Check if `\b` regex is matching as expected.

### Mock not intercepting feedparser.parse
**Issue:** Patch target is wrong or mock isn't being called.
**Solution:** Ensure patch target is `"scripts.fetch.news_fetcher.feedparser.parse"` and that `feedparser` is imported at module top level (not inside a function).

### HTML still in summary
**Issue:** `re.sub(r"<[^>]+>", "", summary)` doesn't catch all cases.
**Solution:** For MVP, acceptable. For robustness, use `html.unescape()` after regex strip, or use `markdownify` library post-MVP.

---

## Next Session

Phase 5 implements the AI agent (`scripts/runtime.py`, `scripts/agent_daily_planner.py`, `scripts/pipeline.py`) to build the complete fetch → context → agent flow. Reference this guide for the fetcher patterns, especially graceful degradation and error logging.

---

**Session Date:** 2025-03-11
**Tests Passing:** 87 (77 existing + 10 new)
**LOC Added:** ~230 (news_fetcher.py + tests)
