"""Tests for negotiation session."""

import json
from pathlib import Path

import pytest

from api.negotiation import NegotiationSession
from scripts.runtime import MockRuntime


class TestNegotiationSession:
    """Test NegotiationSession class."""

    def test_exchange_returns_correct_keys(self, sample_draft, tmp_path):
        """exchange() returns dict with message, draft, decisions keys."""
        vault = tmp_path / "vault"
        config_dir = vault / ".system" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "negotiation_template.md").write_text("Test template")

        runtime = MockRuntime(
            response="Understood.\n<changes>\n{}\n</changes>"
        )
        session = NegotiationSession(
            draft=sample_draft,
            context="Context",
            runtime=runtime,
            vault_path=str(vault),
        )

        result = session.exchange("Drop the standup")

        assert "message" in result
        assert "draft" in result
        assert "decisions" in result

    def test_extract_changes_parses_valid_block(self, sample_draft):
        """_extract_changes parses valid <changes> block into action list."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime
        )

        response = (
            "Got it.\n"
            "<changes>\n"
            '{"action": "drop_task", "task_id": "t1"}\n'
            '{"action": "add_task", "text": "New task", "priority": "high"}\n'
            "</changes>"
        )

        changes = session._extract_changes(response)

        assert len(changes) == 2
        assert changes[0]["action"] == "drop_task"
        assert changes[1]["action"] == "add_task"

    def test_extract_changes_returns_empty_list_when_no_block(self, sample_draft):
        """_extract_changes returns [] when no <changes> block present."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime
        )

        changes = session._extract_changes("No changes needed.")

        assert changes == []

    def test_extract_changes_returns_empty_list_on_malformed_json(
        self, sample_draft
    ):
        """_extract_changes gracefully handles malformed JSON lines."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime
        )

        response = (
            "<changes>\n"
            '{"action": "drop_task", "task_id": "t1"}\n'
            'invalid json here\n'
            '{"action": "add_task", "text": "Task", "priority": "high"}\n'
            "</changes>"
        )

        changes = session._extract_changes(response)

        # Only valid JSON lines are parsed
        assert len(changes) == 2
        assert changes[0]["action"] == "drop_task"
        assert changes[1]["action"] == "add_task"

    def test_apply_mutations_drop_task(self, sample_draft):
        """_apply_mutations with drop_task removes task from draft."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime
        )

        original_count = len(session.draft["tasks"])
        actions = [{"action": "drop_task", "task_id": "t1_1234567890"}]

        session._apply_mutations(actions)

        assert len(session.draft["tasks"]) == original_count - 1
        assert not any(t["id"] == "t1_1234567890" for t in session.draft["tasks"])

    def test_apply_mutations_add_task(self, sample_draft):
        """_apply_mutations with add_task appends task with negotiation source."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime
        )

        original_count = len(session.draft["tasks"])
        actions = [{"action": "add_task", "text": "New task", "priority": "high"}]

        session._apply_mutations(actions)

        assert len(session.draft["tasks"]) == original_count + 1
        new_task = session.draft["tasks"][-1]
        assert new_task["text"] == "New task"
        assert new_task["priority"] == "high"
        assert new_task["source"] == "negotiation"
        assert new_task["status"] == "pending"

    def test_apply_mutations_reprioritize_task(self, sample_draft):
        """_apply_mutations with reprioritize_task changes task priority."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime
        )

        actions = [
            {"action": "reprioritize_task", "task_id": "t1_1234567890", "priority": "low"}
        ]

        session._apply_mutations(actions)

        task = next(
            t for t in session.draft["tasks"] if t["id"] == "t1_1234567890"
        )
        assert task["priority"] == "low"

    def test_exchange_strips_changes_from_message(self, sample_draft, tmp_path):
        """exchange() strips <changes> block from returned message."""
        vault = tmp_path / "vault"
        config_dir = vault / ".system" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "negotiation_template.md").write_text("Test template")

        runtime = MockRuntime(
            response="Understood, dropped it.\n<changes>\n{}\n</changes>"
        )
        session = NegotiationSession(
            draft=sample_draft,
            context="",
            runtime=runtime,
            vault_path=str(vault),
        )

        result = session.exchange("Drop task")

        assert "<changes>" not in result["message"]
        assert "</changes>" not in result["message"]
        assert "Understood, dropped it." in result["message"]

    def test_history_grows_after_exchange(self, sample_draft, tmp_path):
        """history list grows by 2 entries (user + assistant) after exchange."""
        vault = tmp_path / "vault"
        config_dir = vault / ".system" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "negotiation_template.md").write_text("Test template")

        runtime = MockRuntime(
            response="Acknowledged.\n<changes>\n{}\n</changes>"
        )
        session = NegotiationSession(
            draft=sample_draft,
            context="",
            runtime=runtime,
            vault_path=str(vault),
        )

        assert len(session.history) == 0

        session.exchange("First request")

        assert len(session.history) == 2
        assert session.history[0]["role"] == "user"
        assert session.history[1]["role"] == "assistant"

        session.exchange("Second request")

        assert len(session.history) == 4

    def test_build_user_message_first_turn(self, sample_draft):
        """_build_user_message includes draft and context on first turn."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="Daily context", runtime=runtime
        )

        msg = session._build_user_message("User request")

        assert "Current Draft" in msg
        assert "Daily Context" in msg
        assert "User Request" in msg
        assert "Daily context" in msg

    def test_build_user_message_subsequent_turns(self, sample_draft):
        """_build_user_message includes history on subsequent turns."""
        runtime = MockRuntime(response="")
        history = [
            {"role": "user", "content": "First request"},
            {"role": "assistant", "content": "First response"},
        ]
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime, history=history
        )

        msg = session._build_user_message("Second request")

        assert "First request" in msg
        assert "First response" in msg
        assert "Second request" in msg
        assert "Current Draft" not in msg  # Should not repeat draft

    def test_build_system_prompt_loads_from_vault(self, sample_draft, tmp_path):
        """_build_system_prompt loads template from vault."""
        vault = tmp_path / "vault"
        config_dir = vault / ".system" / "config"
        config_dir.mkdir(parents=True)

        template_path = config_dir / "negotiation_template.md"
        template_path.write_text("Test template content")

        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft,
            context="",
            runtime=runtime,
            vault_path=str(vault),
        )

        prompt = session._build_system_prompt()

        assert prompt == "Test template content"

    def test_build_system_prompt_raises_if_missing(self, sample_draft, tmp_path):
        """_build_system_prompt raises FileNotFoundError if template missing."""
        vault = tmp_path / "vault"
        (vault / ".system" / "config").mkdir(parents=True)

        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft,
            context="",
            runtime=runtime,
            vault_path=str(vault),
        )

        with pytest.raises(FileNotFoundError):
            session._build_system_prompt()

    def test_build_system_prompt_raises_if_no_vault_path(self, sample_draft):
        """_build_system_prompt raises FileNotFoundError if vault_path not set."""
        runtime = MockRuntime(response="")
        session = NegotiationSession(
            draft=sample_draft, context="", runtime=runtime, vault_path=""
        )

        with pytest.raises(FileNotFoundError):
            session._build_system_prompt()


class TestNegotiateEndpoint:
    """Test POST /api/negotiate endpoint."""

    def test_negotiate_returns_200_with_response(
        self, api_client, vault_path, sample_draft, sample_day_state, monkeypatch
    ):
        """POST /api/negotiate returns 200 with message, draft, decisions."""
        # Setup vault with draft and state
        draft_path = Path(vault_path) / ".system" / "drafts" / "today_draft.json"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(json.dumps(sample_draft))

        state_path = Path(vault_path) / ".system" / "state" / "day_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(sample_day_state))

        context_path = Path(vault_path) / ".system" / "context" / "daily_context.md"
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text("Daily context text")

        # Setup negotiation template
        template_path = (
            Path(vault_path) / ".system" / "config" / "negotiation_template.md"
        )
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(
            "You are a negotiation agent.\nAcknowledged.\n<changes>\n{}\n</changes>"
        )

        # Mock ClaudeRuntime to use MockRuntime instead
        from api import routes as routes_module
        from scripts.runtime import MockRuntime

        original_claude = routes_module.ClaudeRuntime

        def mock_claude_init(self, model, api_key):
            self.model = model
            self.api_key = api_key
            self._mock = MockRuntime(response="Acknowledged.\n<changes>\n{}\n</changes>")

        def mock_claude_call(self, system_prompt, user_message, max_tokens):
            return self._mock.call(system_prompt, user_message, max_tokens)

        monkeypatch.setattr(original_claude, "__init__", mock_claude_init)
        monkeypatch.setattr(original_claude, "call", mock_claude_call)

        response = api_client.post(
            "/api/negotiate",
            json={"text": "Drop the first task"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "draft" in data
        assert "decisions" in data

    def test_negotiate_with_no_draft_returns_404(
        self, api_client, vault_path, sample_day_state, monkeypatch
    ):
        """POST /api/negotiate returns 404 if no draft exists."""
        state_path = Path(vault_path) / ".system" / "state" / "day_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(sample_day_state))

        # Mock ClaudeRuntime (though route should error before calling it)
        from api import routes as routes_module
        from scripts.runtime import MockRuntime

        original_claude = routes_module.ClaudeRuntime

        def mock_claude_init(self, model, api_key):
            self.model = model
            self.api_key = api_key
            self._mock = MockRuntime(response="OK")

        monkeypatch.setattr(original_claude, "__init__", mock_claude_init)

        response = api_client.post(
            "/api/negotiate",
            json={"text": "Drop the first task"},
        )

        assert response.status_code == 404

    def test_negotiate_persists_history(
        self, api_client, vault_path, sample_draft, sample_day_state, monkeypatch
    ):
        """POST /api/negotiate persists conversation history to vault."""
        # Setup vault
        draft_path = Path(vault_path) / ".system" / "drafts" / "today_draft.json"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(json.dumps(sample_draft))

        state_path = Path(vault_path) / ".system" / "state" / "day_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(sample_day_state))

        context_path = Path(vault_path) / ".system" / "context" / "daily_context.md"
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text("Daily context")

        template_path = (
            Path(vault_path) / ".system" / "config" / "negotiation_template.md"
        )
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(
            "You are a negotiation agent.\nOK.\n<changes>\n{}\n</changes>"
        )

        # Mock ClaudeRuntime
        from api import routes as routes_module
        from scripts.runtime import MockRuntime

        original_claude = routes_module.ClaudeRuntime

        def mock_claude_init(self, model, api_key):
            self.model = model
            self.api_key = api_key
            self._mock = MockRuntime(response="OK.\n<changes>\n{}\n</changes>")

        def mock_claude_call(self, system_prompt, user_message, max_tokens):
            return self._mock.call(system_prompt, user_message, max_tokens)

        monkeypatch.setattr(original_claude, "__init__", mock_claude_init)
        monkeypatch.setattr(original_claude, "call", mock_claude_call)

        api_client.post("/api/negotiate", json={"text": "First message"})

        history_path = Path(vault_path) / ".system" / "state" / "negotiation_history.json"
        assert history_path.exists()

        history = json.loads(history_path.read_text())
        assert len(history) >= 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "First message"
