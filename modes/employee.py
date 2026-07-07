"""
Employee mode logs the four daily DTR timestamps.
Smart menu only shows the valid next action.
Confirmation required before every save.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Input, Button
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from datetime import datetime

from core.database import (
    initialize_database,
    log_audit,
    get_today_entry,
    create_today_entry,
    update_dtr_field,
    flag_entry,
)
from core.auth import authenticate_employee
from core.models import DTREntry, validate_time
from ui.display import DTR_CSS, ConfirmDialog


FIELD_LABELS = {
    "am_in":  "AM In  (Arrival)",
    "am_out": "AM Out (Lunch break)",
    "pm_in":  "PM In  (Return from lunch)",
    "pm_out": "PM Out (End of day)",
}


class EmployeeApp(App):

    CSS = DTR_CSS + """
    #login-box {
        border: solid $accent;
        padding: 1 2;
        margin: 1 2;
        width: 50;
    }
    #record-container {
        padding: 1 2;
    }
    #action-box {
        border: solid $warning;
        padding: 1 2;
        margin: 1 0;
    }
    .field-row   { height: 1; margin: 0 0 0 2; }
    .field-done  { color: $success; }
    .field-empty { color: $text-muted; }
    .field-next  { color: $warning; text-style: bold; }
    #status-msg  { margin: 1 2; color: $warning; }
    """

    BINDINGS = [
        Binding("q", "quit",    "Quit"),
        Binding("r", "restart", "New Login"),
    ]

    def __init__(self):
        super().__init__()
        self.employee     = None
        self.today        = datetime.now().strftime("%Y-%m-%d")
        self.today_entry  = None
        self.next_field   = None
        self.pending_time = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Label("[bold]DTR Tracking System[/]  —  Employee Login"),
            Vertical(
                Label("Employee ID:"),
                Input(placeholder="e.g. EMP-001", id="input-id"),
                Label("PIN:"),
                Input(placeholder="Enter PIN", password=True, id="input-pin"),
                Button("Log In", variant="primary", id="btn-login"),
                id="login-box"
            ),
            id="login-container"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id

        if button_id == "btn-login":
            self._handle_login()
        elif button_id == "btn-log":
            self._show_confirm()
        elif button_id == "btn-confirm":
            if self.pending_time:
                self._save_entry()
        elif button_id == "btn-cancel":
            if self.pending_time:
                self._cancel_confirm()

    def _handle_login(self) -> None:
        emp_id = self.query_one("#input-id",  Input).value.strip().upper()
        pin    = self.query_one("#input-pin", Input).value.strip()

        if not emp_id or not pin:
            self._show_status("Please enter both Employee ID and PIN.")
            return

        employee = authenticate_employee(emp_id, pin)
        if not employee:
            self._show_status("[red]Invalid ID or PIN. Please try again.[/]")
            log_audit(emp_id, "LOGIN_FAIL", "Invalid credentials")
            return

        self.employee = employee
        log_audit(emp_id, "LOGIN", "Employee logged in")
        self._load_record_screen()

    def _load_record_screen(self) -> None:
        create_today_entry(self.employee["employee_id"], self.today)
        row = get_today_entry(self.employee["employee_id"], self.today)

        self.today_entry = DTREntry(
            employee_id = row["employee_id"],
            date        = row["date"],
            am_in       = row["am_in"],
            am_out      = row["am_out"],
            pm_in       = row["pm_in"],
            pm_out      = row["pm_out"],
            total_hours = row["total_hours"],
            status      = row["status"],
            is_flagged  = bool(row["is_flagged"]),
        )

        self.next_field = self.today_entry.next_action()

        try:
            self.query_one("#login-container").remove()
        except Exception:
            pass

        self._render_record_screen()

    def _render_record_screen(self) -> None:
        name  = self.employee["full_name"]
        dept  = self.employee["department"]
        pos   = self.employee["position"]
        entry = self.today_entry
        date  = datetime.now().strftime("%A, %B %d %Y")

        field_rows = []
        for field in ["am_in", "am_out", "pm_in", "pm_out"]:
            value   = getattr(entry, field)
            is_next = field == self.next_field
            label   = FIELD_LABELS[field]

            if value:
                style = "field-done"
                text  = f"  ✓  {label:<32} {value}"
            elif is_next:
                style = "field-next"
                text  = f"  →  {label:<32} [not logged]"
            else:
                style = "field-empty"
                text  = f"     {label:<32} —"

            field_rows.append(Label(text, classes=f"field-row {style}"))

        if self.next_field:
            action_widgets = [
                Label(f"\nNext: [bold]{FIELD_LABELS[self.next_field]}[/]"),
                Button(
                    f"Log {FIELD_LABELS[self.next_field]}",
                    variant="success",
                    id="btn-log"
                ),
            ]
        else:
            action_widgets = [
                Label(
                    "[bold green]✓ All entries complete for today.[/]\n"
                    "You may close this terminal.",
                )
            ]

        self.mount(
            Container(
                Label(f"[bold]{name}[/]  ·  {pos}  ·  {dept}"),
                Label(date),
                Label(""),
                Label("[bold]Today's Record:[/]"),
                *field_rows,
                Vertical(*action_widgets, id="action-box"),
                Label("", id="status-msg"),
                id="record-container"
            )
        )

    def _show_confirm(self) -> None:
        if not self.next_field:
            return

        try:
            self.query_one("#confirm-container").remove()
        except Exception:
            pass

        self.pending_time = datetime.now().strftime("%H:%M")
        is_valid, warning = validate_time(
            self.next_field, self.pending_time
        )

        def mount_confirm():
            try:
                self.query_one("#record-container").mount(
                    Container(
                        ConfirmDialog(
                            action        = self.next_field,
                            time_value    = self.pending_time,
                            employee_name = self.employee["full_name"],
                        ),
                        Label(warning if not is_valid else "",
                            id="warn-msg"),
                        Horizontal(
                            Button("Confirm (Y)", variant="success",
                                id="btn-confirm"),
                            Button("Cancel (N)",  variant="error",
                                id="btn-cancel"),
                        ),
                        id="confirm-container"
                    )
                )
                self.set_focus(None)
            except Exception as e:
                self._show_status(f"[red]{e}[/]")

        self.call_after_refresh(mount_confirm)

    def _save_entry(self) -> None:
        field  = self.next_field
        value  = self.pending_time
        emp_id = self.employee["employee_id"]

        is_valid, warning = validate_time(field, value)

        try:
            update_dtr_field(emp_id, self.today, field, value)
        except Exception as e:
            self._show_status(f"[red]Error: {e}[/]")
            return

        if not is_valid:
            flag_entry(emp_id, self.today, warning, field=field)
            log_audit(emp_id, "FLAG", f"{field}={value}")

        log_audit(emp_id, field.upper(), value)
        self._cleanup_confirm()
        self._show_status(
            f"[green]✓ {FIELD_LABELS[field]} logged at {value}[/]"
            + ("\n[yellow]⚠ Flagged for supervisor review.[/]"
               if not is_valid else "")
        )
        self._refresh_record()

    def _cancel_confirm(self) -> None:
        self._cleanup_confirm()
        self._show_status("Entry cancelled.")

    def _cleanup_confirm(self) -> None:
        self.pending_time = None
        try:
            self.query_one("#confirm-container").remove()
        except Exception:
            pass

    def _refresh_record(self) -> None:
        self.pending_time = None
        try:
            self.query_one("#confirm-container").remove()
        except Exception:
            pass
        try:
            self.query_one("#record-container").remove()
        except Exception:
            pass
        self.call_after_refresh(self._load_record_screen)

    def _show_status(self, msg: str) -> None:
        try:
            self.query_one("#status-msg", Label).update(msg)
        except Exception:
            pass

    def action_restart(self) -> None:
        for el in ["#record-container", "#confirm-container"]:
            try:
                self.query_one(el).remove()
            except Exception:
                pass
        self.employee    = None
        self.today_entry = None
        self.next_field  = None
        self.mount(
            Container(
                Label("[bold]DTR Tracking System[/]  —  Employee Login"),
                Vertical(
                    Label("Employee ID:"),
                    Input(placeholder="e.g. EMP-001", id="input-id"),
                    Label("PIN:"),
                    Input(placeholder="Enter PIN",
                          password=True, id="input-pin"),
                    Button("Log In", variant="primary", id="btn-login"),
                    id="login-box"
                ),
                id="login-container"
            )
        )

    def action_confirm(self) -> None:
        if self.pending_time:
            self._save_entry()

    def action_cancel(self) -> None:
        if self.pending_time:
            self._cancel_confirm()

    def on_key(self, event) -> None:
        if event.key == "y" and self.pending_time:
            self._save_entry()
        elif event.key == "n" and self.pending_time:
            self._cancel_confirm()


def run():
    initialize_database()
    EmployeeApp().run()


if __name__ == "__main__":
    run()