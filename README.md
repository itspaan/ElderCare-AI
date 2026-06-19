# ElderCare AI

A conversational **Machine Learning + LLM** health companion for **Taiwan's elderly** and their caregivers. A Google Gemini agent screens for likely conditions (Hypertension, Diabetes, Osteoarthritis, Dementia, Healthy) from basic vitals, manages medicine reminders, calls an emergency contact, and analyzes uploaded images. The interface is **bilingual — English and Traditional Chinese (zh-TW)** — with a one-tap language switch, and the agent replies in the user's language with short, voice-friendly sentences.

> ⚠️ **Screening and care aid, not a medical diagnosis.** Always consult a healthcare professional.

## Quick Start

```powershell
# 1. Activate the virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Gemini key in .env
#    GEMINI_API_KEY=your_key_here

# 4. (First time) generate data and train the model
python -m data.generate_dummy
python -m training.train_model

# 5. Run the app
python -m uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000. To chat in the terminal instead: `python -m core.agent`.

## Project Layout

| Path | Purpose |
|------|---------|
| `main.py` | FastAPI app + API routes |
| `core/agent.py` | Gemini chat session, tools, ML inference |
| `core/prompts.py` | Agent system prompt |
| `tools/` | Reminders, contacts, image storage |
| `training/train_model.py` | Trains the Random Forest model |
| `data/` | Dataset generator + CSV |
| `models/disease_model.pkl` | Saved model |
| `static/index.html` | Web UI |
| `storage/` | Runtime data (gitignored) |

## Documentation

- [`docs/PRD.md`](docs/PRD.md) — product requirements.
- [`CLAUDE.md`](CLAUDE.md) — context and conventions for working on the code.
