"""
Data structures for the DTR Tracker.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Employee:
    employee_id: str
    full_name:   str
    department:  str
    position:    str
    pin_hash:    str
    is_active:   bool = True
    created_at:  str  = ""

    @property
    def display_name(self):
        return f"{self.full_name} ({self.employee_id})"


@dataclass
class Supervisor:
    supervisor_id: str
    full_name:     str
    department:    str
    pin_hash:      str
    is_active:     bool = True
    created_at:    str  = ""


@dataclass
class DTREntry:
    employee_id:  str
    date:         str
    am_in:        Optional[str]   = None
    am_out:       Optional[str]   = None
    pm_in:        Optional[str]   = None
    pm_out:       Optional[str]   = None
    total_hours:  Optional[float] = None
    status:       str  = "incomplete"
    is_flagged:   bool = False
    flag_reason:  Optional[str]   = None

    def next_action(self):
        if not self.am_in:
            return "am_in"
        if not self.am_out:
            return "am_out"
        if not self.pm_in:
            return "pm_in"
        if not self.pm_out:
            return "pm_out"
        return None

    def next_action_label(self):
        labels = {
            "am_in":  "Log AM In  (Arrival)",
            "am_out": "Log AM Out (Lunch break)",
            "pm_in":  "Log PM In  (Return from lunch)",
            "pm_out": "Log PM Out (End of day)",
            None:     "All entries complete for today",
        }
        return labels.get(self.next_action())

    def display_status(self):
        if self.is_flagged:
            return "⚠  Flagged"
        if self.status == "complete":
            return "✓  Complete"
        if self.am_in:
            return "⏳ In progress"
        return "✗  Absent"


@dataclass
class AuditEntry:
    timestamp:   str
    employee_id: str
    action:      str
    value:       str
    terminal:    str = "MAIN"
    note:        Optional[str] = None


@dataclass
class Correction:
    dtr_entry_id:    int
    employee_id:     str
    field_corrected: str
    old_value:       Optional[str]
    new_value:       str
    reason:          str
    corrected_by:    str
    corrected_at:    str


TIME_RULES = {
    "am_in":  ("06:00", "10:00"),
    "am_out": ("11:00", "13:00"),
    "pm_in":  ("12:00", "14:00"),
    "pm_out": ("15:00", "20:00"),
}


def validate_time(field: str, time_str: str) -> tuple:
    if field not in TIME_RULES:
        return True, ""

    low, high = TIME_RULES[field]

    try:
        t    = datetime.strptime(time_str, "%H:%M")
        t_lo = datetime.strptime(low,      "%H:%M")
        t_hi = datetime.strptime(high,     "%H:%M")
    except ValueError:
        return False, f"Invalid time format: {time_str}"

    if not (t_lo <= t <= t_hi):
        return False, (
            f"⚠  {time_str} is outside expected range "
            f"({low}–{high}) for {field.replace('_', ' ').upper()}. "
            f"This will be flagged for supervisor review."
        )

    return True, ""