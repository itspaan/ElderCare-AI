# CLAUDE.md

This file gives Claude Code the context it needs to work on this project. Read it before making changes.

---

## Project: ElderCare AI

A conversational **Machine Learning + LLM** health companion for **Taiwan's elderly** and their caregivers, built around the common chronic conditions of Taiwan's ageing population. A Google Gemini agent (with function calling) holds a natural, voice-friendly conversation and uses tools to:

1. **Screen for a likely condition** (Hypertension, Diabetes, Osteoarthritis, Dementia, Healthy) from basic vitals/symptoms, via a Random Forest model.
2. **Manage daily care** — set/list/delete medicine reminders, call an emergency contact, store and analyze uploaded images.
3. **Work bilingually** — the UI switches between English and Traditional Chinese (zh-TW), and the agent replies in the user's own language, in short sentences suited for text-to-speech.

See `docs/PRD.md` for full product requirements.

> **Important:** this is a **screening and care aid, not a medical diagnosis.** Every health result must include a disclaimer encouraging the user to consult a healthcare professional.

---

## Tech Stack

- **Language:** Python 3
- **Backend / API:** FastAPI (run with Uvicorn)
- **LLM:** Google Gemini (`gemini-2.5-flash`) via the `google-genai` SDK, with function calling
- **ML:** scikit-learn (Random Forest), pandas, numpy
- **Storage:** SQLite + JSON files under `storage/`
- **Frontend:** plain HTML/CSS/JS in `static/index.html` (no heavy framework)
- **Config:** `.env` with `GEMINI_API_KEY`, loaded via `python-dotenv`
- **Environment:** Windows, VS Code. Virtual env in `venv/`.

---

## How to Run

```powershell
# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# (First time only) generate data and train the model
python -m data.generate_dummy
python -m training.train_model

# Run the app
python -m uvicorn main:app --reload --port 8000
```

Then open http://127.0.0.1:8000 in the browser.

You can also chat with the agent in the terminal: `python -m core.agent`.

---

## Project Structure

```
AgentAi/
├── main.py                       # FastAPI app + API routes
├── core/
│   ├── agent.py                  # Gemini chat session, tools, ML inference, chat_with_agent()
│   └── prompts.py                # System prompt for the agent
├── tools/
│   ├── reminders.py              # Medicine reminders (SQLite + JSON export)
│   ├── contacts.py               # Maker / contact info tool
│   ├── image_storage.py          # Save + index uploaded images
│   └── survey.py                 # Research survey: consent-gated store + CSV export for retraining
├── training/
│   └── train_model.py            # Trains the Random Forest -> models/disease_model.pkl
├── data/
│   ├── generate_dummy.py         # Generates the synthetic dataset
│   └── elderly_synthetic_data.csv
├── models/
│   └── disease_model.pkl         # Saved {model, features} dict
├── static/
│   └── index.html                # Dashboard + chat UI
├── storage/                      # Runtime data (gitignored): reminders.db, images/, *.json
├── requirements.txt
├── docs/
│   └── PRD.md
└── CLAUDE.md
```

> Check the current code before adding files — don't blindly recreate structure.

---

## Key Components

- **API routes (`main.py`):** `GET /` (UI), `POST /api/chat`, `GET /api/health`, `GET /api/reminders`, `GET /api/images`, `POST /api/survey`, `GET /api/survey/stats`, `GET /api/survey/export`. Images arrive as base64 in the chat request.
- **Agent (`core/agent.py`):** loads `models/disease_model.pkl`, registers tools, creates the Gemini chat session, and exposes `chat_with_agent(user_input, image_bytes, image_mime)`.
- **ML tool (`predict_disease_from_vitals`):** builds a one-row DataFrame in the trained feature order, returns prediction + confidence + standard advice.
- **Model artifact:** a pickled dict `{"model": ..., "features": [...]}`. The feature list defines column order at inference — keep training and inference in sync.

---

## Conventions

- Keep ML logic (`training/`, model inference in `core/agent.py`), tools (`tools/`), prompts (`core/prompts.py`), and web routes (`main.py`) separated.
- Never hardcode the Gemini API key — read it from the `GEMINI_API_KEY` environment variable (already wired through `.env`).
- Every user-facing health result must include the safety disclaimer.
- Keep agent replies short, warm, and plain-text (no markdown/bullets) so they sound natural via text-to-speech. Detect the user's language and reply in it.
- The UI is bilingual (English / Traditional Chinese, zh-TW). Frontend strings live in the `translations` table in `static/index.html` keyed by `data-i18n`/`data-i18n-placeholder`/`data-i18n-title`; when adding UI text, add the key to **both** `en` and `zh`. Use Traditional characters (zh-TW), not Simplified, and keep TTS/STT language codes at `zh-TW`.
- New agent capabilities should be added as small, focused tool functions with clear docstrings (Gemini uses the docstring + type hints as the tool schema).
- Use clear variable names; add short comments only for non-obvious logic.

---

## Coding Workflow (please follow)

1. Before coding a new feature, briefly explain the plan and which files will change.
2. Make changes in small, reviewable steps.
3. After a change, say how to test it (e.g. run the app, send a chat, check `storage/`).
4. Ask before deleting files or making large structural changes.

---

## Current Status

> Running, plain-language history of progress: [docs/PROGRESS_LOG.md](docs/PROGRESS_LOG.md) (newest first). Add a dated entry there after finishing a chunk of work.

Done:
- [x] FastAPI app + chat/reminders/images endpoints (`main.py`)
- [x] Synthetic dataset generator (`data/generate_dummy.py`)
- [x] Random Forest training script + saved model (`training/train_model.py`, `models/disease_model.pkl`)
- [x] ML screening tool wired into the agent (`predict_disease_from_vitals`)
- [x] Gemini agent with reminders, emergency-call, image, and maker-info tools
- [x] Reminders persistence (SQLite + JSON export)
- [x] Image upload, storage, and analysis
- [x] Multilingual, voice-friendly responses with safety disclaimer
- [x] Web UI (dashboard + chat)
- [x] Bilingual UI (English / Traditional Chinese zh-TW) with a one-tap language switch, localized starter prompts, and zh-TW TTS/STT
- [x] Prediction explainability — `predict_disease_from_vitals` returns the top factors that drove the result (perturbation against clinical baselines in `core/agent.py`), and the agent verbalizes them

- [x] Research survey for real labelled data collection — consent-gated `tools/survey.py` (SQLite), `POST /api/survey` + `GET /api/survey/stats` + `GET /api/survey/export` (CSV matching the training columns), and a bilingual consent + form modal in the UI

Next (see PRD roadmap):
- [ ] Provision a persistent DB for survey data (managed Postgres) before real collection; collect, export, retrain, evaluate, compare (see `docs/DATA_COLLECTION.md`)
- [ ] Integrate a real dataset (then original Taiwan survey data)
- [ ] Add more conditions / richer features
- [ ] Broaden language support (e.g. Taiwanese Hokkien / Hakka) on top of EN + zh-TW
- [ ] Real voice (TTS/STT) and real telephony for emergency calls
- [ ] Surface the explainability factors visually in the dashboard UI

> Update this checklist as tasks get done.

---

## Notes

- The emergency-call tool is currently **simulated** (returns a success string; no real call).
- Maker/contact info lives in `tools/contacts.py`.
- Everything under `storage/` is runtime data and is gitignored.
- Keep code modular so new conditions and tools can be added without large rewrites.
