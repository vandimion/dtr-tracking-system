"""
Supervisor mode shows live attendance dashboard with auto-refresh.
Approve corrections on flagged entries.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Label, Input, Button
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from datetime import datetime

from core.database import get_connection, initialize_database, log_audit
from core.auth import authenticate_supervisor
from ui.display import DTR_CSS, build_attendance_table, SummaryBar

REFRESH_INTERVAL = 30


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

        rows = self._fetch_today_rows()

        self.mount(
            Vertical(
                Label(
                    f"[bold]Daily Attendance — "
                    f"{datetime.now().strftime('%A, %B %d %Y')}[/]  ·  "
                    f"Supervisor: [cyan]{self.supervisor['full_name']}[/]",
                    id="dash-header"
                ),
                DataTable(id="attendance-table"),
                SummaryBar(id="summary-bar"),
                Label("", id="refresh-label"),
                id="dashboard"
            )
        )

        table = self.query_one("#attendance-table", DataTable)
        build_attendance_table(table, rows)
        self.query_one("#summary-bar", SummaryBar).update_stats(rows)
        self._update_refresh_label()
        self.set_interval(1, self._tick)

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
                COALESCE(d.flag_reason,   '') as flag_reason
            FROM employees e
            LEFT JOIN dtr_entries d
                ON e.employee_id = d.employee_id
                AND d.date = ?
            WHERE e.is_active = 1
            ORDER BY e.department, e.full_name
        """, (self.today,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

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
                    Label(f"  Reason: {first['flag_reason'] or '—'}"),
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

        if field not in {"am_in", "am_out", "pm_in", "pm_out"}:
            return
        if not value or not reason:
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

        try:
            self.query_one("#correction-panel").remove()
        except Exception:
            pass

        self.showing_corrections = False
        self.action_refresh()

    def action_refresh(self) -> None:
        self.refresh_counter = REFRESH_INTERVAL
        rows = self._fetch_today_rows()
        try:
            build_attendance_table(
                self.query_one("#attendance-table", DataTable), rows
            )
            self.query_one("#summary-bar", SummaryBar).update_stats(rows)
        except Exception:
            pass

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