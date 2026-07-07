"""
Admin mode helps manage employees, reset daily records, view audit log, export reports.
Default admin PIN: 0000
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Input, Button, DataTable
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from datetime import datetime

from core.database import get_connection, initialize_database, log_audit
from core.auth import authenticate_admin, hash_pin
from ui.display import DTR_CSS


class AdminApp(App):

    CSS = DTR_CSS + """
    #login-box {
        border: solid $warning;
        padding: 1 2;
        margin: 1 2;
        width: 50;
    }
    #menu-box {
        border: solid $warning;
        padding: 1 2;
        margin: 1 2;
        width: 60;
    }
    #panel {
        border: solid $accent;
        padding: 1 2;
        margin: 1 2;
    }
    #status { margin: 1 2; color: $success; }
    DataTable { height: 20; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "back", "Back"),
    ]

    def __init__(self):
        super().__init__()
        self.today = datetime.now().strftime("%Y-%m-%d")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Label("[bold yellow]DTR Tracking System[/]  —  Admin Panel"),
            Vertical(
                Label("Admin PIN:"),
                Input(placeholder="Enter admin PIN",
                      password=True, id="input-pin"),
                Button("Unlock", variant="warning", id="btn-unlock"),
                id="login-box"
            ),
            id="login-container"
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-unlock":          self._handle_login,
            "btn-reset":           self._reset_daily,
            "btn-add-form":        self._load_add_employee_form,
            "btn-add-employee":    self._save_new_employee,
            "btn-deact-form":      self._load_deactivate_form,
            "btn-deactivate":      self._do_deactivate,
            "btn-audit":           self._view_audit_log,
            "btn-export":          self._export_report,
            "btn-back":            self.action_back,
            "btn-promote-form":    self._load_promote_form,
            "btn-promote":         self._do_promote,
            "btn-deact-sup-form":  self._load_deactivate_sup_form,
            "btn-deactivate-sup":  self._do_deactivate_sup,
        }
        handler = handlers.get(event.button.id)
        if handler:
            handler()

    # ---------------------------------------------------------------- #
    # LOGIN
    # ---------------------------------------------------------------- #
    def _handle_login(self) -> None:
        pin = self.query_one("#input-pin", Input).value.strip()

        if not authenticate_admin(pin):
            try:
                self.query_one("#login-box").mount(
                    Label("[red]Incorrect admin PIN.[/]", id="pin-error")
                )
            except Exception:
                pass
            return

        log_audit("ADMIN", "ADMIN_LOGIN", "Admin panel accessed")
        self._load_menu()

    # ---------------------------------------------------------------- #
    # MAIN MENU
    # ---------------------------------------------------------------- #
    def _load_menu(self) -> None:
        for el in ["#login-container", "#panel"]:
            try:
                self.query_one(el).remove()
            except Exception:
                pass

        self.mount(
            Container(
                Label("[bold yellow]ADMIN PANEL[/]"),
                Label(""),
                Vertical(
                    Button(
                        "[1] Reset today's statuses",
                        id="btn-reset", variant="warning"
                    ),
                    Button(
                        "[2] Add new employee",
                        id="btn-add-form", variant="primary"
                    ),
                    Button(
                        "[3] Deactivate employee",
                        id="btn-deact-form", variant="error"
                    ),
                    Button(
                        "[4] View audit log",
                        id="btn-audit", variant="default"
                    ),
                    Button(
                        "[5] Export monthly DTR",
                        id="btn-export", variant="success"
                    ),
                    Button(
                        "[6] Promote employee to supervisor",
                        id="btn-promote-form", variant="primary"
                    ),
                    Button(
                        "[7] Deactivate supervisor",
                        id="btn-deact-sup-form", variant="error"
                    ),
                    id="menu-box"
                ),
                Label("", id="status"),
                id="menu-container"
            )
        )

    # ---------------------------------------------------------------- #
    # RESET DAILY
    # ---------------------------------------------------------------- #
    def _reset_daily(self) -> None:
        conn = get_connection()
        conn.execute("""
            UPDATE dtr_entries
            SET is_flagged = 0, flag_reason = NULL
            WHERE date = ?
        """, (self.today,))
        conn.commit()
        conn.close()

        log_audit("ADMIN", "DAILY_RESET",
                  f"Flags reset for {self.today}")
        self._show_status(
            f"[green]✓ Daily reset complete for {self.today}.[/] "
            "Board is ready."
        )

    # ---------------------------------------------------------------- #
    # ADD EMPLOYEE
    # ---------------------------------------------------------------- #
    def _load_add_employee_form(self) -> None:
        try:
            self.query_one("#menu-container").remove()
        except Exception:
            pass

        self.mount(
            Container(
                Label("[bold]Add New Employee[/]"),
                Label("Employee ID (e.g. EMP-006):"),
                Input(id="new-emp-id"),
                Label("Full name:"),
                Input(id="new-emp-name"),
                Label("Department:"),
                Input(id="new-emp-dept"),
                Label("Position:"),
                Input(id="new-emp-pos"),
                Label("Initial PIN:"),
                Input(id="new-emp-pin", password=True),
                Horizontal(
                    Button("Save",
                           id="btn-add-employee", variant="primary"),
                    Button("Back",
                           id="btn-back", variant="default"),
                ),
                Label("", id="form-status"),
                id="panel"
            )
        )

    def _save_new_employee(self) -> None:
        try:
            emp_id = self.query_one("#new-emp-id",   Input).value.strip().upper()
            name   = self.query_one("#new-emp-name", Input).value.strip()
            dept   = self.query_one("#new-emp-dept", Input).value.strip()
            pos    = self.query_one("#new-emp-pos",  Input).value.strip()
            pin    = self.query_one("#new-emp-pin",  Input).value.strip()
        except Exception:
            return

        if not all([emp_id, name, dept, pos, pin]):
            try:
                self.query_one("#form-status", Label).update(
                    "[red]All fields are required.[/]"
                )
            except Exception:
                pass
            return

        try:
            conn = get_connection()
            # Check if employee ID exists but is deactivated
            existing = conn.execute("""
                SELECT id, is_active FROM employees
                WHERE employee_id = ?
            """, (emp_id,)).fetchone()

            if existing and existing["is_active"] == 1:
                conn.close()
                self.query_one("#form-status", Label).update(
                    f"[red]Employee ID {emp_id} already exists.[/]"
                )
                return
            elif existing and existing["is_active"] == 0:
                # Reactivate instead of inserting
                conn.execute("""
                    UPDATE employees
                    SET full_name = ?, department = ?, position = ?,
                        pin_hash = ?, is_active = 1
                    WHERE employee_id = ?
                """, (name, dept, pos, hash_pin(pin), emp_id))
            else:
                conn.execute("""
                    INSERT INTO employees
                        (employee_id, full_name, department,
                         position, pin_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    emp_id, name, dept, pos,
                    hash_pin(pin),
                    datetime.now().isoformat()
                ))
            conn.commit()
            conn.close()

            log_audit("ADMIN", "EMPLOYEE_ADDED", f"{emp_id} — {name}")
            try:
                self.query_one("#form-status", Label).update(
                    f"[green]✓ {name} added successfully.[/]"
                )
                self.query_one("#new-emp-id",   Input).value = ""
                self.query_one("#new-emp-name", Input).value = ""
                self.query_one("#new-emp-dept", Input).value = ""
                self.query_one("#new-emp-pos",  Input).value = ""
                self.query_one("#new-emp-pin",  Input).value = ""
            except Exception:
                pass

        except Exception as e:
            try:
                self.query_one("#form-status", Label).update(
                    f"[red]Error: {e}[/]"
                )
            except Exception:
                pass

    # ---------------------------------------------------------------- #
    # DEACTIVATE EMPLOYEE
    # ---------------------------------------------------------------- #
    def _load_deactivate_form(self) -> None:
        try:
            self.query_one("#menu-container").remove()
        except Exception:
            pass

        # Fetch active employees for reference
        conn = get_connection()
        employees = conn.execute("""
            SELECT employee_id, full_name, department, position
            FROM employees
            WHERE is_active = 1
            ORDER BY department, full_name
        """).fetchall()
        conn.close()

        emp_labels = [
            Label(
                f"  [cyan]{e['employee_id']}[/]  "
                f"{e['full_name']}  ·  "
                f"{e['position']}  ·  "
                f"{e['department']}"
            )
            for e in employees
        ]

        # Preserve deactivation message if it exists
        deact_message = getattr(self, "_deact_message", "")

        self.mount(
            Container(
                Label("[bold]Deactivate Employee[/]"),
                Label(""),
                Label("[bold]Active Employees:[/]"),
                *emp_labels,
                Label(""),
                Label("Employee ID to deactivate:"),
                Input(id="deact-id"),
                Label("Confirm admin PIN:"),
                Input(id="deact-pin", password=True),
                Horizontal(
                    Button("Deactivate",
                           id="btn-deactivate", variant="error"),
                    Button("Back",
                           id="btn-back", variant="default"),
                ),
                Label(deact_message, id="deact-status"),
                id="panel"
            )
        )

    def _do_deactivate(self) -> None:
        try:
            emp_id = self.query_one(
                "#deact-id", Input).value.strip().upper()
        except Exception:
            return

        if not emp_id:
            return

        # Require admin PIN confirmation
        try:
            confirm_pin = self.query_one("#deact-pin", Input).value.strip()
        except Exception:
            confirm_pin = ""

        if not authenticate_admin(confirm_pin):
            try:
                self.query_one("#deact-status", Label).update(
                    "[red]Incorrect admin PIN. Deactivation cancelled.[/]"
                )
            except Exception:
                pass
            return

        conn = get_connection()
        row = conn.execute("""
            SELECT id FROM employees
            WHERE employee_id = ? AND is_active = 1
        """, (emp_id,)).fetchone()

        if not row:
            conn.close()
            try:
                self.query_one("#deact-status", Label).update(
                    f"[red]Employee {emp_id} not found or already deactivated.[/]"
                )
            except Exception:
                pass
            return

        conn.execute("""
            UPDATE employees SET is_active = 0
            WHERE employee_id = ?
        """, (emp_id,))
        conn.commit()
        conn.close()

        log_audit("ADMIN", "EMPLOYEE_DEACTIVATED", emp_id)
        self._deact_message = (
            f"[green]✓ Employee {emp_id} successfully deactivated.[/]"
        )

        def reload():
            try:
                self.query_one("#panel").remove()
            except Exception:
                pass
            self.call_after_refresh(self._load_deactivate_form)

        self.call_after_refresh(reload)

    # ---------------------------------------------------------------- #
    # AUDIT LOG
    # ---------------------------------------------------------------- #
    def _view_audit_log(self) -> None:
        try:
            self.query_one("#menu-container").remove()
        except Exception:
            pass

        conn = get_connection()
        rows = conn.execute("""
            SELECT timestamp, employee_id, action, value, terminal, note
            FROM audit_log
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()
        conn.close()

        table = DataTable(id="audit-table")

        self.mount(
            Container(
                Label("[bold]Audit Log[/]  (last 100 entries)"),
                table,
                Button("Back", id="btn-back", variant="default"),
                id="panel"
            )
        )

        table.add_columns(
            "Timestamp", "Employee",
            "Action", "Value", "Terminal", "Note"
        )
        for row in rows:
            table.add_row(
                row["timestamp"][:19],
                row["employee_id"],
                row["action"],
                row["value"][:30],
                row["terminal"],
                row["note"] or "—"
            )

    # ---------------------------------------------------------------- #
    # EXPORT
    # ---------------------------------------------------------------- #
    def _export_report(self) -> None:
        from reports.export import export_monthly_report
        month = datetime.now().strftime("%Y-%m")
        path  = export_monthly_report(month=month, requested_by="ADMIN")
        self._show_status(f"[green]✓ Report exported to {path}[/]")

    # ---------------------------------------------------------------- #
    # HELPERS
    # ---------------------------------------------------------------- #
    def _show_status(self, msg: str) -> None:
        try:
            self.query_one("#status", Label).update(msg)
        except Exception:
            pass

    def action_back(self) -> None:
        for el in ["#panel"]:
            try:
                self.query_one(el).remove()
            except Exception:
                pass
        self._load_menu()

    # ---------------------------------------------------------------- #
    # PROMOTE EMPLOYEE 
    # ---------------------------------------------------------------- #

    def _load_promote_form(self) -> None:
        try:
            self.query_one("#menu-container").remove()
        except Exception:
            pass

        conn = get_connection()
        employees = conn.execute("""
            SELECT employee_id, full_name, department, position
            FROM employees
            WHERE is_active = 1
            ORDER BY department, full_name
        """).fetchall()
        conn.close()

        emp_labels = [
            Label(
                f"  [cyan]{e['employee_id']}[/]  "
                f"{e['full_name']}  ·  "
                f"{e['position']}  ·  "
                f"{e['department']}"
            )
            for e in employees
        ]

        self.mount(
            Container(
                Label("[bold]Promote Employee to Supervisor[/]"),
                Label(""),
                Label("[bold]Active Employees:[/]"),
                *emp_labels,
                Label(""),
                Label("Employee ID to promote:"),
                Input(id="promote-emp-id"),
                Label("New Supervisor ID (e.g. SUP-003):"),
                Input(id="promote-sup-id"),
                Label("Confirm admin PIN:"),
                Input(id="promote-pin", password=True),
                Horizontal(
                    Button("Promote", id="btn-promote", variant="primary"),
                    Button("Back",    id="btn-back",    variant="default"),
                ),
                Label("", id="promote-status"),
                id="panel"
            )
        )

    def _do_promote(self) -> None:
        try:
            emp_id = self.query_one("#promote-emp-id", Input).value.strip().upper()
            sup_id = self.query_one("#promote-sup-id", Input).value.strip().upper()
            pin    = self.query_one("#promote-pin",    Input).value.strip()
        except Exception:
            return

        if not all([emp_id, sup_id, pin]):
            try:
                self.query_one("#promote-status", Label).update(
                    "[red]All fields are required.[/]"
                )
            except Exception:
                pass
            return

        if not authenticate_admin(pin):
            try:
                self.query_one("#promote-status", Label).update(
                    "[red]Incorrect admin PIN.[/]"
                )
            except Exception:
                pass
            return

        conn = get_connection()

        # Check employee exists
        emp = conn.execute("""
            SELECT * FROM employees
            WHERE employee_id = ? AND is_active = 1
        """, (emp_id,)).fetchone()

        if not emp:
            conn.close()
            try:
                self.query_one("#promote-status", Label).update(
                    f"[red]Employee {emp_id} not found or already deactivated.[/]"
                )
            except Exception:
                pass
            return

        # Check SUP ID not already taken or reactivate if deactivated
        existing_sup = conn.execute("""
            SELECT id, is_active FROM supervisors
            WHERE supervisor_id = ?
        """, (sup_id,)).fetchone()

        if existing_sup and existing_sup["is_active"] == 1:
            conn.close()
            try:
                self.query_one("#promote-status", Label).update(
                    f"[red]Supervisor ID {sup_id} already exists and is active.[/]"
                )
            except Exception:
                pass
            return

        # Create or reactivate supervisor record
        if existing_sup and existing_sup["is_active"] == 0:
            conn.execute("""
                UPDATE supervisors
                SET full_name = ?, department = ?,
                    pin_hash = ?, is_active = 1
                WHERE supervisor_id = ?
            """, (
                emp["full_name"],
                emp["department"],
                emp["pin_hash"],
                sup_id
            ))
        else:
            conn.execute("""
                INSERT INTO supervisors
                    (supervisor_id, full_name, department, pin_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                sup_id,
                emp["full_name"],
                emp["department"],
                emp["pin_hash"],
                datetime.now().isoformat()
            ))

        # Auto-deactivate employee record
        conn.execute("""
            UPDATE employees SET is_active = 0
            WHERE employee_id = ?
        """, (emp_id,))

        conn.commit()
        conn.close()

        log_audit(
            "ADMIN", "PROMOTED",
            f"{emp_id} → {sup_id} ({emp['full_name']})"
        )

        try:
            self.query_one("#promote-status", Label).update(
                f"[green]✓ {emp['full_name']} promoted to supervisor "
                f"as {sup_id}. Employee record deactivated.[/]"
            )
            self.query_one("#promote-emp-id", Input).value = ""
            self.query_one("#promote-sup-id", Input).value = ""
            self.query_one("#promote-pin",    Input).value = ""
        except Exception:
            pass

    def _load_deactivate_sup_form(self) -> None:
        try:
            self.query_one("#menu-container").remove()
        except Exception:
            pass

        conn = get_connection()
        supervisors = conn.execute("""
            SELECT supervisor_id, full_name, department
            FROM supervisors
            WHERE is_active = 1
            ORDER BY department, full_name
        """).fetchall()
        conn.close()

        sup_labels = [
            Label(
                f"  [cyan]{s['supervisor_id']}[/]  "
                f"{s['full_name']}  ·  "
                f"{s['department']}"
            )
            for s in supervisors
        ]

        deact_message = getattr(self, "_deact_sup_message", "")

        self.mount(
            Container(
                Label("[bold]Deactivate Supervisor[/]"),
                Label(""),
                Label("[bold]Active Supervisors:[/]"),
                *sup_labels,
                Label(""),
                Label("Supervisor ID to deactivate:"),
                Input(id="deact-sup-id"),
                Label("Confirm admin PIN:"),
                Input(id="deact-sup-pin", password=True),
                Horizontal(
                    Button("Deactivate",
                           id="btn-deactivate-sup", variant="error"),
                    Button("Back",
                           id="btn-back", variant="default"),
                ),
                Label(deact_message, id="deact-sup-status"),
                id="panel"
            )
        )

    def _do_deactivate_sup(self) -> None:
        try:
            sup_id = self.query_one("#deact-sup-id",  Input).value.strip().upper()
            pin    = self.query_one("#deact-sup-pin", Input).value.strip()
        except Exception:
            return

        if not sup_id or not pin:
            return

        if not authenticate_admin(pin):
            try:
                self.query_one("#deact-sup-status", Label).update(
                    "[red]Incorrect admin PIN. Deactivation cancelled.[/]"
                )
            except Exception:
                pass
            return

        conn = get_connection()
        row = conn.execute("""
            SELECT id FROM supervisors
            WHERE supervisor_id = ? AND is_active = 1
        """, (sup_id,)).fetchone()

        if not row:
            conn.close()
            try:
                self.query_one("#deact-sup-status", Label).update(
                    f"[red]Supervisor {sup_id} not found or already deactivated.[/]"
                )
            except Exception:
                pass
            return

        conn.execute("""
            UPDATE supervisors SET is_active = 0
            WHERE supervisor_id = ?
        """, (sup_id,))
        conn.commit()
        conn.close()

        log_audit("ADMIN", "SUPERVISOR_DEACTIVATED", sup_id)
        self._deact_sup_message = (
            f"[green]✓ Supervisor {sup_id} successfully deactivated.[/]"
        )

        def reload():
            try:
                self.query_one("#panel").remove()
            except Exception:
                pass
            self.call_after_refresh(self._load_deactivate_sup_form)

        self.call_after_refresh(reload)

def run():
    initialize_database()
    AdminApp().run()


if __name__ == "__main__":
    run()