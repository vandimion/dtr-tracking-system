"""
Populates the database with sample employees and supervisors.
Run once: python scripts/seed.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from core.database import get_connection, initialize_database
from core.auth import hash_pin


SAMPLE_EMPLOYEES = [
    {
        "employee_id": "EMP-001",
        "full_name":   "Juan dela Cruz",
        "department":  "Records Section",
        "position":    "Administrative Aide I",
        "pin":         "1234",
    },
    {
        "employee_id": "EMP-002",
        "full_name":   "Maria Santos",
        "department":  "Finance Division",
        "position":    "Accountant II",
        "pin":         "2345",
    },
    {
        "employee_id": "EMP-003",
        "full_name":   "Pedro Reyes",
        "department":  "Records Section",
        "position":    "Records Officer I",
        "pin":         "3456",
    },
    {
        "employee_id": "EMP-004",
        "full_name":   "Ana Lim",
        "department":  "IT Division",
        "position":    "Information Systems Analyst I",
        "pin":         "4567",
    },
    {
        "employee_id": "EMP-005",
        "full_name":   "Rosa Mendoza",
        "department":  "Finance Division",
        "position":    "Budget Officer II",
        "pin":         "5678",
    },
]

SAMPLE_SUPERVISORS = [
    {
        "supervisor_id": "SUP-001",
        "full_name":     "Dir. Carlo Bautista",
        "department":    "Office of the Director",
        "pin":           "9999",
    },
    {
        "supervisor_id": "SUP-002",
        "full_name":     "Ms. Ligaya Fernandez",
        "department":    "Human Resources",
        "pin":           "8888",
    },
]


def seed():
    initialize_database()
    conn = get_connection()
    now = datetime.now().isoformat()

    print("\nSeeding employees...")
    for emp in SAMPLE_EMPLOYEES:
        try:
            conn.execute("""
                INSERT INTO employees
                    (employee_id, full_name, department,
                     position, pin_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                emp["employee_id"],
                emp["full_name"],
                emp["department"],
                emp["position"],
                hash_pin(emp["pin"]),
                now
            ))
            print(f"  ✅ {emp['full_name']} ({emp['employee_id']}) — PIN: {emp['pin']}")
        except Exception as e:
            print(f"  ⚠️  Skipped {emp['employee_id']}: {e}")

    print("\nSeeding supervisors...")
    for sup in SAMPLE_SUPERVISORS:
        try:
            conn.execute("""
                INSERT INTO supervisors
                    (supervisor_id, full_name, department,
                     pin_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sup["supervisor_id"],
                sup["full_name"],
                sup["department"],
                hash_pin(sup["pin"]),
                now
            ))
            print(f"  ✅ {sup['full_name']} ({sup['supervisor_id']}) — PIN: {sup['pin']}")
        except Exception as e:
            print(f"  ⚠️  Skipped {sup['supervisor_id']}: {e}")

    conn.commit()
    conn.close()

    print("\n✅ Seed complete. Sample credentials:")
    print("─" * 40)
    print("EMPLOYEES")
    for emp in SAMPLE_EMPLOYEES:
        print(f"  ID: {emp['employee_id']}  PIN: {emp['pin']}  — {emp['full_name']}")
    print("\nSUPERVISORS")
    for sup in SAMPLE_SUPERVISORS:
        print(f"  ID: {sup['supervisor_id']}  PIN: {sup['pin']}  — {sup['full_name']}")
    print("\nADMIN PIN: 0000")
    print("─" * 40)


if __name__ == "__main__":
    seed()