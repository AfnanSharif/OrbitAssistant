from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from .models import AgentResponse
from .storage import AssistantStore
from .tools import ProductivityTools


class PersonalAssistant:
    """Deterministic agent router; safe commands work without an LLM or credentials."""

    def __init__(
        self,
        store: AssistantStore,
        research_path: str | Path | None = None,
        autogen_factory: Callable[[ProductivityTools], Any] | None = None,
    ) -> None:
        self.tools = ProductivityTools(store, research_path)
        self.autogen_factory = autogen_factory

    def route(self, prompt: str) -> str:
        lowered = prompt.lower()
        if re.search(r"\b(email|mail|draft|recipient|subject)\b", lowered):
            return "email"
        if re.search(r"\b(weather|forecast|temperature)\b", lowered):
            return "weather"
        if re.search(r"\b(research|search|look up|find out)\b", lowered):
            return "research"
        if re.search(r"\b(calendar|agenda|meeting|event|schedule|book)\b", lowered):
            return "calendar"
        if re.search(r"\b(task|to-do|todo|remember|complete|finish)\b", lowered):
            return "task"
        return "help"

    async def handle(self, prompt: str, engine: str = "local") -> AgentResponse:
        prompt = " ".join(prompt.split())
        if len(prompt) < 2:
            raise ValueError("Please enter a request")
        engine = engine.strip().lower()
        if engine not in {"local", "autogen"}:
            raise ValueError("engine must be 'local' or 'autogen'")
        if engine == "autogen":
            if self.autogen_factory is None:
                from .autogen_adapter import AutoGenCoordinator

                coordinator = AutoGenCoordinator(self.tools)
            else:
                coordinator = self.autogen_factory(self.tools)
            try:
                message = await coordinator.respond(prompt)
                return AgentResponse(
                    "AutoGen team",
                    message,
                    {"engine": "autogen", "trace": getattr(coordinator, "last_trace", [])},
                )
            finally:
                await coordinator.close()
        route = self.route(prompt)
        if route == "help":
            return AgentResponse(
                "Coordinator",
                "I can manage local tasks, calendar events, and email drafts; fetch configured weather; or search a local/live research source. I never send an email or create a remote event silently.",
                {"route": route},
                ["Add task: prepare slides by Friday", "Schedule review on 2026-08-02 at 14:00", "Draft email to alex@example.com subject: Update; The launch is on track."],
            )
        handler = getattr(self.tools, route)
        result = await handler(prompt)
        result.data.setdefault("engine", "local")
        result.data.setdefault("route", route)
        return result
