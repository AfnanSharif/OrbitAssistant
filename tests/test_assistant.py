import asyncio
import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from personal_assistant.orchestrator import PersonalAssistant
from personal_assistant.presentation import escape_html
from personal_assistant.storage import AssistantStore
from personal_assistant.autogen_adapter import AutoGenCoordinator
from personal_assistant.integrations.slack import SlackMessenger


class FakeCoordinator:
    def __init__(self, tools):
        self.tools = tools
        self.last_trace = [{"source": "calendar_agent", "type": "TextMessage"}]
        self.closed = False

    async def respond(self, prompt):
        return f"coordinated: {prompt}"

    async def close(self):
        self.closed = True


class FakeSlackClient:
    def __init__(self, token):
        self.token = token
        self.calls = []

    async def chat_postMessage(self, **payload):
        self.calls.append(payload)
        return {"ok": True, "ts": "123.4"}


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AssistantStore(Path(self.temp.name) / "test.db")
        self.assistant = PersonalAssistant(self.store, ROOT / "sample_data" / "research.json")

    def tearDown(self):
        self.temp.cleanup()

    def ask(self, prompt):
        return asyncio.run(self.assistant.handle(prompt))

    def test_task_lifecycle(self):
        created = self.ask("Add task: prepare slides by Friday")
        self.assertEqual(created.data["route"], "task")
        task_id = created.data["task"]["id"]
        self.ask(f"complete task {task_id}")
        self.assertEqual(self.store.list_tasks(), [])

    def test_calendar_event(self):
        response = self.ask("Schedule design review on 2026-08-02 at 14:00 for 45 minutes")
        self.assertEqual(response.data["event"]["duration_minutes"], 45)
        self.assertEqual(self.assistant.route("show calendar"), "calendar")

    def test_email_is_draft_only(self):
        response = self.ask("Draft email to alex@example.com subject: Update; We are on track.")
        self.assertTrue(response.requires_confirmation)
        self.assertIn("Nothing was sent", response.message)
        self.assertEqual(len(self.store.list_drafts()), 1)

    def test_offline_research(self):
        response = self.ask("research meeting agendas")
        self.assertIn("desired decisions", response.message)

    def test_weather_without_key_is_honest(self):
        response = self.ask("weather in Karachi")
        self.assertIn("needs OPENWEATHER_API_KEY", response.message)

    def test_html_boundary_escapes_agent_label(self):
        self.assertEqual(escape_html("<b onmouseover='bad()'>agent</b>"), "&lt;b onmouseover=&#x27;bad()&#x27;&gt;agent&lt;/b&gt;")

    def test_autogen_engine_is_reachable_with_injected_team(self):
        created = []

        def factory(tools):
            coordinator = FakeCoordinator(tools)
            created.append(coordinator)
            return coordinator

        assistant = PersonalAssistant(self.store, ROOT / "sample_data" / "research.json", autogen_factory=factory)
        response = asyncio.run(assistant.handle("Coordinate my schedule", engine="autogen"))
        self.assertEqual(response.agent, "AutoGen team")
        self.assertEqual(response.data["trace"][0]["source"], "calendar_agent")
        self.assertTrue(created[0].closed)

    def test_autogen_function_callbacks_use_real_tools(self):
        callbacks = AutoGenCoordinator._callbacks(self.assistant.tools)
        payload = asyncio.run(callbacks["task"]("Add task: verify tool wiring"))
        self.assertIn("verify tool wiring", payload)
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_slack_messenger_posts_threaded_reply(self):
        clients = []

        def factory(token):
            client = FakeSlackClient(token)
            clients.append(client)
            return client

        messenger = SlackMessenger("xoxb-test-placeholder", client_factory=factory)
        response = asyncio.run(messenger.post("C123", "Done", "111.2"))
        self.assertTrue(response["ok"])
        self.assertEqual(clients[0].calls[0]["thread_ts"], "111.2")

    def test_invalid_engine_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "engine"):
            asyncio.run(self.assistant.handle("show tasks", engine="unknown"))


if __name__ == "__main__":
    unittest.main()
