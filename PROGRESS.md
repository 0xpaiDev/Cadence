# Cadence — Progress Log

_Updated at the end of each session. Read this first at the start of every session._

## Current Phase
- Phase 0: Complete ✅ (scaffold done)
- Phase 1: Complete ✅ (schemas + test infrastructure)
- Phase 2: Complete ✅ (context builder)
- Phase 3: Complete ✅ (calendar fetcher + Google OAuth)
- Phase 4: Complete ✅ (news fetcher + RSS)
- Phase 5: Complete ✅ (agent + pipeline)
- Phase 6: Ready to start (API server)

## Phase 1 Summary (Session 2)
**Goal:** Implement all Pydantic models, create test infrastructure, write 20+ assertions.

**Completed:**
- `tests/test_schemas.py` — **49 test assertions** (5 test classes: Calendar, News, Task, DayTasks, DayState, Draft, DayDecisions, LoadState)
- `tests/conftest.py` — 9 pytest fixtures (config, vault_path, mock_runtime, sample_calendar_state, sample_news_state, sample_draft, sample_day_state, sample_day_tasks, sample_decisions)
- `tests/fixtures/` — 3 new JSON files (calendar_state_malformed, calendar_state_v0, news_state_malformed)
- Learning material: `learning/phase1-schemas-and-testing.md` — 10 topics, 300+ lines

**Test Results:**
```
49 passed in 0.13s ✅
```

**Key Achievements:**
- All 19 Pydantic models validated
- Mutation methods tested (complete, drop, defer, add)
- Constraint checking verified (relevance bounds 0-1)
- Enum validation confirmed (TaskStatus, DayStatus, TaskSource, DecisionAction)
- Error handling tested (ValidationError on invalid data)
- Schema version tracking documented (not enforced yet)
- Graceful degradation in load_state() confirmed (None on error, not crash)

## Phase 2 Summary (Session 3)
**Goal:** Implement context builder to merge state files into daily_context.md. Write 10+ assertions.

**Completed:**
- `scripts/build_context.py` — Full implementation with 1 public + 3 private functions
  - `build_context_from_vault()` — Main entry point, orchestrates all sections
  - `_render_news_section()` — Formats news as markdown links, sorted by relevance
  - `_render_schedule_section()` — Formats calendar events with times or "All day"
  - `_render_tomorrow_section()` — Tomorrow preview with same formatting
  - Absolute imports fixed: `from scripts.schemas import ...` (no more relative imports)
  - Token budget enforcement: trims news items (lowest relevance) until under budget
  - Graceful degradation: missing/malformed state → skip section, log warning, never crash
- `tests/test_context_builder.py` — **13 test assertions** covering:
  - All 5 sections render with valid state
  - Missing files/state gracefully skipped
  - Malformed JSON handled without crash
  - All-day events shown as "All day:" label
  - Token budget trimming (trims lowest-relevance news)
  - News capped at `config.news_max_items`
  - Tomorrow preview rendering
  - Schedule sorted chronologically
  - News sorted by relevance descending

**Test Results:**
```
70 passed in 0.15s ✅
  - Context builder: 13 new tests ✅
  - Schemas: 49 tests (unchanged) ✅
  - Placeholders: 8 tests ✅
```

**Key Achievements:**
- Context builder merges calendar, news, tasks, training into single markdown doc
- Token budget respected via iterative news trimming (O(n) algorithm, n ≤ 10)
- All date parsing handles ISO 8601 with Z suffix (Python 3.11+ safe)
- Raw markdown files (tasks, training) included verbatim after section heading
- Logging on graceful degradation (helps debugging in production)

## Phase 3 Summary (Session 4)
**Goal:** Implement Google Calendar fetcher with OAuth2. Write 8+ assertions.

**Completed:**
- `scripts/fetch/calendar_fetcher.py` — Full implementation with OAuth2 support
  - `__init__()` loads/refreshes Google OAuth tokens via `google-auth-oauthlib`
  - `fetch_today()` queries Google Calendar API, parses timed + all-day events
  - Tomorrow preview populated with next day's events
  - Graceful degradation: stale state fallback on API errors
  - `write_state()` writes `calendar_state.json` to vault/.system/state/
- `scripts/config.py` — Updated with `google_credentials_path` field
- `tests/conftest.py` — Updated fixtures (all 70 tests still pass)
- `tests/test_fetchers.py` — **8 test assertions** for calendar fetcher:
  - Valid state returned from API
  - All-day events detected + formatted correctly
  - Tomorrow preview populated
  - Missing credentials → empty state fallback
  - API errors → stale state fallback
  - File I/O + error handling
  - Missing title fallback to "(No title)"
- `scripts/fetch/fetch_all.py` — Wired CalendarFetcher with try/except
- Learning material: `learning/phase3-calendar-fetcher.md` — 8 topics, 300+ lines

**Test Results:**
```
77 passed in 0.18s ✅
  - Calendar fetcher: 8 new tests ✅
  - Context builder: 13 tests (unchanged) ✅
  - Schemas: 49 tests (unchanged) ✅
  - Placeholders: 7 tests ✅
```

**Key Achievements:**
- Google Calendar API integration with OAuth2 Installed App Flow
- Event format handling (timed: dateTime vs all-day: date)
- Token auto-refresh via credentials.refresh()
- Graceful degradation on network failures
- Mock testing of Google API without live credentials

## Phase 4 Summary (Session 5)
**Goal:** Implement RSS news fetcher. Write 10+ assertions.

**Completed:**
- `scripts/fetch/news_fetcher.py` — Full RSS feed functionality
  - 4 hardcoded news sources (Anthropic Blog, AI Safety Institute, MIT Tech Review AI, Hacker News)
  - `fetch()` fetches all feeds, deduplicates by URL, scores by relevance
  - Relevance scoring via word-boundary keyword matching (9 keywords: anthropic, claude, ai, llm, etc.)
  - Topic inference from title + source name
  - HTML stripping from summaries (regex approach for malformed HTML)
  - Graceful degradation: bozo flag handling, per-feed try/except, errors list
  - `write_state()` writes `news_state.json` to vault/.system/state/
- `scripts/fetch/fetch_all.py` — Wired NewsFetcher with try/except pattern
- `tests/test_fetchers.py` — **10 test assertions** for news fetcher:
  - Valid state returned with all feeds
  - Relevance scoring (high for AI keywords, zero for irrelevant)
  - Items sorted by relevance descending
  - Items capped at `config.news_max_items`
  - Feed errors logged in errors list (no crash)
  - Bozo feeds with entries still parsed
  - File I/O + error handling
  - Duplicate URLs deduplicated
- Learning material: `learning/phase4-news-fetcher.md` — 10 topics, 300+ lines

**Test Results:**
```
87 passed in 0.22s ✅
  - News fetcher: 10 new tests ✅
  - Calendar fetcher: 8 tests (unchanged) ✅
  - Context builder: 13 tests (unchanged) ✅
  - Schemas: 49 tests (unchanged) ✅
  - Placeholders: 7 tests ✅
```

**Key Achievements:**
- feedparser integration for robust RSS parsing
- Word-boundary keyword matching prevents false positives ("ai" won't match "rain")
- Bozo flag semantics: still parse if entries exist
- URL-based deduplication (NewsItem has no id field)
- HTML stripping for malformed summaries

## Phase 5 Summary (Session 6)
**Goal:** Implement AI agent integration and full pipeline. Write 21+ assertions.

**Completed:**
- `scripts/agent_daily_planner.py` — Draft generation via Claude API
  - `generate_draft()` loads system prompt from vault/.system/config/daily_template.md
  - Calls ClaudeRuntime with context as user message
  - Parses JSON response with `json.loads()`
  - Validates against Draft schema with `Draft.model_validate()`
  - Full error handling: FileNotFoundError, ValueError, ValidationError
  - Graceful: logs all errors, re-raises with context
- `scripts/pipeline.py` — Full fetch → context → draft orchestration
  - `run_pipeline()` loads config, initializes ClaudeRuntime from ANTHROPIC_API_KEY
  - Calls `fetch_all()` (graceful: logs failure, continues)
  - Calls `build_context_from_vault()` and writes daily_context.md
  - Calls `generate_draft()` and writes today_draft.json
  - Writes DayState with status=draft_pending to day_state.json
  - Creates vault directories if missing
  - Returns True on success, False on critical failure
- `/home/shu/vault/.system/config/daily_template.md` — System prompt
  - JSON schema specification (8 top-level fields with examples)
  - Selection rules: 3–5 news by relevance, all events, suggest tasks if light
  - One-line training summary referencing plan
  - Error handling: never incomplete JSON, always all keys
- `tests/test_agent_output.py` — **11 test assertions**:
  - Valid draft parsing, schema validation
  - Invalid JSON/schema/missing template error handling
  - Runtime call verification, field presence checks
  - Error handling (runtime, empty lists)
- `tests/test_pipeline.py` — **10 test assertions**:
  - Success path, all files written (draft, state, context)
  - Graceful degradation (fetch failure continues)
  - API key validation, directory creation
  - Explicit config parameter, context failure
- Learning material: `learning/phase5-agent-and-pipeline.md` — 9 topics, 600+ lines

**Test Results:**
```
106 passed in 0.24s ✅
  - Agent output: 11 new tests ✅
  - Pipeline: 10 new tests ✅
  - News fetcher: 10 tests (unchanged) ✅
  - Calendar fetcher: 8 tests (unchanged) ✅
  - Context builder: 13 tests (unchanged) ✅
  - Schemas: 49 tests (unchanged) ✅
  - Placeholders: 5 tests ✅
```

**Key Achievements:**
- Anthropic Messages API integration with system + user message
- Pydantic validation of untrusted LLM JSON output (catches parse + schema errors)
- Prompt engineering: explicit schema + rules + no-markdown constraints
- MockRuntime testing pattern (deterministic, no API calls, 100x faster)
- Pipeline orchestration: graceful degradation (fetch fails but pipeline continues)
- Full fetch → context → draft pipeline end-to-end functional

## Blockers / Notes
- None. Phases 0–5 complete.
- Next: Phase 6 (API Server) — FastAPI with 6 endpoints (today, negotiate, approve, tasks, status, health)
