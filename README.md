<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=cc2b5e,753a88&height=200&section=header&text=OrbitAssistant&fontSize=70&fontColor=ffffff&animation=twinkling" width="100%" />

<img src="https://img.icons8.com/?id=M1bt3ZHCANRW&format=png&size=100" width="90" />

<img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=22&duration=2500&pause=1000&color=cc2b5e&center=true&vCenter=true&width=700&height=50&lines=A%20local-first%2C%20tool-routed%20personal%20assistant%20with;Python%20+%20Streamlit" alt="Typing SVG" />

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](#)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](#)
[![AutoGen](https://img.shields.io/badge/AutoGen-0078D4?style=for-the-badge)](#)

</div>

---

## 📖 Overview

**OrbitAssistant** — A local-first, tool-routed personal assistant with optional AutoGen orchestration.

Core logic lives in `src/personal_assistant/`. Configuration is centralized in `config/settings.yaml`
and secrets/API keys are loaded from a local `.env` (see `.env.example`).

## 🏗️ Project Layout

```
OrbitAssistant/
├── app.py               # Streamlit entry point
├── src/personal_assistant/
│   └── ...              # Core package — a local-first, tool-routed personal assistant with optional autogen orchestration
├── config/settings.yaml # App configuration
├── tests/                # Unit tests
├── scripts/setup.sh      # venv + install helper (macOS/Linux)
├── requirements-ai.txt
├── requirements.txt
```

### Also included
- `cli.py` — command-line interface
- `api.py` — standalone API entry point


## ⚡ Setup & Run

### 🪟 Windows (PowerShell / CMD)
```cmd
git clone https://github.com/AfnanSharif/OrbitAssistant.git
cd OrbitAssistant

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-ai.txt  # optional extras

copy .env.example .env
:: edit .env to add any API keys — the app runs fully offline without them

streamlit run app.py
```

### 🍎 macOS / 🐧 Linux
```bash
git clone https://github.com/AfnanSharif/OrbitAssistant.git
cd OrbitAssistant

./scripts/setup.sh                 # creates .venv and installs requirements.txt
source .venv/bin/activate
pip install -r requirements-ai.txt  # optional extras

cp .env.example .env
# edit .env to add any API keys — the app runs fully offline without them

streamlit run app.py
```

Open **http://localhost:8501**.

```bash
make test    # run the test suite
make lint    # lint the codebase
```

---

<div align="center">

**Created by [AfnanSharif](https://github.com/AfnanSharif)** · ⭐ star this repo if it helped you

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=cc2b5e,753a88&height=80&section=footer" width="100%" />

</div>
