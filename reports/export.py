"""
Generates monthly DTR reports in CSC format.
Applies corrections on top of original entries.
Saves to reports/ folder as plain text.
"""

import os
import sys
import calendar
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_connection

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports"
)


def _apply_corrections(entry: dict, corrections: list[dict]) -> dict:
    result = dict(entry)
    for c in corrections:
        if c["employee_id"] == entry["employee_id"]:
            field = c["field_corrected"]
            if field in result:
                result[field] = c["new_value"]
    return result


def export_monthly_report(month: str, requested_by: str = "SYSTEM") -> str:
    year_str, month_str = month.split("-")
    year       = int(year_str)
    month_num  = int(month_str)
    month_name = datetime(year, month_num, 1).strftime("%B %Y")
    days_in_month = calendar.monthrange(year, month_num)[1]

    conn = get_connection()

    employees = conn.execute("""
        SELECT employee_id, full_name, department, position
        FROM employees
        WHERE is_active = 1
        ORDER BY department, full_name
    """).fetchall()

    corrections = conn.execute("""
        SELECT employee_id, field_corrected, new_value, corrected_at
        FROM corrections
        WHERE substr(corrected_at, 1, 7) = ?
        ORDER BY corrected_at
    """, (month,)).fetchall()
    corrections = [dict(c) for c in corrections]

    lines = []
    lines.append("=" * 72)
    lines.append("DAILY TIME RECORD".center(72))
    lines.append(month_name.center(72))
    lines.append("CIVIL SERVICE COMMISSION FORMAT".center(72))
    lines.append("=" * 72)
    lines.append(
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append(f"Requested : {requested_by}")
    lines.append("")

    for emp in employees:
        emp_id = emp["employee_id"]

        entries = conn.execute("""
            SELECT date, am_in, am_out, pm_in, pm_out,
                   total_hours, status, is_flagged
            FROM dtr_entries
            WHERE employee_id = ?
            AND substr(date, 1, 7) = ?
            ORDER BY date
        """, (emp_id, month)).fetchall()
        entries   = [dict(e) for e in entries]
        entries   = [_apply_corrections(e, corrections) for e in entries]
        entry_map = {e["date"]: e for e in entries}

        lines.append("-" * 72)
        lines.append(f"Name     : {emp['full_name']}")
        lines.append(f"ID       : {emp['employee_id']}")
        lines.append(f"Position : {emp['position']}")
        lines.append(f"Dept     : {emp['department']}")
        lines.append("")
        lines.append(
            f"{'Day':<5} {'Date':<12} "
            f"{'AM In':<8} {'AM Out':<8} "
            f"{'PM In':<8} {'PM Out':<8} "
            f"{'Hours':<6} Status"
        )
        lines.append("-" * 72)

        total_hours  = 0.0
        present_days = 0
        absent_days  = 0

        for day_num in range(1, days_in_month + 1):
            d        = date(year, month_num, day_num)
            day_name = d.strftime("%a")
            date_str = d.strftime("%Y-%m-%d")

            if d.weekday() >= 5:
                lines.append(
                    f"{day_name:<5} {date_str:<12} "
                    f"{'':>8} {'':>8} {'':>8} {'':>8} "
                    f"{'':>6} [Weekend]"
                )
                continue

            entry = entry_map.get(date_str)

            if entry:
                am_in  = entry.get("am_in")  or "—"
                am_out = entry.get("am_out") or "—"
                pm_in  = entry.get("pm_in")  or "—"
                pm_out = entry.get("pm_out") or "—"
                hours  = entry.get("total_hours") or 0.0
                status = entry.get("status", "incomplete")
                flag   = " ⚠" if entry.get("is_flagged") else ""

                total_hours  += hours or 0.0
                present_days += 1

                lines.append(
                    f"{day_name:<5} {date_str:<12} "
                    f"{am_in:<8} {am_out:<8} "
                    f"{pm_in:<8} {pm_out:<8} "
                    f"{hours:<6.1f} {status}{flag}"
                )
            else:
                absent_days += 1
                lines.append(
                    f"{day_name:<5} {date_str:<12} "
                    f"{'—':<8} {'—':<8} {'—':<8} {'—':<8} "
                    f"{'—':<6} absent"
                )

        lines.append("-" * 72)
        lines.append(
            f"Total hours  : {total_hours:.1f}  |  "
            f"Present : {present_days}  |  "
            f"Absent  : {absent_days}"
        )
        lines.append("")
        lines.append("Employee signature  : ________________________")
        lines.append("Supervisor signature: ________________________")
        lines.append("")

    conn.close()

    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = (
        f"DTR_{month}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    filepath = os.path.join(REPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


if __name__ == "__main__":
    path = export_monthly_report(
        month=datetime.now().strftime("%Y-%m"),
        requested_by="TEST"
    )
    print(f"Report saved to: {path}")