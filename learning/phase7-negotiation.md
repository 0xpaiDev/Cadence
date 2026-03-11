# Phase 7: Negotiation Session

## Overview

Phase 7 implements interactive negotiation — users can provide feedback on the draft plan, and an AI agent responds with mutations (add/drop/reprioritize tasks). The agent's response format includes both human-readable text and a `<changes>` XML block with structured JSON actions.

---

## Core Concepts

### 1. Multi-Turn Conversation Over Stateless HTTP

**Problem:** The API is stateless (each POST is independent), but negotiation requires conversation history. How do we fold multi-turn state into single-turn runtime calls?

**Solution:** Serialize history to JSON in the vault between requests.

```
Request 1: User says "drop standup"
  → Load prior history (empty)
  → Call agent with draft + context
  → Record history: [user msg, agent response]
  → Write to negotiation_history.json

Request 2: User says "add 30 min focus block"
  → Load prior history from negotiation_history.json
  → Call agent with history + new message
  → Append to history
  → Overwrite negotiation_history.json
```

**File:** `api/routes.py` POST /api/negotiate (lines 195–245)

---

### 2. Structured Output from LLM via XML Blocks

The agent responds with plain text + a `<changes>...</changes>` XML block:

```
Agent response:
"Understood. That gives you 2 hours to focus on the brief.

<changes>
{"action": "drop_task", "task_id": "t4"}
{"action": "add_task", "text": "Deep focus: marketing brief", "priority": "high"}
</changes>
```

**Why XML?**
- Easy to regex parse
- Clearly separates human text from machine-readable actions
- Doesn't conflict with JSON field values

**Regex to extract:**
```python
match = re.search(r"<changes>(.*?)</changes>", response, re.DOTALL)
block_content = match.group(1).strip()
```

**File:** `api/negotiation.py`, `_extract_changes()` method

---

### 3. Agent Response Post-Processing

Two steps:

1. **Strip markup for display:** Remove `<changes>...</changes>` before showing to user.
   ```python
   display_msg = re.sub(r"<changes>.*?</changes>", "", response, flags=re.DOTALL).strip()
   ```

2. **Extract and parse actions:** Parse JSON lines inside the block.
   ```python
   for line in block_content.split("\n"):
       action = json.loads(line)  # One action per line
       actions.append(action)
   ```

**Key insight:** Graceful degradation — if a line is malformed JSON, log a warning and skip it (don't fail the whole request).

**File:** `api/negotiation.py`, `_extract_changes()` method

---

### 4. Draft Mutation Patterns on Plain Dicts

The draft arrives as a plain `dict` (not a Pydantic model) so mutations can be applied directly:

```python
# Drop task
self.draft["tasks"] = [t for t in self.draft["tasks"] if t["id"] != task_id]

# Add task
new_task = {
    "id": f"neg_{uuid.uuid4().hex[:8]}",
    "text": text,
    "source": "negotiation",  # Always mark negotiation source
    "priority": priority,
    "status": "pending"
}
self.draft["tasks"].append(new_task)

# Reprioritize
for task in self.draft["tasks"]:
    if task["id"] == task_id:
        task["priority"] = priority
        break
```

**Why plain dict?**
- Faster iteration than Pydantic validation
- Easier to mutate (no `.model_copy()` or re-validation needed)
- Converted back to dict for JSON serialization anyway

**File:** `api/negotiation.py`, `_apply_mutations()` method

---

### 5. MockRuntime for Testing Agent-Dependent Code

All negotiation tests use `MockRuntime` (deterministic responses, no API calls):

```python
def test_exchange_returns_correct_keys(self, sample_draft):
    runtime = MockRuntime(
        response="Understood.\n<changes>\n{}\n</changes>"
    )
    session = NegotiationSession(
        draft=sample_draft, context="Context", runtime=runtime
    )

    result = session.exchange("Drop the standup")

    assert "message" in result
    assert "draft" in result
    assert "decisions" in result
```

**Benefits:**
- Tests run in <1s (no API latency)
- No Anthropic API key needed
- Responses are predictable (same input → same output)
- Can test error cases (e.g., malformed JSON in changes block)

**File:** `tests/test_negotiation.py`, all 17 test methods

---

### 6. Prompt Engineering for Command-Following Agents

The negotiation template (`vault/.system/config/negotiation_template.md`) uses several techniques to ensure the agent follows instructions:

**1. Clear role definition:**
```
Your role:
- Accept the user's feedback immediately, without pushback or arguments
- Acknowledge the request concisely
- ...
```

**2. Format specification with examples:**
```
## Structured Changes
You MUST respond with the following format:

Plain text response first (acknowledge, adjust, suggest):
```
Understood. Dropped the team sync. That frees up 2pm–3pm to focus on the marketing brief.
```

Then, a `<changes>` block...

## Example
**User says:** "Drop the standup, it's just status updates we can async."

**Your response:**
```
Got it—dropping the standup. That keeps your morning focused on deep work...

<changes>
{"action": "drop_task", "task_id": "t4"}
</changes>
```
```

**3. Constraints on length and content:**
```
- Keep responses to 2–4 sentences max
- Provide 1 suggestion only (if time allows)
```

**4. Fallback for edge cases:**
```
- If the user declines an action (e.g., "never mind"), include an empty `<changes></changes>` block.
- Always include the `<changes>` block, even if empty.
```

**Key takeaway:** Examples trump prose. Show, don't tell.

**File:** `vault/.system/config/negotiation_template.md`

---

## Architecture: NegotiationSession Class

### Constructor

```python
def __init__(
    self,
    draft: dict,
    context: str,
    runtime: AgentRuntime,
    vault_path: str = "",
    history: list[dict] | None = None,
):
```

- **draft:** Mutable dict representing the current plan
- **context:** Markdown string (from `daily_context.md`)
- **runtime:** Agent runtime (ClaudeRuntime or MockRuntime)
- **vault_path:** Path to vault (needed to load negotiation template)
- **history:** Prior conversation turns (loaded from `negotiation_history.json`)

### Public API

**`exchange(user_message: str) -> dict`**
- Main entry point for one round of negotiation
- Returns `{"message": str, "draft": dict, "decisions": list}`
- Updates `self.history` and `self.draft`

### Private Methods

**`_build_system_prompt() -> str`**
- Loads `negotiation_template.md` from vault
- Raises `FileNotFoundError` if missing or no vault_path set

**`_build_user_message(user_message: str) -> str`**
- First turn: includes draft JSON + context + new message
- Subsequent turns: includes conversation history + new message
- Folds multi-turn state into single-turn runtime call

**`_extract_changes(response: str) -> list[dict]`**
- Regex: `r"<changes>(.*?)</changes>"`
- Parses JSON lines inside block
- Gracefully skips malformed JSON
- Returns `[]` if no block or empty block

**`_apply_mutations(actions: list[dict]) -> None`**
- Supports: `drop_task`, `add_task`, `reprioritize_task`
- Modifies `self.draft` in place
- Logs warnings on unknown actions

---

## File Layout

```
api/
  negotiation.py           # NegotiationSession class (140 lines)
  routes.py                # Updated POST /api/negotiate (55 lines)

vault/.system/config/
  negotiation_template.md  # System prompt for negotiation agent

tests/
  test_negotiation.py      # 17 test methods, all using MockRuntime

learning/
  phase7-negotiation.md    # This file
```

---

## Testing Strategy

### Unit Tests (Class Methods)

All use MockRuntime — no API calls.

1. **Basic flow:** `exchange()` returns correct keys
2. **Parsing:** `_extract_changes()` handles valid/empty/malformed blocks
3. **Mutations:** Each action type (drop/add/reprioritize) works correctly
4. **History:** Grows as expected; subsequent turns format correctly
5. **Template loading:** Loads from vault; raises on missing

### Integration Tests (Endpoint)

1. **Happy path:** POST /api/negotiate returns 200 + response dict
2. **Error cases:** Returns 404 if no draft, 409 if already approved
3. **Persistence:** History is written to vault

---

## Common Patterns

### Pattern 1: Graceful Error Handling in Parsing

```python
for line in block_content.split("\n"):
    try:
        action = json.loads(line)
        actions.append(action)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse: {line}. Error: {e}")
        continue  # Skip malformed line, don't fail
```

**Use case:** Negotiation agent may occasionally produce a malformed JSON line. We log it (so developers see the issue) but don't crash the request.

### Pattern 2: First-Turn vs. Subsequent-Turn Behavior

```python
if not self.history:
    # First turn: include draft + context
    return f"## Current Draft\n{draft_json}\n\n## Daily Context\n{context}\n\n{user_message}"
else:
    # Subsequent turns: include history only
    return f"{history_text}\n\nUser: {user_message}"
```

**Why?** On first turn, agent needs full context (draft + calendar + tasks). On subsequent turns, the context is already in the conversation history, so we don't repeat it.

### Pattern 3: Deterministic Task ID Generation

```python
"id": f"neg_{uuid.uuid4().hex[:8]}"
```

**Why?** Tasks added during negotiation need unique IDs. We prefix with `neg_` for debuggability ("this came from negotiation").

---

## Integration with REST API

### Workflow

```
User opens webapp, sees draft
   ↓
User enters feedback: "Drop the standup"
   ↓
POST /api/negotiate {"text": "Drop the standup"}
   ↓
Route loads draft, context, history from vault
   ↓
Create NegotiationSession
   ↓
session.exchange("Drop the standup")
   ↓
Agent responds with text + <changes> block
   ↓
Mutations applied, history recorded
   ↓
Updated draft + history written back to vault
   ↓
Return {"message": "...", "draft": {...updated...}, "decisions": [...]}
   ↓
Webapp displays agent response, refreshes draft
```

**State management:** The draft is always authoritative (stored on disk). History is a side-channel for conversation continuity. If history is corrupted, the next /api/negotiate call starts fresh (history=empty).

---

## Advanced Topics

### Extending to New Action Types

To add a new mutation (e.g., `reorder_task`):

1. Update `negotiation_template.md` with the new action type
2. Add handler in `_apply_mutations()`:
   ```python
   elif action_type == "reorder_task":
       # Implement reordering logic
   ```
3. Add test in `test_negotiation.py`

### Improving Agent Responses

If the agent produces too-long responses or ignores constraints:

1. Review `negotiation_template.md` — tighten the rules
2. Add more examples to the template
3. Reduce `max_tokens` in `session.exchange()` (currently 600)
4. Test with `MockRuntime(response=...)` to verify new constraints work

### Handling Ambiguous User Input

If a user says "drop it" but there are multiple candidates:

Current behavior: Agent sees the full draft and history, so it can infer which task. If it can't, it should ask for clarification (in plain text, no changes block).

Better approach (post-MVP): Allow agent to return a `request_clarification` action.

---

## Debugging

### View negotiation history

```bash
cat /home/shu/vault/.system/state/negotiation_history.json | jq .
```

### View latest draft

```bash
cat /home/shu/vault/.system/drafts/today_draft.json | jq .
```

### Test agent behavior without API

```python
from scripts.runtime import MockRuntime
from api.negotiation import NegotiationSession

session = NegotiationSession(
    draft={...},
    context="...",
    runtime=MockRuntime(response='Understood.\n<changes>\n{"action": "drop_task", "task_id": "t1"}\n</changes>'),
    vault_path="/home/shu/vault"
)
result = session.exchange("Drop the standup")
print(result)
```

---

## Summary

Phase 7 introduces interactive negotiation with structured agent output. Key techniques:

1. **History serialization** — multi-turn conversation over stateless HTTP
2. **XML block parsing** — cleanly separate text and structured data
3. **Graceful mutation** — plain dicts allow fast in-place edits
4. **Prompt engineering** — examples > prose, constraints on length
5. **MockRuntime testing** — deterministic tests without API latency

Total new code: ~140 lines in `NegotiationSession`, ~55 lines in route handler, 17 test methods, system prompt template.
