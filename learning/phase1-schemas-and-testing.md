# Phase 1: Schemas & Testing — Learning Guide

## What This Phase Is About

Phase 1 establishes the **data layer** of Cadence. We define all data structures (schemas) using Pydantic, then verify they work with comprehensive tests. This is the foundation — all other phases depend on these models being correct.

**Deliverables:**
- 19 Pydantic models in `scripts/schemas.py`
- Test infrastructure (fixtures, conftest) in `tests/conftest.py`
- 49 comprehensive test assertions in `tests/test_schemas.py`
- 3 sample fixture JSON files for testing

---

## Topics You Must Understand

### 1. **Pydantic v2 Data Models**
**Why it matters:** All data in Cadence is validated using Pydantic before being used. Bad data gets caught immediately.

**Key concepts:**
- `BaseModel` — base class for all data structures
- Fields with types: `title: str`, `relevance: float`
- Required vs optional fields: `Optional[str] = None`
- Field constraints: `Field(ge=0.0, le=1.0)` enforces bounds
- Defaults: `all_day: bool = False`
- `model_validate()` — parse untrusted JSON and validate

**Learn:**
- [Pydantic v2 Basics](https://docs.pydantic.dev/latest/)
- Field constraints (ge, le, min_length, max_length)
- Why validation at parse time catches bugs early

### 2. **Python Enums (String Enums)**
**Why it matters:** Enums define fixed sets of valid values. `TaskStatus` can only be pending/completed/dropped/deferred — nothing else.

**Key concepts:**
- `class Status(str, Enum)` — inherit from both str and Enum
- String enums serialize to JSON naturally
- Enums prevent typos and invalid states

**Learn:**
- When to use enums vs strings
- String enums vs int enums
- Comparing enum values

**In Cadence:**
- `TaskStatus` — pending, completed, dropped, deferred
- `TaskSource` — today, carried_over, suggested, negotiation, ad_hoc
- `DayStatus` — draft_pending, negotiating, active, completed
- `DecisionAction` — declined, added, moved, reprioritized, modified, accepted_suggestion

### 3. **State Machines (DayStatus Enum)**
**Why it matters:** A day progresses through specific states. Understanding the state machine prevents invalid transitions.

**State flow:**
```
draft_pending → negotiating → active → completed
```

**Key concepts:**
- Each state has meaning
- Not all transitions are valid
- State changes trigger side effects (writing files, starting tracking)

**Learn:**
- State machine design patterns
- Why explicit states are better than flags

### 4. **pytest Fixtures (conftest.py)**
**Why it matters:** Fixtures provide reusable test data and setup. Without them, every test repeats boilerplate.

**Key concepts:**
- `@pytest.fixture` decorator
- Function-scoped fixtures (run once per test)
- Fixtures as function parameters
- `tmp_path` fixture (pytest built-in for temporary directories)

**Fixtures in conftest.py:**
- `config()` — test Config instance
- `vault_path(tmp_path)` — creates vault directory tree
- `mock_runtime()` — mock agent (for future phases)
- `sample_calendar_state()` — dict with calendar events
- `sample_news_state()` — dict with news items
- `sample_draft()` — dict with complete draft
- `sample_day_state()` — dict with day state
- `sample_day_tasks()` — dict with task list
- `sample_decisions()` — dict with decisions

**Learn:**
- [pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- How fixtures avoid test duplication
- Parametrized fixtures

### 5. **JSON Schema Validation**
**Why it matters:** Data flows in and out as JSON. Pydantic validates JSON against schemas before processing.

**Key concepts:**
- `load_state()` helper function
- Graceful degradation: invalid JSON returns `None`, not crashes
- Schema version tracking (for future migrations)

**In Cadence:**
- `load_state(path, model)` loads JSON, validates, returns model or None
- If file missing → None
- If JSON invalid → None
- If validation fails (bounds, required fields) → None

**Learn:**
- JSON parsing in Python (`json.load()`)
- Pydantic `model_validate()` for untrusted data
- Try/except for graceful error handling

### 6. **Field Constraints & Validation**
**Why it matters:** Constraints catch bad data at parse time, before it causes bugs downstream.

**Key constraints in Cadence:**
- `relevance: float = Field(ge=0.0, le=1.0)` — news relevance bounded 0-1
- `TaskStatus`, `DayStatus`, enums — only valid values
- Required fields with `text: str` — no None unless `Optional[str]`
- Defaults with `Field(default_factory=list)` — empty lists, not shared

**Learn:**
- Pydantic Field validators (ge, le, min_length, max_length)
- `default_factory` vs direct defaults
- Why `default_factory=list` is better than `= []`

### 7. **Type Hints in Python**
**Why it matters:** Type hints document intent and catch errors with mypy before runtime.

**Key concepts:**
- `str`, `int`, `float`, `bool` — basic types
- `list[Item]`, `dict[str, int]` — generic types
- `Optional[str]` — either str or None
- `list[CalendarEvent]` — list of model instances

**Learn:**
- Why type hints matter
- Generic types (list, dict, set)
- Optional and Union types

### 8. **Pytest Assertions & ValidationError**
**Why it matters:** Tests verify behavior. Assertions check if code works as expected.

**Key concepts:**
- `assert value == expected`
- `pytest.raises(ValidationError)` — catch expected exceptions
- Testing both happy path (works) and sad path (fails correctly)

**Test patterns in test_schemas.py:**
- Happy path: valid data parses → assert fields are correct
- Bounds checking: invalid relevance → assert ValidationError
- Required fields: missing title → assert ValidationError
- Method behavior: complete() → assert status changed + timestamp set

**Learn:**
- [pytest Assertions](https://docs.pytest.org/en/stable/assert.html)
- Testing error conditions
- Good test names describe intent, not implementation

### 9. **Python Dataclasses vs Pydantic Models**
**Why it matters:** Know the difference to pick the right tool.

**Key difference:**
- **Dataclasses** — lightweight, no validation, fast
- **Pydantic** — validation, JSON serialization, error messages

**In Cadence:** All external data uses Pydantic (calendar, news, tasks). Internal config uses dataclass (Config in scripts/config.py).

**Learn:**
- When to use dataclasses (internal code only)
- When to use Pydantic (external data, APIs)

### 10. **Fixture JSON Files**
**Why it matters:** Tests need realistic sample data. Fixtures are that data in JSON.

**Files created in Phase 1:**
- `calendar_state.json` — normal state with 2 events
- `calendar_state_empty.json` — valid but no events
- `calendar_state_malformed.json` — missing required field (date)
- `calendar_state_v0.json` — old schema version, still loads (for now)
- `news_state.json` — normal state with 2 items
- `news_state_empty.json` — valid but no items
- `news_state_malformed.json` — relevance=1.5 (out of bounds)
- `sample_draft.json` — complete draft with all sections
- Other fixtures for tasks, decisions, notes

**Learn:**
- How test fixtures work
- Why sample data should be realistic
- Edge cases (empty, malformed, old versions)

---

## Architecture Connection

**Phase 1 fits in the architecture:**
```
VPS Pipeline         API Server         Webapp
   ↓                    ↓                 ↓
calendar_state.json   /api/today       (displays)
news_state.json       ↓
day_state.json     → routes.py uses schemas to validate
tasks.json           ↓
decisions.json    (mutation methods: complete, drop, defer)
```

All data flows through these schemas. Every state file, API request, and response validates against a schema first.

---

## Key Files to Study

1. **`scripts/schemas.py`** (200 lines)
   - All 19 Pydantic models
   - Mutation methods on DayTasks
   - `load_state()` helper
   - Read this to understand data structures

2. **`tests/conftest.py`** (200 lines)
   - Fixtures for config, vault, runtime
   - Sample data for calendar, news, draft, day state, tasks, decisions
   - Read this to see how test data is structured

3. **`tests/test_schemas.py`** (600 lines)
   - 49 test assertions
   - Tests for each model (valid, invalid, constraints, defaults, methods)
   - Read this to understand testing patterns

4. **`tests/fixtures/*.json`** (sample files)
   - Real JSON examples of each state file
   - Read these to see what actual data looks like

---

## Next Phase (Phase 2)

Phase 2 builds the **context builder** — a function that merges all state files (calendar, news, day state) into a single markdown file for the agent to read. It will use these schemas to load and validate the state files.

---

## Self-Study Checklist

- [ ] Read Pydantic docs on BaseModel and Field validators
- [ ] Understand Python enums (str enum vs int enum)
- [ ] Study pytest fixtures and conftest.py pattern
- [ ] Read about JSON schema validation
- [ ] Learn type hints (Optional, list, dict, generic types)
- [ ] Understand when to use pytest.raises()
- [ ] Review all fixture JSON files to see data structure
- [ ] Run `python3 -m pytest tests/test_schemas.py -v` locally
- [ ] Modify a test to fail, see what pytest shows
- [ ] Add a new field to a model and write tests for it

---

## Key Takeaways

✅ **Phase 1 validates:** All data is correct before processing
✅ **Tests as documentation:** Tests show how to use each model
✅ **Graceful degradation:** Invalid data returns None, doesn't crash
✅ **Enums prevent bugs:** Fixed states/sources prevent typos
✅ **Fixtures avoid duplication:** Test data centralized in conftest
✅ **Pydantic catches errors:** Bounds, required fields caught at parse time

---

## Resources

- [Pydantic v2 Documentation](https://docs.pydantic.dev/latest/)
- [pytest Documentation](https://docs.pytest.org/)
- [Python Enums](https://docs.python.org/3/library/enum.html)
- [Type Hints in Python](https://docs.python.org/3/library/typing.html)
- [Python Data Model (Dunder Methods)](https://docs.python.org/3/reference/datamodel.html)
