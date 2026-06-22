"""
Survey tool — collects REAL labelled data from elderly participants (or their
caregivers) to replace the synthetic dataset and properly evaluate the screening
model. See docs/DATA_COLLECTION.md for the full plan, consent/ethics rules, and
the path from survey data to a retrained model.

Design mirrors tools/reminders.py: a small SQLite store under storage/ with a
real-time JSON export, plus a CSV export whose columns match
data/elderly_synthetic_data.csv exactly so training/train_model.py can point at
it directly.

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
import sqlite3
from datetime import datetime

# Store database alongside the other runtime data in storage/.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
DB_PATH = os.path.join(STORAGE_DIR, "survey.db")
JSON_PATH = os.path.join(STORAGE_DIR, "survey.json")
CSV_PATH = os.path.join(STORAGE_DIR, "survey_export.csv")

# The label set must match the model's classes (see CLAUDE.md / MODEL_CARD.md).
VALID_CONDITIONS = {"Hypertension", "Diabetes", "Osteoarthritis", "Dementia", "Healthy"}

# Weakest -> strongest; recorded per row for honest reporting in the thesis.
VALID_LABEL_SOURCES = {"clinician", "medical_record", "self_report"}

# CSV column order must mirror data/elderly_synthetic_data.csv so the training
# script can read this export with no changes.
CSV_COLUMNS = ["Age", "Systolic_BP", "Blood_Sugar", "Joint_Pain", "Memory_Loss", "Fatigue", "Disease"]


def _get_connection():
    """Return a database connection and ensure the storage directory exists."""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _init_db():
    """Create the survey_response table if it does not exist."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS survey_response (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id      TEXT NOT NULL,
                age                 INTEGER,
                systolic_bp         INTEGER,
                blood_sugar         INTEGER,
                joint_pain          INTEGER,
                memory_loss         INTEGER,
                fatigue             INTEGER,
                diagnosed_condition TEXT NOT NULL,
                label_source        TEXT,
                consent             INTEGER NOT NULL,
                language            TEXT,
                created_at          TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


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

    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO survey_response (
                participant_id, age, systolic_bp, blood_sugar, joint_pain,
                memory_loss, fatigue, diagnosed_condition, label_source,
                consent, language, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pid, age, systolic_bp, blood_sugar, joint_pain, memory_loss,
                fatigue, condition, source, consent_flag, lang,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    except Exception as e:
        print(f"[SYSTEM] -> Error saving survey response: {e}")
        return {"ok": False, "message": f"Failed to save response: {e}", "participant_id": None}
    finally:
        conn.close()

    _sync_to_json()
    print(f"[SYSTEM] -> Survey response saved: {pid} ({condition}, source={source})")
    return {"ok": True, "message": "Response saved. Thank you for contributing to the research.", "participant_id": pid}


def _fetch_rows():
    """Return all survey rows as a list of dicts (consented rows only are stored)."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT participant_id, age, systolic_bp, blood_sugar, joint_pain,
                   memory_loss, fatigue, diagnosed_condition, label_source,
                   language, created_at
            FROM survey_response
            ORDER BY id
            """
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    keys = [
        "participant_id", "age", "systolic_bp", "blood_sugar", "joint_pain",
        "memory_loss", "fatigue", "diagnosed_condition", "label_source",
        "language", "created_at",
    ]
    return [dict(zip(keys, r)) for r in rows]


def _sync_to_json():
    """Mirror all stored responses to a JSON file (real-time snapshot)."""
    try:
        data = _fetch_rows()
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[SYSTEM] -> Error syncing survey to JSON: {e}")


def get_survey_stats() -> dict:
    """Return total count and a per-condition breakdown for monitoring balance."""
    rows = _fetch_rows()
    by_condition = {c: 0 for c in sorted(VALID_CONDITIONS)}
    for r in rows:
        by_condition[r["diagnosed_condition"]] = by_condition.get(r["diagnosed_condition"], 0) + 1
    return {"total": len(rows), "by_condition": by_condition}


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
