"""
Handles all SQLite connection and table creation for the DTR Tracker.
Every other module imports from here.
"""

import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "dtr.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id   TEXT    UNIQUE NOT NULL,
            full_name     TEXT    NOT NULL,
            department    TEXT    NOT NULL,
            position      TEXT    NOT NULL,
            pin_hash      TEXT    NOT NULL,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dtr_entries (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id   TEXT    NOT NULL,
            date          TEXT    NOT NULL,
            am_in         TEXT,
            am_out        TEXT,
            pm_in         TEXT,
            pm_out        TEXT,
            total_hours   REAL,
            status        TEXT    NOT NULL DEFAULT 'incomplete',
            is_flagged    INTEGER NOT NULL DEFAULT 0,
            flag_reason   TEXT,
            created_at    TEXT    NOT NULL,
            UNIQUE(employee_id, date),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp     TEXT    NOT NULL,
            employee_id   TEXT    NOT NULL,
            action        TEXT    NOT NULL,
            value         TEXT    NOT NULL,
            terminal      TEXT    NOT NULL DEFAULT 'MAIN',
            note          TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            dtr_entry_id    INTEGER NOT NULL,
            employee_id     TEXT    NOT NULL,
            field_corrected TEXT    NOT NULL,
            old_value       TEXT,
            new_value       TEXT    NOT NULL,
            reason          TEXT    NOT NULL,
            corrected_by    TEXT    NOT NULL,
            corrected_at    TEXT    NOT NULL,
            FOREIGN KEY (dtr_entry_id) REFERENCES dtr_entries(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supervisors (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            supervisor_id   TEXT    UNIQUE NOT NULL,
            full_name       TEXT    NOT NULL,
            department      TEXT    NOT NULL,
            pin_hash        TEXT    NOT NULL,
            is_active       INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT    NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"[OK] Database initialized at {DB_PATH}")


def log_audit(employee_id, action, value, terminal="MAIN", note=None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO audit_log (timestamp, employee_id, action, value, terminal, note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), employee_id, action, value, terminal, note))
    conn.commit()
    conn.close()


def get_today_entry(employee_id, date):
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM dtr_entries
        WHERE employee_id = ? AND date = ?
    """, (employee_id, date)).fetchone()
    conn.close()
    return row


def create_today_entry(employee_id, date):
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO dtr_entries (employee_id, date, created_at)
        VALUES (?, ?, ?)
    """, (employee_id, date, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def update_dtr_field(employee_id, date, field, value):
    allowed_fields = {"am_in", "am_out", "pm_in", "pm_out"}
    if field not in allowed_fields:
        raise ValueError(f"Invalid DTR field: {field}")
    conn = get_connection()
    conn.execute(f"""
        UPDATE dtr_entries
        SET {field} = ?, status = 'incomplete'
        WHERE employee_id = ? AND date = ?
    """, (value, employee_id, date))
    _recalculate_hours(conn, employee_id, date)
    conn.commit()
    conn.close()


def flag_entry(employee_id: str, date: str, reason: str, field: str = ""):
    conn = get_connection()
    row = conn.execute("""
        SELECT flag_reason FROM dtr_entries
        WHERE employee_id = ? AND date = ?
    """, (employee_id, date)).fetchone()

    existing = row["flag_reason"] if row and row["flag_reason"] else ""
    fields = [f.strip() for f in existing.split(",") if f.strip()]

    if field and field not in fields:
        fields.append(field)

    new_reason = ",".join(fields) if fields else reason

    conn.execute("""
        UPDATE dtr_entries
        SET is_flagged = 1, flag_reason = ?
        WHERE employee_id = ? AND date = ?
    """, (new_reason, employee_id, date))
    conn.commit()
    conn.close()


def _recalculate_hours(conn, employee_id, date):
    row = conn.execute("""
        SELECT am_in, am_out, pm_in, pm_out
        FROM dtr_entries
        WHERE employee_id = ? AND date = ?
    """, (employee_id, date)).fetchone()

    if not row:
        return

    total = 0.0
    status = "incomplete"

    try:
        if row["am_in"] and row["am_out"]:
            am_in  = datetime.strptime(row["am_in"],  "%H:%M")
            am_out = datetime.strptime(row["am_out"], "%H:%M")
            total += (am_out - am_in).seconds / 3600
        if row["pm_in"] and row["pm_out"]:
            pm_in  = datetime.strptime(row["pm_in"],  "%H:%M")
            pm_out = datetime.strptime(row["pm_out"], "%H:%M")
            total += (pm_out - pm_in).seconds / 3600
        if all([row["am_in"], row["am_out"], row["pm_in"], row["pm_out"]]):
            status = "complete"
    except Exception:
        pass

    conn.execute("""
        UPDATE dtr_entries SET total_hours = ?, status = ?
        WHERE employee_id = ? AND date = ?
    """, (round(total, 2), status, employee_id, date))


if __name__ == "__main__":
    initialize_database()