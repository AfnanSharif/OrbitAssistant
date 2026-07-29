from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Use the Orbit local personal assistant")
    parser.add_argument("request", nargs="+")
    parser.add_argument("--database", type=Path, default=ROOT / ".data" / "assistant.db")
    parser.add_argument("--engine", choices=("local", "autogen"), default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    assistant = PersonalAssistant(AssistantStore(args.database), ROOT / "sample_data" / "research.json")
    import os

    result = asyncio.run(assistant.handle(" ".join(args.request), engine=args.engine or os.getenv("ASSISTANT_ENGINE", "local")))
    print(json.dumps(result.to_dict(), indent=2) if args.json else result.message)


if __name__ == "__main__":
    main()
