# Architecture — ElderCare AI

How the system is put together: components, request flow, and the key design
decisions (and trade-offs) behind them.

---

## 1. High-level overview

ElderCare AI is a conversational health companion. A web UI sends the user's
message (and optional image) to a FastAPI backend. The backend forwards it to a
Google Gemini agent that holds the conversation and, when needed, calls Python
**tools** — including a scikit-learn model for health screening.

```
┌─────────────────────────────┐
│   Browser (static/index.html)│   plain HTML/CSS/JS, bilingual EN / zh-TW
│   - chat UI + dashboard      │   TTS/STT in the browser
└──────────────┬──────────────┘
               │  HTTP JSON  (POST /api/chat: text + optional base64 image)
               ▼
┌─────────────────────────────┐
│   FastAPI app (main.py)      │   routes, request parsing, logging
│   /  /api/chat  /api/health  │
│   /api/reminders  /api/images│
└──────────────┬──────────────┘
               │  chat_with_agent(text, image_bytes, mime)
               ▼
┌─────────────────────────────┐
│   Agent (core/agent.py)      │   Gemini chat session + tool registry
│   system prompt: prompts.py  │
└──────┬───────────────┬───────┘
       │ function call │ generates reply
       ▼               ▼
┌──────────────┐   ┌──────────────────────────┐
│  Tools       │   │  Google Gemini           │
│  tools/*.py  │   │  (gemini-2.5-flash)      │
│  + ML tool   │   │  decides when to call a  │
└──────┬───────┘   │  tool from its docstring │
       │           └──────────────────────────┘
       ▼
┌─────────────────────────────┐     ┌────────────────────────────┐
│  ML model                   │     │  storage/ (runtime data)    │
│  models/disease_model.pkl   │     │  reminders.db (SQLite)      │
│  Random Forest, sklearn     │     │  images/ + *.json exports   │
└─────────────────────────────┘     └────────────────────────────┘
```

---

## 2. Components

| Component | File(s) | Responsibility |
|---|---|---|
| **Web UI** | `static/index.html` | Chat + dashboard, bilingual EN/zh-TW, browser TTS/STT |
| **API layer** | `main.py` | FastAPI routes, request/response, logging, serves UI + images |
| **Agent** | `core/agent.py` | Gemini chat session, tool registration, ML inference, explainability |
| **Prompt** | `core/prompts.py` | System instruction (voice-friendly, bilingual, safety rules) |
| **Tools** | `tools/reminders.py`, `tools/contacts.py`, `tools/image_storage.py` | Discrete agent capabilities |
| **ML training** | `training/train_model.py` | Trains Random Forest → `models/disease_model.pkl` |
| **Data** | `data/generate_dummy.py`, `*.csv` | Synthetic dataset (to be replaced by real data) |
| **Storage** | `storage/` (gitignored) | SQLite DB, uploaded images, JSON exports |

---

## 3. Request flow (a health-screening chat)

1. User types/speaks a symptom in the browser → `POST /api/chat` with the text.
2. `main.py` decodes any image and calls `chat_with_agent(...)`.
3. The Gemini session reads the message. The system prompt instructs it to call
   `predict_disease_from_vitals` for health complaints, asking for age / BP /
   blood sugar first if missing.
4. Gemini issues a **function call**; the agent runs the Python tool:
   - builds a one-row DataFrame in the trained feature order,
   - runs `model.predict` / `predict_proba`,
   - computes the **key factors** (explainability),
   - returns prediction + confidence + factors + advice as a string.
5. Gemini turns that into a short, warm, plain-text reply in the user's language,
   including the safety disclaimer, and returns it.
6. `main.py` sends `{"reply": ...}` back to the browser, which displays and
   optionally speaks it.

---

## 4. Key design decisions & trade-offs

### Function calling, **not** MCP
The agent's tools are plain Python functions registered directly with Gemini,
which reads each function's **docstring + type hints** as the tool schema.

- **Why:** the tools live *inside* this application and operate on local data
  (SQLite, the local model, the filesystem). Function calling is the simplest
  correct fit.
- **Why not MCP:** the Model Context Protocol is for exposing tools across a
  process/network boundary to multiple AI clients. We have no such boundary, so
  MCP would add a server, a protocol, and operational overhead with no benefit.
- **When MCP *would* make sense (future):** if these tools needed to be reused by
  other, separate AI clients, or run as an independent service.

### Random Forest for screening
- **Why:** small tabular dataset, fast training/inference, naturally multi-class,
  and supports simple explainability. No GPU needed; the artifact is tiny.
- **Trade-off:** with the current synthetic data the problem is trivially
  separable (see MODEL_CARD.md §6). Real data is needed for a meaningful model.

### Plain HTML/JS frontend (no framework)
- **Why:** one screen, simple state; keeps the project approachable and avoids a
  build step. Bilingual strings live in a `translations` table keyed by `data-i18n`.
- **Trade-off:** less structure than React/Vue; acceptable at this scope.

### FastAPI + Uvicorn
- **Why:** async, minimal boilerplate, **auto-generated API docs** at `/docs`,
  Pydantic request validation.

### SQLite + JSON files for storage
- **Why:** zero-config, file-based, fine for a single-instance prototype.
- **Trade-off:** not suitable for multi-instance or persistent cloud hosting on
  ephemeral disks — see [DEPLOYMENT.md](DEPLOYMENT.md) and
  [DATA_COLLECTION.md](DATA_COLLECTION.md).

---

## 5. Configuration & secrets

- `GEMINI_API_KEY` is read from the environment (loaded from `.env` locally via
  `python-dotenv`). It is **never** hardcoded. In cloud hosting it is set as an
  environment variable in the platform dashboard.

## 6. Related documents

- [PRD.md](PRD.md) — product requirements.
- [MODEL_CARD.md](MODEL_CARD.md) — the ML model in detail.
- [DEPLOYMENT.md](DEPLOYMENT.md) — hosting for real users.
- [DATA_COLLECTION.md](DATA_COLLECTION.md) — survey plan for real data.
