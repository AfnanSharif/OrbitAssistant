from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

from .tools import ProductivityTools


ToolCallback = Callable[[str], Awaitable[str]]


def _load_autogen() -> tuple[Any, ...]:
    """Load the optional AutoGen runtime only when that engine is selected."""
    try:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
        from autogen_agentchat.teams import MagenticOneGroupChat
        from autogen_core.tools import FunctionTool
        from autogen_ext.models.openai import OpenAIChatCompletionClient
    except ImportError as exc:
        raise RuntimeError("Install AutoGen with `pip install -r requirements-ai.txt`") from exc
    return (
        AssistantAgent,
        MaxMessageTermination,
        TextMentionTermination,
        MagenticOneGroupChat,
        FunctionTool,
        OpenAIChatCompletionClient,
    )


class AutoGenCoordinator:
    """Magentic-One team backed by the same safe, async productivity tools."""

    def __init__(self, tools: ProductivityTools) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for AutoGen mode")
        (
            AssistantAgent,
            MaxMessageTermination,
            TextMentionTermination,
            MagenticOneGroupChat,
            FunctionTool,
            OpenAIChatCompletionClient,
        ) = _load_autogen()

        self.client = OpenAIChatCompletionClient(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            api_key=api_key,
            parallel_tool_calls=False,
        )
        callbacks = self._callbacks(tools)
        roles = (
            ("task_agent", "Manage local tasks and completion state.", "task"),
            ("calendar_agent", "Manage local calendar events and agendas.", "calendar"),
            ("email_agent", "Create local email drafts only; never send mail.", "email"),
            ("weather_agent", "Fetch configured live weather without inventing data.", "weather"),
            ("research_agent", "Research through the configured local shelf or Tavily.", "research"),
        )
        participants = []
        for name, description, callback_name in roles:
            tool = FunctionTool(callbacks[callback_name], description=description)
            participants.append(
                AssistantAgent(
                    name=name,
                    description=description,
                    model_client=self.client,
                    tools=[tool],
                    reflect_on_tool_use=True,
                    system_message=(
                        f"You are Orbit's {name.replace('_', ' ')}. Use your function tool for requests in your domain. "
                        "Report its real result exactly. Never claim a remote action occurred unless the tool result says so."
                    ),
                )
            )
        termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(max_messages=24)
        self.team = MagenticOneGroupChat(
            participants,
            model_client=self.client,
            termination_condition=termination,
            max_turns=12,
            max_stalls=2,
            final_answer_prompt=(
                "Return a concise final answer grounded only in tool results. State clearly when an integration is not configured, "
                "never imply an email was sent, and append TERMINATE after the user-facing answer."
            ),
        )
        self.last_trace: list[dict[str, str]] = []

    @staticmethod
    def _callbacks(tools: ProductivityTools) -> dict[str, ToolCallback]:
        async def manage_task(request: str) -> str:
            """Create, list, or complete a task from a natural-language request."""
            return json.dumps((await tools.task(request)).to_dict(), ensure_ascii=False)

        async def manage_calendar(request: str) -> str:
            """Create or list local calendar events from a natural-language request."""
            return json.dumps((await tools.calendar(request)).to_dict(), ensure_ascii=False)

        async def create_email_draft(request: str) -> str:
            """Create a local email draft; this function never sends the message."""
            return json.dumps((await tools.email(request)).to_dict(), ensure_ascii=False)

        async def get_weather(request: str) -> str:
            """Fetch configured current weather for the city in the request."""
            return json.dumps((await tools.weather(request)).to_dict(), ensure_ascii=False)

        async def research_web(request: str) -> str:
            """Research a topic using the configured local or Tavily source."""
            return json.dumps((await tools.research(request)).to_dict(), ensure_ascii=False)

        return {
            "task": manage_task,
            "calendar": manage_calendar,
            "email": create_email_draft,
            "weather": get_weather,
            "research": research_web,
        }

    async def respond(self, prompt: str) -> str:
        result = await self.team.run(task=prompt)
        self.last_trace = [
            {"source": str(getattr(message, "source", "team")), "type": type(message).__name__}
            for message in result.messages
        ]
        content = str(result.messages[-1].content).strip()
        if content.endswith("TERMINATE"):
            content = content[: -len("TERMINATE")].rstrip()
        return content

    async def close(self) -> None:
        await self.client.close()
