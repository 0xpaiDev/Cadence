# Phase 5: Agent Integration & Pipeline Orchestration

## Overview

Phase 5 introduces the AI agent into the pipeline: load a system prompt, call the Claude API, parse structured JSON responses, and orchestrate the fetch → context → draft workflow. This phase teaches patterns for working with LLMs reliably in production code.

---

## Topic 1: Abstract Base Classes (ABC) — Swappable Runtime Pattern

### What is an ABC?

An Abstract Base Class defines a contract that subclasses must implement. It enforces an interface without providing implementation.

```python
from abc import ABC, abstractmethod

class AgentRuntime(ABC):
    """Contract for any AI agent runtime."""

    @abstractmethod
    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        """Subclasses must implement this."""
        pass
```

### Why Use This Pattern?

The ABC pattern lets you:
- **Swap implementations at runtime** — ClaudeRuntime, MockRuntime, GPTRuntime, etc.
- **Write testable code** — Mock the interface without API calls
- **Extend safely** — Add new runtimes without breaking existing code

### Cadence Example

```python
# Define the contract
class AgentRuntime(ABC):
    @abstractmethod
    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        pass

# Production implementation
class ClaudeRuntime(AgentRuntime):
    def __init__(self, model: str, api_key: str):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)

    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text

# Test implementation
class MockRuntime(AgentRuntime):
    def __init__(self, response: str):
        self.response = response

    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        return self.response
```

### Key Pattern Rules

1. **Abstract methods define the interface** — what all subclasses must implement
2. **Concrete classes implement the contract** — ClaudeRuntime, MockRuntime, etc.
3. **Type hints use the ABC** — `runtime: AgentRuntime` accepts any implementation
4. **Tests use MockRuntime** — avoid network calls, control outputs deterministically

---

## Topic 2: Anthropic Messages API

### Basic API Call

```python
from anthropic import Anthropic

client = Anthropic(api_key="sk-ant-...")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1500,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)

# Extract text response
text = response.content[0].text
```

### Key Concepts

| Concept | Purpose |
|---------|---------|
| `model` | Which Claude version (e.g., "claude-sonnet-4-6") |
| `max_tokens` | Maximum length of response (budget) |
| `system` | System prompt (defines agent behavior) |
| `messages[]` | Conversation history (role: "user" or "assistant") |
| `response.content[0].text` | The actual response string |

### Error Handling

```python
try:
    response = client.messages.create(...)
    return response.content[0].text
except ImportError:
    raise RuntimeError("anthropic package not installed")
except Exception as e:
    logger.error(f"API call failed: {e}")
    raise RuntimeError(f"Agent call failed: {e}") from e
```

**Key pattern:** Catch errors, log them, re-raise as your own exception type.

---

## Topic 3: Prompt Engineering for Structured JSON Output

### The Challenge

Large language models (LLMs) naturally produce prose. To get machine-parseable JSON, you must:
- **Explicitly request JSON** — "return JSON only"
- **Specify exact schema** — show the fields and types
- **Prevent markdown** — no code blocks, no backticks
- **Provide examples** — show what good output looks like

### Cadence's Approach (daily_template.md)

```markdown
You are a daily intelligence assistant.

## Output Format
Return ONLY valid JSON, no markdown, no explanation.

## Schema
Your JSON must match this exact structure:

{
  "date": "YYYY-MM-DD",
  "schema_version": 1,
  "generated_at": "ISO8601 timestamp",
  "news": [...],
  "schedule": [...],
  "training": {"summary": "...", "plan_reference": null},
  "agent_suggestions": [...]
}

## Rules
- Select 3–5 highest-relevance news items
- Include all calendar events
- If fewer than 3 tasks, suggest 1–2 more
```

### Why This Works

1. **"Return JSON only"** — removes markdown fluff
2. **Full schema** — field names, types, example values
3. **Rules section** — constraints on content (3–5 news, all events, etc.)
4. **"Never output..."** — error cases explicitly forbidden

### Common Pitfalls

| Mistake | Fix |
|---------|-----|
| No schema spec | Provide exact JSON structure |
| Allow markdown | Request "JSON only, no backticks" |
| Ambiguous rules | "Include ALL events, not just important ones" |
| No examples | Show a valid JSON output in the prompt |

---

## Topic 4: Validating LLM Output with Pydantic

### The Problem

LLM responses are strings. They might be:
- Invalid JSON (missing quote, stray comma)
- Valid JSON but wrong schema (missing field, wrong type)
- Right schema but wrong values (impossible enum, future date)

You must validate before trusting the data.

### Pydantic Validation Pattern

```python
import json
from pydantic import ValidationError
from scripts.schemas import Draft

# 1. Parse string as JSON
try:
    parsed = json.loads(response)
except json.JSONDecodeError as e:
    logger.error(f"Not valid JSON: {e}")
    raise ValueError(f"Invalid JSON: {e}")

# 2. Validate against schema
try:
    draft = Draft.model_validate(parsed)
except ValidationError as e:
    logger.error(f"Schema mismatch: {e}")
    raise ValueError(f"Invalid draft: {e}")

# 3. Return as dict
return draft.model_dump()
```

### What Gets Validated?

The `Draft` Pydantic model validates:
- **Required fields present** — date, schema_version, generated_at, news, schedule, tasks, training, agent_suggestions
- **Field types correct** — news is list[DraftNewsItem], not string or int
- **Enum values valid** — TaskStatus is "pending", "completed", "dropped", or "deferred" (not "unknown")
- **Nested models** — each NewsItem has title, source, url, etc.

### Error Message Example

```
ValidationError: 3 validation errors
field_required: Field required [type=missing, input_value={...}]
  date
type_error.integer: value is not a valid integer [type=type_error.integer]
  schema_version
```

---

## Topic 5: MockRuntime Testing Pattern

### Why Mock?

Every test that calls the real API:
- ❌ Costs money
- ❌ Is slow (100+ ms per call)
- ❌ Depends on network/API availability
- ❌ Is non-deterministic (LLM output varies)

### MockRuntime Solution

```python
class MockRuntime(AgentRuntime):
    """Fixed response for testing."""

    def __init__(self, response: str = "Mock response"):
        self.response = response

    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        return self.response  # Always return the same string
```

### Using in Tests

```python
def test_generate_draft_returns_dict():
    # 1. Create mock with fixed response
    sample_draft = {
        "schema_version": 1,
        "date": "2025-06-15",
        "generated_at": "...",
        ...
    }
    runtime = MockRuntime(response=json.dumps(sample_draft))

    # 2. Call your code
    result = generate_draft("test context", config, runtime)

    # 3. Assert on deterministic result
    assert result["date"] == "2025-06-15"
```

### Advanced: Spying on Runtime Calls

```python
from unittest.mock import Mock

# Create a mock that records what was called
runtime = Mock(spec=AgentRuntime)
runtime.call.return_value = json.dumps(sample_draft)

# Call your code
generate_draft("test context", config, runtime)

# Assert runtime was called correctly
runtime.call.assert_called_once()
call_args = runtime.call.call_args
assert call_args[1]["user_message"] == "test context"
```

---

## Topic 6: Pipeline Orchestration & Graceful Degradation

### Pattern: Catch-and-Continue

Your pipeline has multiple steps. If one fails (e.g., API unreachable), you have two choices:

**Fail-fast:** Stop immediately
```python
fetch_all(config)      # ← if this fails, pipeline stops
build_context(...)     # Never reached
generate_draft(...)    # Never reached
```

**Graceful degradation:** Log the error, continue
```python
try:
    fetch_all(config)
except Exception as e:
    logger.warning(f"Fetch failed (continuing): {e}")
    # Don't return or raise — continue

build_context(...)     # Runs even if fetch failed
generate_draft(...)    # Runs with stale/empty data
```

### Cadence's Approach

**Critical steps** (fail if they fail):
- Building context from vault files → errors are logged, pipeline aborts
- Generating draft via agent → if JSON invalid or schema mismatch, pipeline aborts

**Optional steps** (log but don't fail):
- Fetching news/calendar → if API unreachable, continue with cached data
- Writing files → if filesystem issue, log warning (but this should be rare)

```python
def run_pipeline(config: Optional[Config] = None) -> bool:
    try:
        # Step 1: Initialize
        runtime = ClaudeRuntime(...)

        # Step 2: Fetch (graceful)
        try:
            fetch_all(config)
        except Exception as e:
            logger.warning(f"Fetch failed (continuing): {e}")

        # Step 3: Context (critical)
        context = build_context_from_vault(vault, config)

        # Step 4: Draft (critical)
        draft = generate_draft(context, config, runtime)

        # Step 5: Write (should succeed if dirs exist)
        write_draft_file(...)
        write_state_file(...)

        return True

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return False
```

### Decision Rules

| Step | Fail-Fast? | Why |
|------|------------|-----|
| Fetch news/calendar | No | Cached data from yesterday works |
| Build context | Yes | Need context to call agent |
| Generate draft | Yes | Invalid draft = unusable plan |
| Write files | Yes | If filesystem fails, alert admin |

---

## Topic 7: Using dataclasses.replace() for Test Configs

### The Problem

Your `Config` dataclass has 10+ fields:
```python
config = Config(
    vault_path="...",
    google_credentials_path="...",
    cron_hour=6,
    ... 9 more fields
)
```

For each test, you might want to override just ONE field:
```python
test_config = Config(
    vault_path="/tmp/test_vault",  # ← Only this changes
    google_credentials_path="...",
    cron_hour=6,
    ... (copy all others)
)
```

This gets tedious and error-prone.

### Solution: dataclasses.replace()

```python
from dataclasses import replace

# Original config (from fixture)
config = Config(vault_path="/home/shu/vault", cron_hour=6, ...)

# Create variant with one field changed
test_config = replace(config, vault_path="/tmp/test_vault")

# All other fields inherited from original
```

### Used in Phase 4 (News Fetcher Tests)

```python
def test_news_fetcher_with_custom_vault(config):
    test_config = replace(config, vault_path="/tmp/custom_vault")
    fetcher = NewsFetcher(test_config)
    ...
```

---

## Integration Example: Full Pipeline Call

```python
def main():
    """Example: run full pipeline with agent integration."""
    config = load_config()

    # Pipeline internally uses:
    # 1. ClaudeRuntime — calls Claude API with daily_template.md
    # 2. JSON parsing & Pydantic validation — validates Draft schema
    # 3. Graceful degradation — fetch fails, but draft still generated
    # 4. File I/O — writes context, draft, day_state

    success = run_pipeline(config)

    if success:
        print("Draft ready for negotiation")
        draft = load_draft_from_vault(config.vault_path)
        print(f"Tasks: {len(draft['tasks'])}")
        print(f"News items: {len(draft['news'])}")
    else:
        print("Pipeline failed — check logs")
```

---

## Testing Strategies Summary

| Scenario | How to Test | Tool |
|----------|-------------|------|
| Agent integration | MockRuntime with sample JSON | conftest.py fixtures |
| JSON parsing | Feed garbage JSON, expect ValueError | pytest + json module |
| Schema validation | Wrong fields, expect ValidationError | Pydantic + pytest |
| Pipeline success | Patch all external calls, assert files written | unittest.mock |
| Graceful failure | Patch fetch_all to raise, assert draft still written | unittest.mock |

---

## Key Learnings

1. **ABC pattern** — design for swappable implementations from the start
2. **Prompt engineering** — explicit schema + rules + no markdown
3. **Pydantic validation** — never trust external JSON, validate before use
4. **MockRuntime** — speeds up tests 100x, makes them deterministic
5. **Graceful degradation** — optional steps log and continue, critical steps fail fast
6. **dataclasses.replace()** — one-liner config variants for tests

---

## References

- [Anthropic Messages API](https://docs.anthropic.com/messages/api/messages-API)
- [Pydantic Validation](https://docs.pydantic.dev/)
- [Python ABC Module](https://docs.python.org/3/library/abc.html)
- Cadence code: `scripts/runtime.py`, `scripts/agent_daily_planner.py`, `scripts/pipeline.py`
