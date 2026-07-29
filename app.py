from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "src"))

from personal_assistant.orchestrator import PersonalAssistant
from personal_assistant.presentation import escape_html
from personal_assistant.storage import AssistantStore

st.set_page_config(page_title="Orbit", page_icon="◉", layout="wide")
st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 90% 0,#312e8155,transparent 38%),#080b16;color:#f4f4ff}
[data-testid="stSidebar"]{background:#0e1222}.hero{padding:1.7rem 2rem;border:1px solid #343b61;border-radius:24px;background:#11162acc;margin-bottom:1rem;animation:orbit-enter .55s ease-out both,orbit-breathe 8s ease-in-out infinite}
.hero h1{font-size:3rem;margin:0;color:#e9d5ff}.eyebrow{color:#a78bfa;letter-spacing:.14em;text-transform:uppercase}
.agent{display:inline-block;padding:.25rem .55rem;border-radius:8px;background:#312e81;color:#ddd6fe;font-size:.8rem}
@keyframes orbit-enter{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes orbit-breathe{50%{border-color:#a78bfa77;box-shadow:0 18px 52px #6d28d92b}}
@media (prefers-reduced-motion: reduce){.hero{animation:none!important}}
</style><div class="hero"><div class="eyebrow">Your day, one calm command at a time</div><h1>Orbit</h1><p>A privacy-friendly team of specialized agents for tasks, time, drafts, weather, and research.</p></div>
""", unsafe_allow_html=True)

DATA_DIR = ROOT / ".data"
DATA_DIR.mkdir(exist_ok=True)
store = AssistantStore(DATA_DIR / "assistant.db")
assistant = PersonalAssistant(store, ROOT / "sample_data" / "research.json")

with st.sidebar:
    st.header("Agent roster")
    engine_options = ["local", "autogen"]
    configured_engine = os.getenv("ASSISTANT_ENGINE", "local").lower()
    engine = st.selectbox(
        "Orchestration engine",
        engine_options,
        index=engine_options.index(configured_engine) if configured_engine in engine_options else 0,
        help="AutoGen activates a Magentic-One team and requires the optional dependencies plus OPENAI_API_KEY.",
    )
    for icon, name, text in [("✓", "Task", "Local planning"), ("▣", "Calendar", "Local schedule"), ("✉", "Email", "Drafts only"), ("☁", "Weather", "Optional live data"), ("⌕", "Research", "Local or Tavily")]:
        st.markdown(f"**{icon} {name} agent**  \n{text}")
    st.caption("Remote side effects are never performed by the offline workflow.")

chat_tab, tasks_tab, calendar_tab, drafts_tab = st.tabs(["Conversation", "Tasks", "Calendar", "Drafts"])
with chat_tab:
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "What can I take off your plate?", "agent": "Coordinator"}]
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message.get("agent"):
                st.markdown(f"<span class='agent'>{escape_html(message['agent'])}</span>", unsafe_allow_html=True)
            st.markdown(message["content"])
            if message.get("trace"):
                st.caption("AutoGen trace · " + " → ".join(item["source"] for item in message["trace"] if item.get("source")))
    if prompt := st.chat_input("Try “Add task: prepare launch brief by Friday”"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        try:
            response = asyncio.run(assistant.handle(prompt, engine=engine))
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.message,
                "agent": response.agent,
                "trace": response.data.get("trace", []),
            })
        except Exception as exc:
            st.session_state.messages.append({"role": "assistant", "content": f"I couldn’t complete that: {exc}", "agent": "Coordinator"})
        st.rerun()
with tasks_tab:
    rows = store.list_tasks(include_completed=True)
    if not rows:
        st.info("No tasks yet. Add one in the conversation.")
    for row in rows:
        checked = st.checkbox(f"#{row['id']} · {row['title']} · {row['priority']}", value=bool(row["completed"]), key=f"task-view-{row['id']}", disabled=bool(row["completed"]))
        if checked and not row["completed"]:
            store.complete_task(row["id"])
            st.rerun()
with calendar_tab:
    for row in store.list_events():
        st.markdown(f"**{row['starts_at']}**  \n{row['title']} · {row['duration_minutes']} minutes")
    if not store.list_events():
        st.info("Your calendar is clear.")
with drafts_tab:
    for row in store.list_drafts():
        with st.expander(f"To {row['recipient']} · {row['subject']}"):
            st.code(row["body"], language=None)
            st.caption("Saved locally — not sent")
    if not store.list_drafts():
        st.info("No email drafts yet.")
