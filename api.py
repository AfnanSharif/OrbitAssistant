from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import sys
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from personal_assistant.orchestrator import PersonalAssistant
from personal_assistant.storage import AssistantStore
from personal_assistant.integrations.google_workspace import GoogleWorkspace
from personal_assistant.integrations.slack import SlackMessenger

logger = logging.getLogger(__name__)

DATA_DIR = ROOT / ".data"
DATA_DIR.mkdir(exist_ok=True)
assistant = PersonalAssistant(AssistantStore(DATA_DIR / "assistant.db"), ROOT / "sample_data" / "research.json")
app = FastAPI(title="Orbit Assistant API", version="1.0.0")


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=4000)
    engine: str | None = Field(default=None, pattern="^(local|autogen)$")


class Confirmation(BaseModel):
    confirm: bool = False


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "mode": "offline-first"}


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> dict:
    try:
        engine = payload.engine or os.getenv("ASSISTANT_ENGINE", "local")
        return (await assistant.handle(payload.message, engine=engine)).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/google/events/{event_id}")
async def sync_google_event(event_id: int, payload: Confirmation) -> dict:
    if not payload.confirm:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required before creating a remote event")
    try:
        result = GoogleWorkspace().create_calendar_event(assistant.tools.store.get_event(event_id))
        return {"status": "created", "provider": "google-calendar", "id": result.get("id"), "htmlLink": result.get("htmlLink")}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/google/drafts/{draft_id}")
async def sync_gmail_draft(draft_id: int, payload: Confirmation) -> dict:
    if not payload.confirm:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required before creating a remote draft")
    try:
        result = GoogleWorkspace().create_gmail_draft(assistant.tools.store.get_draft(draft_id))
        return {"status": "created", "provider": "gmail-draft", "id": result.get("id")}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _valid_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    secret = os.getenv("SLACK_SIGNING_SECRET", "")
    try:
        stale = not timestamp or abs(time.time() - int(timestamp)) > 300
    except ValueError:
        return False
    if not secret or stale:
        return False
    digest = "v0=" + hmac.new(secret.encode(), b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


async def _reply_to_slack(event: dict) -> None:
    try:
        prompt = re.sub(r"<@[A-Z0-9]+>", "", str(event.get("text", ""))).strip()
        result = await assistant.handle(prompt, engine=os.getenv("SLACK_ASSISTANT_ENGINE", os.getenv("ASSISTANT_ENGINE", "local")))
        await SlackMessenger().post(
            str(event.get("channel", "")),
            result.message,
            str(event.get("thread_ts") or event.get("ts") or "") or None,
        )
    except Exception:
        logger.exception("Slack background reply failed")


@app.post("/api/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks) -> dict:
    body = await request.body()
    if not _valid_slack_signature(body, request.headers.get("X-Slack-Request-Timestamp", ""), request.headers.get("X-Slack-Signature", "")):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    payload = await request.json()
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    event = payload.get("event", {})
    if event.get("bot_id") or event.get("type") not in {"app_mention", "message"}:
        return {"ok": True, "ignored": True}
    if not os.getenv("SLACK_BOT_TOKEN", "").strip():
        raise HTTPException(status_code=503, detail="SLACK_BOT_TOKEN is required for conversational replies")
    if not event.get("channel") or not event.get("text"):
        raise HTTPException(status_code=422, detail="Slack event is missing channel or text")
    background_tasks.add_task(_reply_to_slack, event)
    return {"ok": True, "queued": True}
