"""
Survey tool — collects REAL labelled data from elderly participants (or their
caregivers) to replace the synthetic dataset and properly evaluate the screening
model. See docs/DATA_COLLECTION.md for the full plan, consent/ethics rules, and
the path from survey data to a retrained model.

Persistence is backed by SQLAlchemy so the SAME code runs on either:
  * SQLite (default, local dev) — a file under storage/, like reminders.py; or
  * managed Postgres (production) — set DATABASE_URL, and survey data survives
    redeploys on an ephemeral host. See docs/DEPLOYMENT.md §6.

A real-time JSON mirror and a CSV export (columns matching
data/elderly_synthetic_data.csv) are still written to storage/ so training and
quick inspection work as before; with Postgres the database is the source of
truth and those files are regenerated on demand.

Two rules from the data-collection plan are enforced here:
  1. Store a row ONLY if consent is true (sensitive personal data).
  2. Never let the model's own prediction become the ground-truth label — the
     diagnosed_condition must come from the caller (clinician / record / self
     report), and we record its source.
"""

import os
import csv
import json
import uuid
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, insert, select, func,
)

# Load .env so DATABASE_URL is available even when this module is imported on its
# own (e.g. a direct test), not only through main.py / core.agent.
load_dotenv()

# JSON/CSV mirrors live alongside the other runtime data in storage/.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
JSON_PATH = os.path.join(STORAGE_DIR, "survey.json")
CSV_PATH = os.path.join(STORAGE_DIR, "survey_export.csv")

# The label set must match the model's classes (see CLAUDE.md / MODEL_CARD.md).
VALID_CONDITIONS = {"Hypertension", "Diabetes", "Osteoarthritis", "Dementia", "Healthy"}

# Weakest -> strongest; recorded per row for honest reporting in the thesis.
VALID_LABEL_SOURCES = {"clinician", "medical_record", "self_report"}

# CSV column order must mirror data/elderly_synthetic_data.csv so the training
# script can read this export with no changes.
CSV_COLUMNS = ["Age", "Systolic_BP", "Blood_Sugar", "Joint_Pain", "Memory_Loss", "Fatigue", "Disease"]


def _database_url() -> str:
    """Pick the database backend from the environment.

    Returns DATABASE_URL when set (managed Postgres in production), otherwise a
    local SQLite file under storage/ so development needs no extra services.
    Normalizes the legacy ``postgres://`` scheme some hosts hand out to the
    ``postgresql://`` form SQLAlchemy expects.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        return "sqlite:///" + os.path.join(STORAGE_DIR, "survey.db")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


DATABASE_URL = _database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

# One engine per process. pool_pre_ping recycles connections dropped by managed
# Postgres (Supabase/serverless idle timeouts) so the first request after an
# idle period doesn't fail.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

metadata = MetaData()
survey_response = Table(
    "survey_response", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("participant_id", String, nullable=False),
    Column("age", Integer),
    Column("systolic_bp", Integer),
    Column("blood_sugar", Integer),
    Column("joint_pain", Integer),
    Column("memory_loss", Integer),
    Column("fatigue", Integer),
    Column("diagnosed_condition", String, nullable=False),
    Column("label_source", String),
    Column("consent", Integer, nullable=False),
    Column("language", String),
    Column("created_at", String, nullable=False),
)


def _init_db():
    """Create the survey_response table if it does not exist."""
    metadata.create_all(engine)


def _coerce_binary(value, field_name):
    """Coerce a 0/1-ish value (0/1, '0'/'1', bool, 'yes'/'no') to 0 or 1."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) == 1 else 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "y"):
            return 1
        if v in ("0", "false", "no", "n", ""):
            return 0
    raise ValueError(f"{field_name} must be 0 or 1 (got {value!r}).")


def save_survey_response(
    age,
    systolic_bp,
    blood_sugar,
    joint_pain,
    memory_loss,
    fatigue,
    diagnosed_condition: str,
    consent,
    label_source: str = "self_report",
    language: str = "en",
    participant_id: str = None,
) -> dict:
    """Validate and persist one labelled survey record.

    The diagnosed_condition is the ground-truth ML label and must come from the
    caller (clinician / medical record / self report) — never from the model's
    own prediction. The row is stored only when consent is true.

    Returns a dict: {"ok": bool, "message": str, "participant_id": str | None}.
    """
    # 1. Consent gate — refuse to store anything without explicit consent.
    consent_flag = _coerce_binary(consent, "consent")
    if consent_flag != 1:
        return {"ok": False, "message": "Consent is required; nothing was stored.", "participant_id": None}

    # 2. Validate the ground-truth label and its source.
    condition = (diagnosed_condition or "").strip().title()
    if condition not in VALID_CONDITIONS:
        return {
            "ok": False,
            "message": f"diagnosed_condition must be one of {sorted(VALID_CONDITIONS)}.",
            "participant_id": None,
        }
    source = (label_source or "self_report").strip().lower()
    if source not in VALID_LABEL_SOURCES:
        return {
            "ok": False,
            "message": f"label_source must be one of {sorted(VALID_LABEL_SOURCES)}.",
            "participant_id": None,
        }

    # 3. Validate / coerce the feature fields.
    try:
        age = int(age)
        systolic_bp = int(systolic_bp)
        blood_sugar = int(blood_sugar)
        joint_pain = _coerce_binary(joint_pain, "joint_pain")
        memory_loss = _coerce_binary(memory_loss, "memory_loss")
        fatigue = _coerce_binary(fatigue, "fatigue")
    except (TypeError, ValueError) as e:
        return {"ok": False, "message": f"Invalid input: {e}", "participant_id": None}

    # Loose sanity ranges — catch typos without rejecting real outliers.
    if not (40 <= age <= 120):
        return {"ok": False, "message": "age looks out of range (expected 40-120).", "participant_id": None}
    if not (60 <= systolic_bp <= 260):
        return {"ok": False, "message": "systolic_bp looks out of range (expected 60-260).", "participant_id": None}
    if not (40 <= blood_sugar <= 600):
        return {"ok": False, "message": "blood_sugar looks out of range (expected 40-600).", "participant_id": None}

    # 4. Opaque, de-identified participant id (no names anywhere — see plan §3).
    pid = participant_id or ("P-" + uuid.uuid4().hex[:10])
    lang = "zh-TW" if str(language).lower().startswith("zh") else "en"

    try:
        with engine.begin() as conn:
            conn.execute(
                insert(survey_response).values(
                    participant_id=pid,
                    age=age,
                    systolic_bp=systolic_bp,
                    blood_sugar=blood_sugar,
                    joint_pain=joint_pain,
                    memory_loss=memory_loss,
                    fatigue=fatigue,
                    diagnosed_condition=condition,
                    label_source=source,
                    consent=consent_flag,
                    language=lang,
                    created_at=datetime.now().isoformat(),
                )
            )
    except Exception as e:
        print(f"[SYSTEM] -> Error saving survey response: {e}")
        return {"ok": False, "message": f"Failed to save response: {e}", "participant_id": None}

    _sync_to_json()
    print(f"[SYSTEM] -> Survey response saved: {pid} ({condition}, source={source})")
    return {"ok": True, "message": "Response saved. Thank you for contributing to the research.", "participant_id": pid}


def _fetch_rows():
    """Return all survey rows as a list of dicts (consented rows only are stored)."""
    stmt = select(
        survey_response.c.participant_id,
        survey_response.c.age,
        survey_response.c.systolic_bp,
        survey_response.c.blood_sugar,
        survey_response.c.joint_pain,
        survey_response.c.memory_loss,
        survey_response.c.fatigue,
        survey_response.c.diagnosed_condition,
        survey_response.c.label_source,
        survey_response.c.language,
        survey_response.c.created_at,
    ).order_by(survey_response.c.id)
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    # ._mapping turns each Row into a dict keyed by the selected column names.
    return [dict(r._mapping) for r in rows]


def _sync_to_json():
    """Mirror all stored responses to a JSON file (real-time snapshot)."""
    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        data = _fetch_rows()
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[SYSTEM] -> Error syncing survey to JSON: {e}")


def get_survey_stats() -> dict:
    """Return total count and a per-condition breakdown for monitoring balance."""
    by_condition = {c: 0 for c in sorted(VALID_CONDITIONS)}
    stmt = select(
        survey_response.c.diagnosed_condition,
        func.count().label("n"),
    ).group_by(survey_response.c.diagnosed_condition)
    total = 0
    with engine.connect() as conn:
        for condition, n in conn.execute(stmt).all():
            by_condition[condition] = by_condition.get(condition, 0) + n
            total += n
    return {"total": total, "by_condition": by_condition}


def export_survey_csv() -> str:
    """Write all responses to a CSV whose columns match the training dataset.

    Maps diagnosed_condition -> Disease and matches the feature column
    names/casing of data/elderly_synthetic_data.csv, so training/train_model.py
    can read this file with no changes.

    Returns the path to the written CSV.
    """
    rows = _fetch_rows()
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for r in rows:
            writer.writerow([
                r["age"], r["systolic_bp"], r["blood_sugar"], r["joint_pain"],
                r["memory_loss"], r["fatigue"], r["diagnosed_condition"],
            ])
    print(f"[SYSTEM] -> Exported {len(rows)} survey rows to {CSV_PATH}")
    return CSV_PATH


# Initialize the database when the module is imported.
_init_db()
