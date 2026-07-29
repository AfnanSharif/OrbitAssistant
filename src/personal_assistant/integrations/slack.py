from __future__ import annotations

import os
from typing import Any, Callable


class SlackMessenger:
    """Small lazy Slack Web API boundary suitable for FastAPI background work."""

    def __init__(self, token: str | None = None, client_factory: Callable[..., Any] | None = None) -> None:
        self.token = (token or os.getenv("SLACK_BOT_TOKEN", "")).strip()
        if not self.token:
            raise RuntimeError("SLACK_BOT_TOKEN is required to post Slack replies")
        if client_factory is None:
            try:
                from slack_sdk.web.async_client import AsyncWebClient
            except ImportError as exc:
                raise RuntimeError("Install Slack support with `pip install -r requirements-ai.txt`") from exc
            client_factory = AsyncWebClient
        self.client = client_factory(token=self.token)

    async def post(self, channel: str, text: str, thread_ts: str | None = None) -> dict[str, Any]:
        channel = channel.strip()
        text = text.strip()
        if not channel:
            raise ValueError("Slack channel is required")
        if not text:
            raise ValueError("Slack message cannot be empty")
        response = await self.client.chat_postMessage(
            channel=channel,
            text=text[:4000],
            thread_ts=thread_ts,
        )
        return dict(response)
