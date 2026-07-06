"""
PIN hashing and verification.
Uses bcrypt, PINs are never stored in plain text.
"""

import bcrypt
from core.database import get_connection


def hash_pin(plain_pin: str) -> str:
    return bcrypt.hashpw(plain_pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(plain_pin: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain_pin.encode(), hashed.encode())
    except Exception:
        return False


def authenticate_employee(employee_id: str, plain_pin: str):
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM employees
        WHERE employee_id = ? AND is_active = 1
    """, (employee_id,)).fetchone()
    conn.close()

    if not row:
        return None
    if verify_pin(plain_pin, row["pin_hash"]):
        return row
    return None


def authenticate_supervisor(supervisor_id: str, plain_pin: str):
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM supervisors
        WHERE supervisor_id = ? AND is_active = 1
    """, (supervisor_id,)).fetchone()
    conn.close()

    if not row:
        return None
    if verify_pin(plain_pin, row["pin_hash"]):
        return row
    return None


def authenticate_admin(plain_pin: str) -> bool:
    conn = get_connection()
    row = conn.execute("""
        SELECT value FROM audit_log
        WHERE action = 'ADMIN_PIN_SET'
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()

    if row:
        return verify_pin(plain_pin, row["value"])

    # Default admin PIN is 0000 if none has been set yet
    return plain_pin == "0000"