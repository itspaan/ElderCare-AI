# Product Requirements Document (PRD) — ElderCare AI

> A conversational **Machine Learning + LLM** health companion that helps elderly people and their caregivers screen for common chronic conditions and manage daily care, explained in plain, spoken-friendly language.

---

## 1. Overview

**ElderCare AI** is a caring, voice-friendly assistant for elderly users and their families. It is designed around the **common chronic conditions of Taiwan's ageing population**, where a fast-growing share of older adults live with one or more of these diseases and often rely on family members for daily care. It combines two AI components inside a single conversational agent:

- **Machine Learning model** — a Random Forest classifier that screens for a likely condition (Hypertension, Diabetes, Osteoarthritis, Dementia, or Healthy) from basic vitals and symptoms (age, blood pressure, blood sugar, joint pain, memory loss, fatigue).
- **LLM (Google Gemini)** — an agent with tool/function calling that interprets the ML result, holds a natural conversation, and performs helpful actions (set reminders, call an emergency contact, analyze uploaded images).

The assistant is **bilingual (English and Traditional Chinese, zh-TW)** with a one-tap language switch in the UI, and additionally detects the user's typed language and replies in kind — using short, warm sentences that sound natural when read aloud by a text-to-speech engine. This reflects the everyday Taiwan setting, where elders are most comfortable in Mandarin while caregivers and clinicians may switch between Mandarin and English.

> **Important:** ElderCare AI is a **screening and daily-care aid, not a medical diagnosis.** Every health result includes a disclaimer encouraging the user to consult a healthcare professional.

---

## 2. Problem Statement

- Taiwan is an **aged society** (over 14% of the population is 65+), so chronic conditions like hypertension, diabetes, osteoarthritis, and dementia are increasingly common among elders.
- Elderly users and non-medical caregivers struggle to interpret raw health numbers.
- Many older users find typing and complex interfaces difficult; they need conversational, spoken-friendly interaction.
- Most AI health tools output technical scores with no plain-language guidance and no follow-up actions.
- Tools are often English-only and ignore the user's preferred language — for Taiwan elders, a **Mandarin-first** experience is essential.

**Result:** early warning signs are missed and daily care tasks (e.g. taking medicine on time) slip. We need an assistant that is accurate, understandable, bilingual (English / Mandarin), and able to *act*.

---

## 3. Goals

1. Screen for common Taiwan elderly conditions from simple vitals/symptoms.
2. Explain results in warm, plain language that works when spoken aloud.
3. Serve users bilingually in **English and Mandarin Chinese** via a UI language switch, and auto-detect the typed language to reply in kind.
4. Help with daily care: medicine reminders, emergency contact, image/report analysis.
5. Keep the architecture modular so new conditions, tools, and languages can be added.

### Success Criteria
- ML model reaches strong accuracy/F1 on the evaluation split.
- Non-technical users can understand the spoken explanation without help.
- The agent correctly chooses and runs the right tool for a given request.
- Reminders and image records persist reliably across restarts.

---

## 4. Scope

### In Scope (current)
- Conversational health agent powered by Gemini with function calling.
- Multi-condition ML screening (Hypertension, Diabetes, Osteoarthritis, Dementia, Healthy).
- Medicine reminders (create, list, delete) persisted to SQLite + JSON export.
- Emergency-contact call action.
- Image upload, storage, and analysis (e.g. health reports, medicine bottles).
- Bilingual English / Mandarin UI with a one-tap language switch, plus automatic language detection for replies, optimized for text-to-speech.
- Web UI (dashboard + chat) served by FastAPI.
- Safety disclaimer on all health responses.

### Out of Scope (for now)
- Real medical diagnosis or treatment prescriptions.
- Clinical-grade datasets and hospital/EHR integration.
- Live telephony (the emergency-call tool is simulated).
- Native mobile apps.

---

## 5. Target Users

| User | Needs |
|------|-------|
| **Elderly person** (primary, Taiwan) | Talk naturally in Mandarin, hear simple spoken answers, get reminders and reassurance. |
| **Caregiver / family** | Understand the elder's health signals in Mandarin or English; rely on reminders and emergency contact. |
| **Researcher (you)** | Train/evaluate the model; extend conditions, tools, languages, and (later) real Taiwan data. |

---

## 6. Key Features

1. **Conversational Health Agent** — natural chat; the agent decides when to screen, remind, call, or analyze an image.
2. **ML Health Screening** — `predict_disease_from_vitals` returns a predicted condition + confidence and standard care guidance.
3. **Medicine Reminders** — create / list / delete reminders, persisted to SQLite (`storage/reminders.db`) with a live JSON export (`storage/reminders.json`).
4. **Emergency Contact** — initiate a (simulated) call to a family member or emergency contact.
5. **Image Analysis & Storage** — user uploads an image; it is saved to `storage/images/`, recorded in `storage/images_db.json`, and passed to Gemini for analysis.
6. **Bilingual, Voice-Friendly Interface** — a top-left language switch toggles the entire UI between English and Mandarin Chinese (and remembers the choice); the agent also detects the typed input language and replies in kind, with short plain-text sentences suited for TTS. Text-to-speech and speech input follow the selected language (Traditional Chinese `zh-TW` voice for Mandarin, as used in Taiwan).
7. **Safety Disclaimer** — every health result reminds the user this is an AI screening aid, not a diagnosis.

---

## 7. User Flow

1. User opens the web app and types or speaks a message (optionally attaching an image).
2. The Gemini agent interprets intent and calls the appropriate tool:
   - Health complaint → `predict_disease_from_vitals` (asks for missing vitals first).
   - "Remind me…" → reminders tool.
   - "Call my family" → emergency-contact tool.
   - Image attached → save + analyze.
3. The agent composes a warm, plain-language reply in the user's language.
4. Health replies always include the safety disclaimer.

---

## 8. System Architecture

```
Browser (static/index.html)
        │  POST /api/chat  (text + optional base64 image)
        ▼
FastAPI (main.py)
        │
        ▼
Gemini Agent (core/agent.py + core/prompts.py)
   ├─ predict_disease_from_vitals ──► Random Forest (models/disease_model.pkl)
   ├─ reminders tool ──────────────► SQLite + JSON (storage/)
   ├─ emergency-contact tool
   ├─ image storage + analysis ────► storage/images/ + images_db.json
   └─ maker-info tool
```

- **Backend / API:** FastAPI served by Uvicorn (`main.py`).
- **Agent:** `core/agent.py` builds a Gemini chat session with tools; `core/prompts.py` holds the system prompt.
- **Tools:** `tools/reminders.py`, `tools/contacts.py`, `tools/image_storage.py`.
- **ML:** `training/train_model.py` trains and saves `models/disease_model.pkl`.
- **Data:** `data/generate_dummy.py` generates `data/elderly_synthetic_data.csv`.
- **Frontend:** `static/index.html` (dashboard + chat UI).

---

## 9. ML Model & Data

- **Algorithm:** Random Forest classifier (scikit-learn).
- **Features:** `Age, Systolic_BP, Blood_Sugar, Joint_Pain, Memory_Loss, Fatigue`.
- **Target:** `Disease` ∈ {Hypertension, Diabetes, Osteoarthritis, Dementia, Healthy}.
- **Current data:** synthetic dataset (`data/generate_dummy.py`) for reproducible training and demos.
- **Planned:** replace/augment with a real public dataset and, later, original survey data (see Roadmap). The synthetic schema is intentionally simple so it can map onto richer real data.

---

## 10. Tech Stack

- **Language:** Python 3
- **Backend:** FastAPI + Uvicorn
- **LLM:** Google Gemini (`gemini-2.5-flash`) via `google-genai`, with function calling
- **ML:** scikit-learn (Random Forest), pandas, numpy
- **Storage:** SQLite + JSON files under `storage/`
- **Frontend:** plain HTML/CSS/JS (`static/index.html`)
- **Config:** `.env` with `GEMINI_API_KEY` (loaded via `python-dotenv`)

---

## 11. Safety & Disclaimers

- ElderCare AI is a screening and care aid, **not** a medical diagnosis.
- Every health result must include a disclaimer and encourage contacting a doctor or family member if symptoms persist or worsen.
- The model output is probabilistic; confidence is shown but never presented as certainty.

---

## 12. Future Roadmap

- Integrate a real public dataset, then original Taiwan elderly survey data.
- Add more conditions and richer features (modular model design).
- Broaden language support (e.g. Taiwanese Hokkien / Hakka) on top of the current English + Traditional Chinese (zh-TW), with localized TTS/STT voices.
- Real text-to-speech / speech-to-text voice mode.
- Real telephony for the emergency-contact action.
- Explainability: show which vitals/symptoms drove a prediction.
- Mobile-friendly UI.
