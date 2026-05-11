"""Thin wrapper around the Anthropic SDK. One LLM turn per env step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from kitchen_agent.env.observation import Observation

SYSTEM_PROMPT = """\
You are a kitchen agent. Each turn you receive a snapshot of the world and \
make exactly one tool call. You stop when the goal in the observation is met.

Rules:
- You have two hands. Many actions need one of them free.
- Use the ids shown in the observation (e.g. egg_1, mixing_bowl, oven) verbatim in tool calls.
- Most actions require you to be adjacent — navigate_to first, then act.
- Read failure messages literally. They name what's missing and what to do next.
- Be efficient; don't repeat an action that just failed for the same reason.
"""


@dataclass
class AgentDecision:
    tool_name: str
    tool_args: dict[str, Any]
    reasoning: str
    tool_use_id: str


class ClaudeAgent:
    """Maintains conversation history and forces a tool call per turn."""

    def __init__(
        self,
        client: Anthropic,
        tools: list[dict[str, Any]],
        system_prompt: str = SYSTEM_PROMPT,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
    ) -> None:
        self.client = client
        self.tools = tools
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self._messages: list[dict[str, Any]] = []
        self._pending_tool_use_id: str | None = None
        self._pending_step_result: tuple[bool, str] | None = None

    def record_step_result(self, success: bool, message: str) -> None:
        """Stash the env's reply to the previous tool call. The next `act()`
        will deliver it as a tool_result and tack on the new observation."""
        self._pending_step_result = (success, message)

    def act(self, observation: Observation) -> AgentDecision:
        user_content: list[dict[str, Any]] = []
        if self._pending_tool_use_id is not None and self._pending_step_result is not None:
            success, message = self._pending_step_result
            user_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": self._pending_tool_use_id,
                    "content": message,
                    "is_error": not success,
                }
            )
        user_content.append({"type": "text", "text": observation.text})
        self._messages.append({"role": "user", "content": user_content})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            tools=self.tools,
            tool_choice={"type": "any"},
            messages=self._messages,
        )

        assistant_content = [block.model_dump() for block in response.content]
        self._messages.append({"role": "assistant", "content": assistant_content})

        reasoning_parts: list[str] = []
        tool_name: str | None = None
        tool_args: dict[str, Any] | None = None
        tool_use_id: str | None = None
        for block in response.content:
            if block.type == "text":
                reasoning_parts.append(block.text)
            elif block.type == "tool_use":
                # tool_choice=any guarantees at least one; take the first.
                if tool_name is None:
                    tool_name = block.name
                    raw_input = block.input or {}
                    if not isinstance(raw_input, dict):
                        raw_input = {}
                    tool_args = dict(raw_input)
                    tool_use_id = block.id

        if tool_name is None or tool_args is None or tool_use_id is None:
            raise RuntimeError(
                "Model did not return a tool_use block despite tool_choice='any'."
            )

        self._pending_tool_use_id = tool_use_id
        return AgentDecision(
            tool_name=tool_name,
            tool_args=tool_args,
            reasoning="\n".join(reasoning_parts).strip(),
            tool_use_id=tool_use_id,
        )
