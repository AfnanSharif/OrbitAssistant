from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from .models import AgentResponse
from .storage import AssistantStore


class ProductivityTools:
    def __init__(self, store: AssistantStore, research_path: str | Path | None = None) -> None:
        self.store = store
        self.research_path = Path(research_path) if research_path else None

    async def task(self, prompt: str) -> AgentResponse:
        complete = re.search(r"(?:complete|finish|done)\s+(?:task\s+)?#?(\d+)", prompt, re.I)
        if complete:
            row = self.store.complete_task(int(complete.group(1)))
            return AgentResponse("Task agent", f"Marked task #{row['id']} complete: {row['title']}", {"task": row})
        if re.search(r"\b(list|show|what).*(tasks?|to-?do)|\b(tasks?|to-?do)\b.*\b(list|show)\b", prompt, re.I):
            rows = self.store.list_tasks()
            message = "Your open tasks:\n" + "\n".join(f"- #{r['id']} {r['title']} ({r['priority']})" for r in rows) if rows else "You have no open tasks."
            return AgentResponse("Task agent", message, {"tasks": rows}, ["Add task: prepare the demo by Friday"])
        title = re.sub(r"^(please\s+)?(?:add|create|remember)\s+(?:a\s+)?(?:task|to-?do)?\s*[:\-]?\s*", "", prompt, flags=re.I).strip()
        due_match = re.search(r"\b(?:by|due)\s+(.+)$", title, re.I)
        due = due_match.group(1).strip() if due_match else None
        if due_match:
            title = title[: due_match.start()].strip()
        priority_match = re.search(r"\b(high|medium|low)\s+priority\b", title, re.I)
        priority = priority_match.group(1).lower() if priority_match else "medium"
        title = re.sub(r"\b(high|medium|low)\s+priority\b", "", title, flags=re.I).strip(" ,-.")
        if len(title) < 3:
            raise ValueError("Tell me what the task should be")
        row = self.store.add_task(title, due, priority)
        return AgentResponse("Task agent", f"Added task #{row['id']}: **{title}**" + (f" — due {due}" if due else ""), {"task": row}, ["Show my tasks", f"Complete task {row['id']}"])

    async def calendar(self, prompt: str) -> AgentResponse:
        if re.search(r"\b(agenda|calendar|events?|schedule)\b", prompt, re.I) and not re.search(r"\b(add|book|create|schedule)\b.*\b(on|at)\b", prompt, re.I):
            rows = self.store.list_events()
            message = "Upcoming events:\n" + "\n".join(f"- {r['starts_at']} — {r['title']} ({r['duration_minutes']} min)" for r in rows) if rows else "Your local calendar is clear."
            return AgentResponse("Calendar agent", message, {"events": rows}, ["Schedule Design review on 2026-08-02 at 14:00"])
        match = re.search(
            r"(?:schedule|book|add|create)\s+(?P<title>.+?)\s+(?:on\s+)?(?P<date>\d{4}-\d{2}-\d{2})\s+(?:at\s+)?(?P<time>\d{1,2}:\d{2})(?:\s+for\s+(?P<duration>\d+)\s*(?:min|minutes))?",
            prompt,
            re.I,
        )
        if not match:
            raise ValueError("Use: schedule <title> on YYYY-MM-DD at HH:MM [for 30 minutes]")
        start = f"{match.group('date')}T{match.group('time')}"
        row = self.store.add_event(match.group("title").strip(), start, int(match.group("duration") or 30))
        return AgentResponse("Calendar agent", f"Scheduled **{row['title']}** for {row['starts_at']} ({row['duration_minutes']} minutes).", {"event": row}, ["Show my agenda"])

    async def email(self, prompt: str) -> AgentResponse:
        recipient_match = re.search(r"\bto\s+([^\s,]+@[^\s,]+)", prompt, re.I)
        subject_match = re.search(r"\bsubject\s*[:=]\s*([^;]+)", prompt, re.I)
        if not recipient_match:
            raise ValueError("Include a recipient, for example: draft email to alex@example.com subject: Follow-up; ...")
        recipient = recipient_match.group(1)
        subject = subject_match.group(1).strip() if subject_match else "Follow-up"
        details = prompt.split(";", 1)[1].strip() if ";" in prompt else "I wanted to follow up and share a quick update."
        body = f"Hello,\n\n{details}\n\nBest regards"
        row = self.store.add_draft(recipient, subject, body)
        return AgentResponse("Email agent", f"Saved draft #{row['id']} to **{recipient}** with subject **{subject}**. Nothing was sent.", {"draft": row}, ["Review drafts"], requires_confirmation=True)

    async def weather(self, prompt: str) -> AgentResponse:
        location_match = re.search(r"\b(?:in|for)\s+([A-Za-z][A-Za-z .,'-]+)$", prompt)
        if not location_match:
            raise ValueError("Name a city, for example: weather in Karachi")
        city = location_match.group(1).strip()
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            return AgentResponse("Weather agent", f"Live weather for {city} needs OPENWEATHER_API_KEY. No estimate was fabricated.", {"city": city}, ["Add OPENWEATHER_API_KEY to .env"])
        query = urllib.parse.urlencode({"q": city, "appid": api_key, "units": os.getenv("WEATHER_UNITS", "metric")})
        data = await asyncio.to_thread(_read_json, f"https://api.openweathermap.org/data/2.5/weather?{query}")
        description = data["weather"][0]["description"]
        temperature = data["main"]["temp"]
        return AgentResponse("Weather agent", f"{city}: **{temperature}°**, {description}.", {"weather": data})

    async def research(self, prompt: str) -> AgentResponse:
        query = re.sub(r"^(research|search|look up)\s+", "", prompt, flags=re.I).strip()
        api_key = os.getenv("TAVILY_API_KEY")
        if api_key:
            request = urllib.request.Request(
                "https://api.tavily.com/search",
                data=json.dumps({"api_key": api_key, "query": query, "max_results": 5}).encode(),
                headers={"Content-Type": "application/json"},
            )
            data = await asyncio.to_thread(_read_json_request, request)
            rows = [{"title": row.get("title"), "url": row.get("url"), "summary": row.get("content")} for row in data.get("results", [])]
            message = "\n".join(f"- [{r['title']}]({r['url']}): {r['summary']}" for r in rows) or "No search results found."
            return AgentResponse("Research agent", message, {"results": rows})
        rows = json.loads(self.research_path.read_text(encoding="utf-8")) if self.research_path and self.research_path.exists() else []
        terms = set(re.findall(r"[a-z]{3,}", query.lower()))
        scored = sorted(rows, key=lambda row: len(terms & set(re.findall(r"[a-z]{3,}", (row["title"] + " " + row["summary"]).lower()))), reverse=True)
        matches = [row for row in scored if terms & set(re.findall(r"[a-z]{3,}", (row["title"] + " " + row["summary"]).lower()))][:3]
        if not matches:
            return AgentResponse("Research agent", "The local reference shelf has no relevant entry. Configure TAVILY_API_KEY for live search.", {"results": []})
        return AgentResponse("Research agent", "\n".join(f"- **{r['title']}** — {r['summary']}" for r in matches), {"results": matches}, ["Configure Tavily for current web results"])


def _read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=12) as response:
        return json.load(response)


def _read_json_request(request: urllib.request.Request) -> dict:
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)
