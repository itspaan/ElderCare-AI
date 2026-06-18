"""
Reminders tool — persists medicine reminders to a SQLite database.
"""

import os
import json
import sqlite3
from datetime import datetime

# Store database in storage/reminders.db at the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
DB_PATH = os.path.join(STORAGE_DIR, "reminders.db")
JSON_PATH = os.path.join(STORAGE_DIR, "reminders.json")


def _get_connection():
    """Return a database connection and ensure directory exists."""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _init_db():
    """Initialize the database tables and perform migration from JSON if needed."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_name TEXT NOT NULL,
                time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
            """
        )
        conn.commit()

        # One-time migration from the legacy reminders.json.
        #
        # NOTE: reminders.json is reused as a live export by _sync_to_json(),
        # so its mere existence is NOT a reliable "needs migration" signal —
        # it gets recreated after every add/delete. Gate the migration on the
        # DB table being empty instead, otherwise every restart would re-import
        # (and duplicate) all reminders and then crash on the .bak rename.
        cursor.execute("SELECT COUNT(*) FROM reminders")
        table_is_empty = cursor.fetchone()[0] == 0

        if table_is_empty and os.path.exists(JSON_PATH):
            try:
                with open(JSON_PATH, "r", encoding="utf-8") as f:
                    old_reminders = json.load(f)

                if old_reminders:
                    print("\n[SYSTEM] -> Migrating existing reminders from reminders.json to SQLite database...")
                    for r in old_reminders:
                        cursor.execute(
                            """
                            INSERT INTO reminders (medicine_name, time, created_at, active)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                r["medicine_name"],
                                r["time"],
                                r.get("created_at", datetime.now().isoformat()),
                                1 if r.get("active", True) else 0
                            )
                        )
                    conn.commit()

                    # Keep a one-time backup of the legacy file. os.replace
                    # overwrites an existing .bak atomically (os.rename does not
                    # on Windows), then re-export so the live JSON matches the DB.
                    os.replace(JSON_PATH, JSON_PATH + ".bak")
                    print(f"[SYSTEM] -> Migration completed. Backup saved at {JSON_PATH}.bak")
                    _sync_to_json()
            except Exception as e:
                print(f"[SYSTEM] -> Error migrating data from JSON: {e}")
    finally:
        conn.close()


def _sync_to_json():
    """Sync all reminders from the SQLite database to a JSON file in real-time."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, medicine_name, time, created_at, active FROM reminders")
        rows = cursor.fetchall()
        data = []
        for r in rows:
            data.append({
                "id": r[0],
                "medicine_name": r[1],
                "time": r[2],
                "created_at": r[3],
                "active": bool(r[4])
            })
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"\n[SYSTEM] -> Synced reminders to JSON.")
    except Exception as e:
        print(f"[SYSTEM] -> Error syncing to JSON: {e}")
    finally:
        conn.close()


def add_reminder(medicine_name: str, time: str) -> str:
    """Add a new medicine reminder and persist it to the SQLite database.

    Args:
        medicine_name: Name of the medicine or activity.
        time: Time for the reminder (e.g. '9 AM', '08:00').

    Returns:
        A success message string.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reminders (medicine_name, time, created_at, active)
            VALUES (?, ?, ?, 1)
            """,
            (medicine_name, time, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        print(f"[SYSTEM] -> Error saving reminder to database: {e}")
        return f"Error: Failed to save reminder. Details: {e}"
    finally:
        conn.close()

    _sync_to_json()
    print(f"\n[SYSTEM] -> Reminder saved to database: {medicine_name} at {time}")
    return f"Success: Reminder set for '{medicine_name}' at {time}. (Saved to SQLite database)"


def get_all_reminders() -> str:
    """Retrieve all active reminders from the database as a formatted string.

    Returns:
        A formatted string listing all active reminders, or a message if none exist.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT medicine_name, time 
            FROM reminders 
            WHERE active = 1
            """
        )
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[SYSTEM] -> Error reading reminders from database: {e}")
        return f"Error: Failed to fetch reminders. Details: {e}"
    finally:
        conn.close()

    if not rows:
        return "You have no active reminders."

    lines = []
    for row in rows:
        lines.append(f"- {row[0]} at {row[1]}")
    return "Your active reminders:\n" + "\n".join(lines)


def delete_reminder(medicine_name: str) -> str:
    """Deactivate a reminder in the database by medicine name.

    Args:
        medicine_name: The name of the medicine/activity to remove.

    Returns:
        A success or not-found message string.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if the reminder exists and is active
        cursor.execute(
            """
            SELECT id FROM reminders 
            WHERE LOWER(medicine_name) = LOWER(?) AND active = 1
            """,
            (medicine_name,)
        )
        rows = cursor.fetchall()
        
        if not rows:
            return f"No active reminder found for '{medicine_name}'."

        # Mark them as inactive
        cursor.execute(
            """
            UPDATE reminders 
            SET active = 0 
            WHERE LOWER(medicine_name) = LOWER(?) AND active = 1
            """,
            (medicine_name,)
        )
        conn.commit()
        _sync_to_json()
        print(f"\n[SYSTEM] -> Reminder removed from database: {medicine_name}")
        return f"Success: Reminder for '{medicine_name}' has been removed."
    except Exception as e:
        print(f"[SYSTEM] -> Error deleting reminder from database: {e}")
        return f"Error: Failed to delete reminder. Details: {e}"
    finally:
        conn.close()


# Run DB initialization when the module is imported (defined last so it can
# reference _sync_to_json during a one-time migration).
_init_db()
