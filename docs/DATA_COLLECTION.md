# Data Collection Plan — ElderCare AI Survey

How to collect **real** data from elderly participants (and/or caregivers) to
replace the synthetic dataset and properly evaluate the screening model. This is
the plan referenced in [MODEL_CARD.md](MODEL_CARD.md) §6 and the roadmap.

> Why this matters: the current model reaches 100% accuracy only because the
> synthetic data is perfectly separable. Real, noisy, labelled data is required
> for a meaningful evaluation — this is the core empirical contribution of the
> thesis.

---

## 1. What we are collecting

For each participant, one record pairing **the same inputs the model uses** with
the **ground-truth condition** (the ML "label"):

| Field | Type | Source | Notes |
|---|---|---|---|
| `participant_id` | string | auto | Random/opaque ID — **no names** |
| `age` | int | participant | 60–95 target range |
| `systolic_bp` | int | measured | mmHg |
| `blood_sugar` | int | measured | mg/dL, fasting if possible |
| `joint_pain` | 0/1 | participant | self-report |
| `memory_loss` | 0/1 | participant/caregiver | self/caregiver report |
| `fatigue` | 0/1 | participant | self-report |
| `diagnosed_condition` | category | **clinician / medical record** | the **ground-truth label** — see §2 |
| `consent` | bool | participant | must be `true` to store |
| `timestamp` | datetime | auto | |
| `language` | en / zh-TW | UI | for sub-group analysis |

The label set should match the model's classes: `Hypertension`, `Diabetes`,
`Osteoarthritis`, `Dementia`, `Healthy` (extend later as needed).

---

## 2. The ground-truth label (most important point)

A supervised model can only be evaluated against **trusted labels**. The
`diagnosed_condition` must come from a reliable source, **not** from the model's
own prediction (that would be circular and invalidate the thesis).

Acceptable sources, best first:
1. A clinician's diagnosis / existing medical record for the participant.
2. A standardized screening instrument administered by a qualified person.
3. Self-reported *existing diagnosis* (weakest; record that it is self-reported).

Never store the model's prediction into the `diagnosed_condition` field.

---

## 3. Consent & ethics (do this before collecting anything)

Collecting health data from elderly people is **sensitive personal data**.

- Obtain **ethics / IRB approval** from your university before any real
  collection. Keep the approval reference with your thesis.
- Present a clear **consent screen**: who you are, purpose (academic research),
  what is collected, that it is voluntary, that they can withdraw, how data is
  stored, and how long it is kept. Store data **only if `consent = true`**.
- **Minimize and de-identify:** no names, addresses, phone numbers, or photos of
  faces tied to records. Use an opaque `participant_id`.
- Follow Taiwan's **Personal Data Protection Act (PDPA)** and your institution's
  rules. For minors or those unable to consent, use a legal guardian's consent.
- Store the data in a private location with restricted access; never commit real
  participant data to git.

> The app already shows a medical disclaimer on results — keep that. The screening
> output shown to participants is still **not** a diagnosis.

---

## 4. How it fits the app (suggested implementation)

A small, focused addition — no MCP needed, just FastAPI + a database table.

1. **New endpoint** `POST /api/survey` accepting the fields in §1.
2. **New tool/module** `tools/survey.py` (mirrors the style of `tools/reminders.py`)
   that validates consent and writes one row.
3. **Storage:** write to a **persistent external database** (see
   [DEPLOYMENT.md](DEPLOYMENT.md) §6 — the free-tier disk is ephemeral and will
   lose data). A managed Postgres (Render/Supabase free tier) is recommended.
4. **A simple survey form** in the UI (or a separate page) with the consent screen.

Suggested table schema (Postgres):

```sql
CREATE TABLE survey_response (
  id                  SERIAL PRIMARY KEY,
  participant_id      TEXT NOT NULL,
  age                 INT,
  systolic_bp         INT,
  blood_sugar         INT,
  joint_pain          SMALLINT,
  memory_loss         SMALLINT,
  fatigue             SMALLINT,
  diagnosed_condition TEXT,        -- ground-truth label
  consent             BOOLEAN NOT NULL,
  language            TEXT,
  created_at          TIMESTAMPTZ DEFAULT now()
);
```

---

## 5. Target sample size

- Aim for a **balanced** spread across the five conditions; class imbalance hurts
  the minority classes (Dementia is already the smallest in the synthetic set).
- As a rough guide, target at least a few dozen labelled records **per class**
  for a first real evaluation; more is better. State your actual achieved numbers
  honestly in the thesis.

---

## 6. From survey data to a retrained model

1. **Export** the `survey_response` table to a CSV with the same columns as
   `data/elderly_synthetic_data.csv` (rename `diagnosed_condition` → `Disease`,
   match the feature column names/casing).
2. **Point training at the real CSV** (or merge real + synthetic and add a
   `source` flag for analysis).
3. **Retrain:** `python -m training.train_model`.
4. **Evaluate honestly** on a held-out *real* test split — expect accuracy well
   below 100%. Report precision/recall/F1 **per class**, plus a confusion matrix.
5. **Compare** synthetic-only vs real-data models — this comparison is a strong
   results section for the thesis.

---

## 7. Checklist

- [ ] IRB / ethics approval obtained
- [x] Consent screen written (EN + zh-TW) and wired to store only on consent
- [x] Ground-truth labelling source captured per row (`label_source`: clinician / medical_record / self_report)
- [x] Code supports a persistent database — `tools/survey.py` switches between local SQLite (default) and managed Postgres via the `DATABASE_URL` env var, no code change needed
- [ ] Persistent database **provisioned** (not ephemeral disk) — set `DATABASE_URL` to a managed Postgres (Supabase free) before real collection (see [DEPLOYMENT.md](DEPLOYMENT.md) §6.1)
- [x] `/api/survey` endpoint + `tools/survey.py` implemented (plus `GET /api/survey/stats` and `GET /api/survey/export`)
- [ ] Pilot test with a few records, verify rows persist across a redeploy
- [ ] Collect, export, retrain, evaluate, compare

> **Implementation notes.** `tools/survey.py` stores rows only when `consent` is
> true, validates the label against the model's five classes, records the label
> source, and de-identifies with an opaque `participant_id` (no names). The
> `GET /api/survey/export` CSV uses the exact column names/casing of
> `data/elderly_synthetic_data.csv` (`diagnosed_condition` → `Disease`), so
> `python -m training.train_model` can point at it directly per §6.
>
> **Storage backend.** Persistence goes through SQLAlchemy and is selected by the
> `DATABASE_URL` env var: unset → local SQLite at `storage/survey.db` (dev); set
> to a Postgres URL → that managed database (production, survives redeploys). The
> `survey_response` table is created automatically on startup. See
> [DEPLOYMENT.md](DEPLOYMENT.md) §6.1 for the Supabase setup.
