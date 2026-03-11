"""
Agent runtime abstraction and implementations.

Defines AgentRuntime ABC and Claude API implementation.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AgentRuntime(ABC):
    """Abstract base class for AI agent runtimes."""

    @abstractmethod
    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        """
        Call the agent with system prompt and user message.

        Args:
            system_prompt: System prompt defining agent behavior
            user_message: User/context message
            max_tokens: Maximum tokens in response

        Returns:
            Agent response text

        Raises:
            RuntimeError: If API call fails
        """
        pass


class ClaudeRuntime(AgentRuntime):
    """Claude AI agent via Anthropic API."""

    def __init__(self, model: str, api_key: str):
        """
        Initialize Claude runtime.

        Args:
            model: Claude model ID (e.g., "claude-sonnet-4-6")
            api_key: Anthropic API key
        """
        self.model = model
        self.api_key = api_key
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
        except ImportError:
            raise RuntimeError("anthropic package not installed")

    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        """
        Call Claude API.

        Args:
            system_prompt: System prompt
            user_message: User message
            max_tokens: Max tokens in response

        Returns:
            Claude response text

        Raises:
            RuntimeError: If API call fails
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise RuntimeError(f"Agent call failed: {e}") from e


class MockRuntime(AgentRuntime):
    """Mock runtime for testing (returns fixed responses)."""

    def __init__(self, response: str = "Mock response"):
        """Initialize mock runtime with optional fixed response."""
        self.response = response

    def call(self, system_prompt: str, user_message: str, max_tokens: int) -> str:
        """Return fixed mock response."""
        return self.response
