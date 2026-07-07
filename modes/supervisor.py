"""
Supervisor mode shows live attendance dashboard with auto-refresh.
Approve corrections on flagged entries.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label, Input, Button, Static
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from datetime import datetime

from core.database import get_connection, initialize_database, log_audit
from core.auth import authenticate_supervisor
from ui.display import DTR_CSS, build_attendance_table, SummaryBar


REFRESH_INTERVAL = 5


class SupervisorApp(App):

    CSS = DTR_CSS + """
    #login-box {
        border: solid $accent;
        padding: 1 2;
        margin: 1 2;
        width: 50;
    }
    #dashboard { height: 1fr; }
    #correction-panel {
        border: solid $warning;
        padding: 1 2;
        margin: 1 0;
    }
    #refresh-label { color: $text-muted; padding: 0 1; }
    """

    BINDINGS = [
        Binding("r", "refresh",     "Refresh"),
        Binding("c", "corrections", "Corrections"),
        Binding("e", "export",      "Export DTR"),
        Binding("q", "quit",        "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.supervisor          = None
        self.today               = datetime.now().strftime("%Y-%m-%d")
        self.refresh_counter     = REFRESH_INTERVAL
        self.showing_corrections = False
        self._current_flagged    = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Label("[bold]DTR Tracking System[/]  —  Supervisor Login"),
            Vertical(
                Label("Supervisor ID:"),
                Input(placeholder="e.g. SUP-001", id="input-id"),
                Label("PIN:"),
                Input(placeholder="Enter PIN", password=True, id="input-pin"),
                Button("Log In", variant="primary", id="btn-login"),
                id="login-box"
            ),
            id="login-container"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-login":   self._handle_login,
            "btn-approve": self._approve_correction,
        }
        handler = handlers.get(event.button.id)
        if handler:
            handler()

    def _handle_login(self) -> None:
        sup_id = self.query_one("#input-id",  Input).value.strip().upper()
        pin    = self.query_one("#input-pin", Input).value.strip()

        if not sup_id or not pin:
            return

        supervisor = authenticate_supervisor(sup_id, pin)
        if not supervisor:
            try:
                self.query_one("#login-box").mount(
                    Label("[red]Invalid ID or PIN.[/]", id="login-error")
                )
            except Exception:
                pass
            return

        self.supervisor = supervisor
        log_audit(sup_id, "SUPERVISOR_LOGIN", "Dashboard accessed")
        self._load_dashboard()

    def _load_dashboard(self) -> None:
        try:
            self.query_one("#login-container").remove()
        except Exception:
            pass
        try:
            self.query_one("#dashboard").remove()
        except Exception:
            pass

        self.mount(
            Vertical(
                Label(
                    f"[bold]Daily Attendance — "
                    f"{datetime.now().strftime('%A, %B %d %Y')}[/]  ·  "
                    f"Supervisor: [cyan]{self.supervisor['full_name']}[/]",
                    id="dash-header"
                ),
                Static(id="attendance-display"),
                Static(id="summary-display"),
                Label("", id="refresh-label"),
                id="dashboard"
            )
        )

        self.call_after_refresh(self._render_table)
        self.set_interval(1, self._tick)


    def _render_table(self) -> None:
        rows = self._fetch_today_rows()

        from rich.table import Table
        from rich.text import Text

        table = Table(
            show_header=True,
            header_style="bold cyan",
            expand=True
        )

        table.add_column("Employee",  style="white",  min_width=20)
        table.add_column("AM In",     style="green",  min_width=8)
        table.add_column("AM Out",    style="green",  min_width=8)
        table.add_column("PM In",     style="green",  min_width=8)
        table.add_column("PM Out",    style="green",  min_width=8)
        table.add_column("Hours",     style="cyan",   min_width=6)
        table.add_column("Status",    min_width=14)

        for row in rows:
            flagged = bool(row.get("is_flagged", False))
            status  = row.get("status", "absent")

            if flagged:
                status_text = Text("⚠  Flagged",    style="bold yellow")
            elif status == "complete":
                status_text = Text("✓  Complete",   style="bold green")
            elif status == "incomplete":
                status_text = Text("⏳ In progress", style="bold yellow")
            else:
                status_text = Text("✗  Absent",     style="bold red")

            name = Text(
                row["full_name"],
                style="bold yellow" if flagged else "white"
            )

            table.add_row(
                name,
                Text(row.get("am_in")  or "—",
                    style="yellow" if flagged else "green"),
                row.get("am_out") or "—",
                row.get("pm_in")  or "—",
                row.get("pm_out") or "—",
                f"{row.get('total_hours') or '—'}",
                status_text,
            )

        total    = len(rows)
        complete = sum(1 for r in rows if r.get("status") == "complete")
        flagged  = sum(1 for r in rows if r.get("is_flagged"))
        absent   = sum(1 for r in rows if not r.get("am_in"))
        progress = total - complete - absent

        summary = (
            f"[bold]{total}[/] total  "
            f"[green]{complete}[/] complete  "
            f"[yellow]{progress}[/] in progress  "
            f"[red]{absent}[/] absent  "
            f"[yellow]{flagged}[/] flagged"
        )

        try:
            self.query_one("#attendance-display", Static).update(table)
            self.query_one("#summary-display",    Static).update(summary)
        except Exception:
            pass

    def _fetch_today_rows(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                e.employee_id,
                e.full_name,
                e.department,
                COALESCE(d.am_in,       NULL) as am_in,
                COALESCE(d.am_out,      NULL) as am_out,
                COALESCE(d.pm_in,       NULL) as pm_in,
                COALESCE(d.pm_out,      NULL) as pm_out,
                COALESCE(d.total_hours, NULL) as total_hours,
                COALESCE(d.status,   'absent') as status,
                COALESCE(d.is_flagged,     0) as is_flagged,
                COALESCE(d.flag_reason,   '') as flag_reason,
                d.id as entry_id
            FROM employees e
            LEFT JOIN dtr_entries d
                ON e.employee_id = d.employee_id
                AND d.date = ?
            WHERE e.is_active = 1
            ORDER BY e.department, e.full_name
        """, (self.today,)).fetchall()

        # Fetch today's corrections
        corrections = conn.execute("""
            SELECT c.dtr_entry_id, c.field_corrected, c.new_value
            FROM corrections c
            JOIN dtr_entries d ON c.dtr_entry_id = d.id
            WHERE d.date = ?
            ORDER BY c.corrected_at
        """, (self.today,)).fetchall()
        conn.close()

        # Build correction lookup by entry_id
        correction_map = {}
        for c in corrections:
            entry_id = c["dtr_entry_id"]
            if entry_id not in correction_map:
                correction_map[entry_id] = {}
            correction_map[entry_id][c["field_corrected"]] = c["new_value"]

        # Apply corrections and recalculate hours
        result = []
        for row in rows:
            r = dict(row)
            entry_id = r.get("entry_id")
            if entry_id and entry_id in correction_map:
                for field, new_value in correction_map[entry_id].items():
                    r[field] = new_value

            # Recalculate total_hours from corrected values
            try:
                total = 0.0
                if r.get("am_in") and r.get("am_out"):
                    am_in  = datetime.strptime(r["am_in"],  "%H:%M")
                    am_out = datetime.strptime(r["am_out"], "%H:%M")
                    total += (am_out - am_in).seconds / 3600
                if r.get("pm_in") and r.get("pm_out"):
                    pm_in  = datetime.strptime(r["pm_in"],  "%H:%M")
                    pm_out = datetime.strptime(r["pm_out"], "%H:%M")
                    total += (pm_out - pm_in).seconds / 3600
                if total > 0:
                    r["total_hours"] = round(total, 2)
            except Exception:
                pass

            result.append(r)

        return result

    def _tick(self) -> None:
        self.refresh_counter -= 1
        if self.refresh_counter <= 0:
            self.refresh_counter = REFRESH_INTERVAL
            self.action_refresh()
        self._update_refresh_label()

    def _update_refresh_label(self) -> None:
        try:
            self.query_one("#refresh-label", Label).update(
                f"[dim]Auto-refresh in {self.refresh_counter}s  ·  "
                f"[bold]R[/] to refresh now[/]"
            )
        except Exception:
            pass

    def _load_corrections_panel(self) -> None:
        conn = get_connection()
        flagged = conn.execute("""
            SELECT
                d.id as entry_id,
                e.full_name,
                d.employee_id,
                d.date,
                d.am_in, d.am_out, d.pm_in, d.pm_out,
                d.flag_reason
            FROM dtr_entries d
            JOIN employees e ON d.employee_id = e.employee_id
            WHERE d.is_flagged = 1 AND d.date = ?
            ORDER BY d.created_at
        """, (self.today,)).fetchall()
        conn.close()

        if not flagged:
            try:
                self.query_one("#dashboard").mount(
                    Label("[green]No flagged entries today.[/]",
                          id="no-flags")
                )
            except Exception:
                pass
            return

        first = dict(flagged[0])
        self._current_flagged = first

        try:
            self.query_one("#dashboard").mount(
                Vertical(
                    Label(
                        f"[bold yellow]⚠ Flagged[/]  —  "
                        f"{first['full_name']}  ·  {first['date']}"
                    ),
                    Label(
                        f"  AM In: {first['am_in'] or '—'}  "
                        f"AM Out: {first['am_out'] or '—'}  "
                        f"PM In: {first['pm_in'] or '—'}  "
                        f"PM Out: {first['pm_out'] or '—'}"
                    ),
                    Label(
                        f"  Flagged fields: [yellow]{first['flag_reason'] or '—'}[/]"
                    ),
                    Label(
                        "  Expected ranges:  "
                        "[green]AM In: 06:00–10:00[/]  "
                        "[green]AM Out: 11:00–13:00[/]  "
                        "[green]PM In: 12:00–14:00[/]  "
                        "[green]PM Out: 15:00–20:00[/]"
                    ),
                    Label(
                        f"  Logged values:  "
                        f"AM In: [yellow]{first['am_in'] or '—'}[/]  "
                        f"AM Out: [yellow]{first['am_out'] or '—'}[/]  "
                        f"PM In: [yellow]{first['pm_in'] or '—'}[/]  "
                        f"PM Out: [yellow]{first['pm_out'] or '—'}[/]"
                    ),
                    Label(""),
                    Label("Field to correct:"),
                    Input(
                        placeholder="am_in / am_out / pm_in / pm_out",
                        id="corr-field"
                    ),
                    Label("Correct value (HH:MM):"),
                    Input(placeholder="08:05", id="corr-value"),
                    Label("Reason (required):"),
                    Input(
                        placeholder="Describe reason for correction",
                        id="corr-reason"
                    ),
                    Button("Approve Correction",
                           variant="warning", id="btn-approve"),
                    Label("", id="corr-error"),
                    id="correction-panel"
                )
            )
        except Exception:
            pass

    def _approve_correction(self) -> None:
        try:
            field  = self.query_one("#corr-field",  Input).value.strip()
            value  = self.query_one("#corr-value",  Input).value.strip()
            reason = self.query_one("#corr-reason", Input).value.strip()
        except Exception:
            return

        # Validate field name
        if field not in {"am_in", "am_out", "pm_in", "pm_out"}:
            try:
                self.query_one("#corr-error", Label).update(
                    "[red]Invalid field. Must be: am_in, am_out, pm_in, pm_out[/]"
                )
            except Exception:
                self.query_one("#correction-panel").mount(
                    Label("", id="corr-error")
                )
                self.query_one("#corr-error", Label).update(
                    "[red]Invalid field. Must be: am_in, am_out, pm_in, pm_out[/]"
                )
            return

        # Validate field is actually flagged
        flagged_fields = [
            f.strip()
            for f in (self._current_flagged.get("flag_reason") or "").split(",")
            if f.strip()
        ]
        if flagged_fields and field not in flagged_fields:
            try:
                self.query_one("#corr-error", Label).update(
                    f"[red]'{field}' is not flagged. "
                    f"Flagged fields: {', '.join(flagged_fields)}[/]"
                )
            except Exception:
                pass
            return

        # Validate time format
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            try:
                self.query_one("#corr-error", Label).update(
                    "[red]Invalid time format. Use HH:MM (e.g. 08:05)[/]"
                )
            except Exception:
                pass
            return

        # Validate time is within expected range
        from core.models import TIME_RULES, validate_time
        is_valid, warning = validate_time(field, value)
        if not is_valid:
            try:
                self.query_one("#corr-error", Label).update(
                    f"[red]Correction value is also outside expected range. "
                    f"Expected {TIME_RULES[field][0]}–{TIME_RULES[field][1]}. "
                    f"Confirm anyway? Change reason to OVERRIDE to force.[/]"
                )
            except Exception:
                pass
            if reason.upper() != "OVERRIDE":
                return

        # Validate reason is not empty
        if not reason:
            try:
                self.query_one("#corr-error", Label).update(
                    "[red]Reason is required before approving.[/]"
                )
            except Exception:
                pass
            return

        entry = self._current_flagged
        conn  = get_connection()

        row = conn.execute(
            f"SELECT {field} FROM dtr_entries WHERE id = ?",
            (entry["entry_id"],)
        ).fetchone()
        old_value = row[0] if row else None

        conn.execute("""
            INSERT INTO corrections
                (dtr_entry_id, employee_id, field_corrected,
                 old_value, new_value, reason, corrected_by, corrected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry["entry_id"],
            entry["employee_id"],
            field,
            old_value,
            value,
            reason,
            self.supervisor["supervisor_id"],
            datetime.now().isoformat()
        ))

        # Remove corrected field from flag_reason
        current = conn.execute("""
            SELECT flag_reason FROM dtr_entries WHERE id = ?
        """, (entry["entry_id"],)).fetchone()

        existing = current["flag_reason"] if current and current["flag_reason"] else ""
        remaining = [f.strip() for f in existing.split(",")
                     if f.strip() and f.strip() != field]

        if remaining:
            conn.execute("""
                UPDATE dtr_entries
                SET flag_reason = ?
                WHERE id = ?
            """, (",".join(remaining), entry["entry_id"]))
        else:
            conn.execute("""
                UPDATE dtr_entries
                SET is_flagged = 0, flag_reason = NULL
                WHERE id = ?
            """, (entry["entry_id"],))

        conn.commit()
        conn.close()

        log_audit(
            entry["employee_id"],
            "CORRECTION",
            f"{field}: {old_value} → {value}",
            note=f"Approved by {self.supervisor['supervisor_id']}: {reason}"
        )

        self.showing_corrections = False

        def refresh_after():
            try:
                self.query_one("#correction-panel").remove()
            except Exception:
                pass
            self.call_after_refresh(self._render_table)

        self.call_after_refresh(refresh_after)

    def action_refresh(self) -> None:
        self.refresh_counter = REFRESH_INTERVAL
        self.call_after_refresh(self._render_table)

    def action_corrections(self) -> None:
        if self.showing_corrections:
            try:
                self.query_one("#correction-panel").remove()
            except Exception:
                pass
            self.showing_corrections = False
        else:
            self._load_corrections_panel()
            self.showing_corrections = True

    def action_export(self) -> None:
        from reports.export import export_monthly_report
        path = export_monthly_report(
            month=datetime.now().strftime("%Y-%m"),
            requested_by=self.supervisor["supervisor_id"]
        )
        try:
            self.query_one("#dash-header", Label).update(
                f"[green]✓ Exported to {path}[/]"
            )
        except Exception:
            pass


def run():
    initialize_database()
    SupervisorApp().run()


if __name__ == "__main__":
    run()