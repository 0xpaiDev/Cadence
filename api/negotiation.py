"""
Negotiation session management.

Handles agent-mediated conversation to refine the daily plan.
"""

import json
import logging
import re
import uuid
from pathlib import Path

from scripts.runtime import AgentRuntime

logger = logging.getLogger(__name__)


class NegotiationSession:
    """Manage negotiation conversation and draft mutations."""

    def __init__(
        self,
        draft: dict,
        context: str,
        runtime: AgentRuntime,
        vault_path: str = "",
        history: list[dict] | None = None,
    ):
        """
        Initialize negotiation session.

        Args:
            draft: Initial draft dict
            context: Daily context markdown
            runtime: Agent runtime instance
            vault_path: Path to vault for loading system prompt template
            history: Optional conversation history (for multi-turn sessions)
        """
        self.draft = draft
        self.context = context
        self.runtime = runtime
        self.vault_path = vault_path
        self.history = history or []
        self.decisions: list[dict] = []

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
        """
        system_prompt = self._build_system_prompt()
        user_msg = self._build_user_message(user_message)

        response = self.runtime.call(system_prompt, user_msg, max_tokens=600)

        # Strip <changes> block from displayed message
        display_msg = re.sub(
            r"<changes>.*?</changes>", "", response, flags=re.DOTALL
        ).strip()

        # Extract and apply mutations
        changes = self._extract_changes(response)
        self._apply_mutations(changes)

        # Record in history
        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": display_msg})

        # Return result
        return {"message": display_msg, "draft": self.draft, "decisions": changes}

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

        Returns:
            Template text loaded from vault/.system/config/negotiation_template.md

        Raises:
            FileNotFoundError: If template not found in vault
        """
        if not self.vault_path:
            raise FileNotFoundError("vault_path not provided to NegotiationSession")

        template_path = (
            Path(self.vault_path)
            / ".system"
            / "config"
            / "negotiation_template.md"
        )
        if not template_path.exists():
            raise FileNotFoundError(f"Negotiation template not found: {template_path}")

        return template_path.read_text()

    def _build_user_message(self, user_message: str) -> str:
        """
        Build user message from draft, context, and history.

        For first turn, includes draft and context.
        For subsequent turns, includes conversation history.

        Args:
            user_message: Current user message

        Returns:
            Formatted user message for agent
        """
        if not self.history:
            # First turn: include draft and context
            draft_json = json.dumps(self.draft, indent=2)
            return (
                f"## Current Draft\n{draft_json}\n\n"
                f"## Daily Context\n{self.context}\n\n"
                f"## User Request\n{user_message}"
            )
        else:
            # Subsequent turns: include history then new message
            history_text = ""
            for msg in self.history:
                role = "User" if msg["role"] == "user" else "Assistant"
                history_text += f"{role}: {msg['content']}\n"

            return f"{history_text}\nUser: {user_message}"

    def _extract_changes(self, response: str) -> list[dict]:
        """
        Extract structured changes from agent response.

        Parses <changes>...</changes> XML block with JSON actions.

        Args:
            response: Agent response text

        Returns:
            List of action dicts, empty list if no block or parse errors
        """
        match = re.search(r"<changes>(.*?)</changes>", response, re.DOTALL)
        if not match:
            return []

        block_content = match.group(1).strip()
        if not block_content:
            return []

        actions = []
        for line in block_content.split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                action = json.loads(line)
                actions.append(action)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse action JSON: {line}. Error: {e}")
                continue

        return actions

    def _apply_mutations(self, actions: list[dict]) -> None:
        """
        Apply mutations to draft based on actions.

        Supports:
        - drop_task: remove task by id
        - add_task: append new task
        - reprioritize_task: change task priority
        - reschedule_event: move event to new time
        - add_task_notes: add/update notes on task

        Args:
            actions: List of action dicts from agent
        """
        for action in actions:
            action_type = action.get("action")

            if action_type == "drop_task":
                task_id = action.get("task_id")
                if task_id:
                    self.draft["tasks"] = [
                        t for t in self.draft.get("tasks", []) if t["id"] != task_id
                    ]
                    logger.debug(f"Dropped task {task_id}")

            elif action_type == "add_task":
                text = action.get("text")
                priority = action.get("priority", "normal")
                if text:
                    new_task = {
                        "id": f"neg_{uuid.uuid4().hex[:8]}",
                        "text": text,
                        "source": "negotiation",
                        "priority": priority,
                        "status": "pending",
                    }
                    self.draft.setdefault("tasks", []).append(new_task)
                    logger.debug(f"Added task: {text}")

            elif action_type == "reprioritize_task":
                task_id = action.get("task_id")
                priority = action.get("priority")
                if task_id and priority:
                    for task in self.draft.get("tasks", []):
                        if task["id"] == task_id:
                            task["priority"] = priority
                            logger.debug(f"Reprioritized task {task_id} to {priority}")
                            break

            elif action_type == "reschedule_event":
                event_id = action.get("event_id")
                new_time_start = action.get("time_start")
                if event_id and new_time_start:
                    for event in self.draft.get("schedule", []):
                        if event["id"] == event_id:
                            event["time_start"] = new_time_start
                            # Update end time if duration provided
                            if "duration_minutes" in action:
                                duration = action["duration_minutes"]
                                # Simple time arithmetic (assumes HH:MM format)
                                try:
                                    start_h, start_m = map(int, new_time_start.split(":"))
                                    end_h = start_h + duration // 60
                                    end_m = start_m + duration % 60
                                    if end_m >= 60:
                                        end_h += 1
                                        end_m -= 60
                                    event["time_end"] = f"{end_h:02d}:{end_m:02d}"
                                except (ValueError, TypeError):
                                    pass
                            logger.debug(f"Rescheduled event {event_id} to {new_time_start}")
                            break

            elif action_type == "add_task_notes":
                task_id = action.get("task_id")
                notes = action.get("notes", "")
                if task_id:
                    for task in self.draft.get("tasks", []):
                        if task["id"] == task_id:
                            task["notes"] = notes
                            logger.debug(f"Added notes to task {task_id}")
                            break

            else:
                logger.warning(f"Unknown action type: {action_type}")
