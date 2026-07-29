from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GoogleWorkspace:
    """Narrow OAuth2 adapter: create calendar events and Gmail drafts, never send mail."""

    def __init__(self, credentials_file: str | Path | None = None, token_file: str | Path | None = None) -> None:
        self.credentials_file = Path(credentials_file or os.getenv("GOOGLE_CLIENT_SECRET_FILE", "credentials.json"))
        self.token_file = Path(token_file or os.getenv("GOOGLE_TOKEN_FILE", "token.json"))
        self.credentials = self._credentials()

    def _credentials(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise RuntimeError("Install the Google Workspace extras from requirements-ai.txt") from exc
        credentials = Credentials.from_authorized_user_file(str(self.token_file), SCOPES) if self.token_file.exists() else None
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            if not self.credentials_file.exists():
                raise RuntimeError(f"Google OAuth client file not found: {self.credentials_file}")
            credentials = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES).run_local_server(port=0)
        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        return credentials

    def create_calendar_event(self, event: dict) -> dict:
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Install google-api-python-client") from exc
        timezone = os.getenv("ASSISTANT_TIMEZONE", "UTC")
        starts_at = datetime.fromisoformat(event["starts_at"])
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=ZoneInfo(timezone))
        ends_at = starts_at + timedelta(minutes=int(event["duration_minutes"]))
        payload = {
            "summary": event["title"],
            "location": event.get("location", ""),
            "start": {"dateTime": starts_at.isoformat(), "timeZone": timezone},
            "end": {"dateTime": ends_at.isoformat(), "timeZone": timezone},
        }
        return build("calendar", "v3", credentials=self.credentials, cache_discovery=False).events().insert(calendarId="primary", body=payload).execute()

    def create_gmail_draft(self, draft: dict) -> dict:
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Install google-api-python-client") from exc
        message = EmailMessage()
        message["To"] = draft["recipient"]
        message["Subject"] = draft["subject"]
        message.set_content(draft["body"])
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        payload = {"message": {"raw": raw}}
        return build("gmail", "v1", credentials=self.credentials, cache_discovery=False).users().drafts().create(userId="me", body=payload).execute()
