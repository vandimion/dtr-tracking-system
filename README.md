# DTR Tracking System

A terminal-based Daily Time Record (DTR) system built for a Philippine government office. It replaces paper bundy sheets or biometrics (which is considered more accurate, yet highly prone to user error) with a PIN-protected TUI where employees log their four daily timestamps, supervisors watch a live attendance dashboard, and admins manage staff and export monthly reports.

This is my first personal project, built with Python.

## Features

- **Employee mode** — PIN login, then a smart menu that only shows the next valid action (AM In → AM Out → PM In → PM Out), with a confirmation step before every save.
- **Supervisor mode** — live, auto-refreshing attendance dashboard, plus the ability to review and approve corrections on flagged entries.
- **Admin mode** — add/manage employees and supervisors, review the audit log, and export monthly reports in CSC format.
- **Time validation** — each timestamp is checked against expected clock-in/out windows; anything outside the window is automatically flagged for supervisor review.
- **Security** — PINs are never stored in plain text; they're hashed with bcrypt.
- **Audit trail** — every action (log, correction, admin change) is recorded with a timestamp and terminal ID.

## Stack

- Python 3.10+ (uses `match` statements)
- [Textual](https://textual.textualize.io/) + [Rich](https://github.com/Textualize/rich) for the terminal UI
- SQLite for storage
- [bcrypt](https://pypi.org/project/bcrypt/) for PIN hashing

## Getting started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

(Core dependencies: `textual`, `rich`, `bcrypt`.)

### 2. Initialize the database

```bash
python main.py --init
```

### 3. Seed sample data

Creates sample employees, supervisors, and prints their PINs to the console:

```bash
python main.py --seed
```

### 4. Run a mode

```bash
python main.py --mode employee # enter employee app

python main.py --mode supervisor # enter supervisor app

python main.py --mode admin # enter admin app
```

Or use the interactive launcher menu instead:

```bash
bash start.sh
```


**Note:** There is currently no feature that lets user create their own dataset from scratch. Make use of `python main.py --seed` for the meantime and edit using the set admin role if you want to enter your own credentials. Delete the sample entries (employees and supervisors) and create your own.

Each mode can be tagged with a terminal ID for the audit log, e.g. `python main.py --mode employee --terminal "TERMINAL-1"`.

### Default admin PIN

`0000`, until an admin PIN is set from within the app.


## Project structure

```
dtr-tracking-system/
├── main.py              # CLI entry point (--mode, --init, --seed)
├── start.sh             # Interactive launcher menu
├── reset.sh             # Daily reset script (intended for cron)
├── core/
│   ├── database.py      # SQLite connection & schema
│   ├── auth.py          # PIN hashing & authentication
│   └── models.py        # Employee, DTREntry, and validation logic
├── modes/
│   ├── employee.py      # Employee TUI
│   ├── supervisor.py    # Supervisor TUI (live dashboard)
│   └── admin.py         # Admin TUI (management & exports)
├── ui/
│   └── display.py       # Shared Textual widgets and styling
├── reports/
│   └── export.py        # Monthly CSC-format report generator
├── scripts/
│   └── seed.py          # Sample data seeder
└── data/                # SQLite database lives here (dtr.db)
```

## Automating the daily reset

`reset.sh` is meant to be scheduled with cron to run at the end of each day:

```bash
crontab -e
# 59 23 * * * /path/to/dtr-tracking-system/reset.sh >> /path/to/logs/reset.log 2>&1
```

## Status

Actively in progress — built as a learning project to practice Python, SQLite, and building real terminal UIs with Textual.

This is a personal / test project, not meant to be deployed for real government or production use in its current state.

## Known limitations & notes for improvement

- **Not yet tested on Linux.** A main objective of this project is to be able to run it on low-end school computers that have Linux OS installed. Development so far has been on other platforms. Paths `start.sh`/`reset.sh` and cron behavior haven't been verified on Linux yet.
- **Security has not been tested or audited.** PINs are bcrypt-hashed and there's a basic audit log, but there's been no real security review (e.g. brute-force protection, session handling, SQL injection surface).
- **No feature yet to add employees/supervisors from within the app.** Right now they can only be created via `scripts/seed.py`; The current contents of the seed need to be used temporarily, delete all current employees and supervisors and replace with own entries for now.
- **Concurrency is untested.** Multiple terminals writing to the same SQLite database (e.g. several employee terminals logging in at once) hasn't been verified to work reliably.
- **Program structure is highly cramped.** The main Python files exceed over 1000 lines. Code needs to be refactored for easier feature addition and debugging.
- **Open to improvement.** Feel free to fork, pull, or suggest changes, including things like cleaning up the file structure or adding tests.