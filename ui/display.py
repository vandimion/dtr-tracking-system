"""
Reusable Textual UI components.
"""

from textual.widgets import DataTable, Static, Label
from textual.containers import Horizontal, Vertical
from textual.app import ComposeResult
from rich.text import Text
from datetime import datetime


# ------------------------------------------------------------------ #
# STATUS BADGES
# ------------------------------------------------------------------ #

def status_badge(status: str, is_flagged: bool = False) -> Text:
    if is_flagged:
        return Text("⚠  Flagged",    style="bold yellow")
    match status:
        case "complete":
            return Text("✓  Complete",   style="bold green")
        case "incomplete":
            return Text("⏳ In progress", style="bold yellow")
        case _:
            return Text("✗  Absent",     style="bold red")


def time_cell(value: str | None, flagged: bool = False) -> Text:
    if not value:
        return Text("—", style="dim")
    if flagged:
        return Text(value, style="bold yellow")
    return Text(value, style="green")


def hours_cell(value: float | None) -> Text:
    if value is None:
        return Text("—", style="dim")
    return Text(f"{value:.1f}h", style="cyan")


# ------------------------------------------------------------------ #
# ATTENDANCE TABLE
# ------------------------------------------------------------------ #

def build_attendance_table(table: DataTable, rows: list[dict]) -> None:
    table.clear(columns=True)
    table.add_columns(
        "Employee",
        "AM In",
        "AM Out",
        "PM In",
        "PM Out",
        "Hours",
        "Status",
    )
    for row in rows:
        flagged = bool(row.get("is_flagged", False))
        table.add_row(
            Text(row["full_name"], style="bold" if flagged else ""),
            time_cell(row.get("am_in"),  flagged and not row.get("am_out")),
            time_cell(row.get("am_out")),
            time_cell(row.get("pm_in")),
            time_cell(row.get("pm_out")),
            hours_cell(row.get("total_hours")),
            status_badge(row.get("status", "absent"), flagged),
            key=row["employee_id"],
        )


# ------------------------------------------------------------------ #
# SUMMARY BAR
# ------------------------------------------------------------------ #

class SummaryBar(Static):
    def update_stats(self, rows: list[dict]) -> None:
        total    = len(rows)
        complete = sum(1 for r in rows if r.get("status") == "complete")
        flagged  = sum(1 for r in rows if r.get("is_flagged"))
        absent   = sum(1 for r in rows if not r.get("am_in"))
        progress = total - complete - absent

        self.update(
            f"[bold]{total}[/] total  "
            f"[green]{complete}[/] complete  "
            f"[yellow]{progress}[/] in progress  "
            f"[red]{absent}[/] absent  "
            f"[yellow]{flagged}[/] flagged"
        )


# ------------------------------------------------------------------ #
# APP HEADER
# ------------------------------------------------------------------ #

class AppHeader(Static):
    def __init__(self, mode: str, department: str = "All Departments"):
        super().__init__()
        self.mode       = mode
        self.department = department

    def compose(self) -> ComposeResult:
        now  = datetime.now()
        date = now.strftime("%A, %B %d %Y")
        time = now.strftime("%I:%M %p")
        yield Horizontal(
            Label(
                f"[bold]DTR Tracking System[/]  ·  "
                f"[cyan]{self.mode.upper()} MODE[/]",
                id="header-title"
            ),
            Label(
                f"{date}  ·  {time}  ·  {self.department}",
                id="header-date"
            ),
        )


# ------------------------------------------------------------------ #
# CONFIRMATION DIALOG
# ------------------------------------------------------------------ #

class ConfirmDialog(Static):
    def __init__(self, action: str, time_value: str, employee_name: str):
        super().__init__()
        self.action        = action
        self.time_value    = time_value
        self.employee_name = employee_name

    def compose(self) -> ComposeResult:
        action_label = self.action.replace("_", " ").upper()
        yield Vertical(
            Label(f"[bold yellow]Confirm Entry[/]"),
            Label(f"  Employee : [bold]{self.employee_name}[/]"),
            Label(f"  Action   : [bold]{action_label}[/]"),
            Label(f"  Time     : [bold green]{self.time_value}[/]"),
            Label(f"  Date     : {datetime.now().strftime('%B %d, %Y')}"),
            Label(""),
            Label("[bold]Press Y to confirm  ·  N or Esc to cancel[/]"),
            id="confirm-dialog"
        )


# ------------------------------------------------------------------ #
# SHARED CSS
# ------------------------------------------------------------------ #

DTR_CSS = """
Screen {
    background: $surface;
}

#header-title {
    color: $text;
    text-style: bold;
    padding: 0 1;
}

#header-date {
    color: $text-muted;
    padding: 0 1;
    text-align: right;
}

DataTable {
    height: 1fr;
    border: solid $primary;
}

DataTable > .datatable--header {
    text-style: bold;
    color: $accent;
}

DataTable > .datatable--cursor {
    background: $primary 30%;
}

SummaryBar {
    padding: 0 1;
    color: $text-muted;
    height: 1;
}

#confirm-dialog {
    border: solid $warning;
    padding: 1 2;
    margin: 1 0;
    background: $surface-darken-1;
}

AppHeader {
    height: 3;
    border-bottom: solid $primary;
    background: $surface-darken-1;
    padding: 0 1;
}
"""