"""
Negotiation session management.

Handles agent-mediated conversation to refine the daily plan.
"""

import logging
from typing import Optional
from ..scripts.runtime import AgentRuntime
from ..scripts.schemas import Decision, DecisionAction

logger = logging.getLogger(__name__)


class NegotiationSession:
    """Manage negotiation conversation and draft mutations."""

    def __init__(self, draft: dict, context: str, runtime: AgentRuntime):
        """
        Initialize negotiation session.

        Args:
            draft: Initial draft dict
            context: Daily context markdown
            runtime: Agent runtime instance

        TODO: Implement
        - Store draft, context, runtime
        - Initialize conversation history
        - Initialize decisions list
        """
        self.draft = draft
        self.context = context
        self.runtime = runtime
        self.history = []
        self.decisions = []

    def exchange(self, user_message: str) -> dict:
        """
        One round of negotiation.

        Args:
            user_message: User's message (e.g., "drop the meeting")

        Returns:
            {
                "message": "Agent response text",
                "draft": {...updated draft...},
                "decisions": [...decisions made...]
            }

        TODO: Implement
        - Add user message to history
        - Build system prompt from negotiation template
        - Call runtime.call(system + history)
        - Parse response:
          - Extract text response
          - Extract <changes> XML block
          - Parse JSON actions
          - Apply mutations to draft
        - Record decisions
        - Return response dict
        """
        return {"error": "Not implemented"}

    def approve(self) -> dict:
        """
        Approve the plan.

        Renders draft to markdown, writes files, updates day state.

        Returns:
            {
                "note_path": "Daily/YYYY-MM-DD.md",
                "tasks": {...DayTasks...},
                "decisions": [...all decisions...]
            }

        TODO: Implement
        - Render draft to markdown daily note
        - Write vault/Daily/YYYY-MM-DD.md
        - Write vault/.system/state/decisions.json
        - Update vault/data/tasks/today.md
        - Update day_state to active
        - Return approval result
        """
        return {"error": "Not implemented"}

    def _build_system_prompt(self) -> str:
        """
        Build negotiation system prompt from template.

        TODO: Implement
        - Load negotiation_template.md from vault/.system/config/
        - Return template text
        """
        return "TODO: Implement"

    def _build_user_message(self) -> str:
        """
        Build user message from draft and context.

        TODO: Implement
        - Include draft as first message
        - Include latest user input
        """
        return "TODO: Implement"

    def _extract_changes(self, response: str) -> list[dict]:
        """
        Extract structured changes from agent response.

        Parses <changes>...</changes> XML block with JSON actions.

        Args:
            response: Agent response text

        Returns:
            List of action dicts

        TODO: Implement
        - Find <changes> block in response
        - Parse each line as JSON
        - Return list of actions
        - Return empty list if no block found
        """
        return []

    def _apply_mutations(self, actions: list[dict]) -> None:
        """
        Apply mutations to draft based on actions.

        Args:
            actions: List of action dicts from agent

        TODO: Implement
        - For each action:
          - drop_task: remove task from draft
          - add_task: add task to draft
          - reprioritize_task: change priority
        - Update self.draft
        """
        pass
