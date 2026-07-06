"""
Entry point for the DTR Tracking System.

Usage:
    python main.py --mode employee
    python main.py --mode supervisor
    python main.py --mode admin
    python main.py --init
    python main.py --seed
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import initialize_database


def main():
    parser = argparse.ArgumentParser(
        description="DTR Tracking System — Philippine Government Office",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  employee    Log your daily time record
  supervisor  View live attendance dashboard
  admin       Manage employees and export reports

Examples:
  python main.py --mode employee
  python main.py --mode supervisor
  python main.py --mode admin
  python main.py --init
  python main.py --seed
        """
    )

    parser.add_argument(
        "--mode",
        choices=["employee", "supervisor", "admin"],
        help="Terminal mode to launch"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize database and exit"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed sample employees and supervisors"
    )
    parser.add_argument(
        "--terminal",
        default="MAIN",
        help="Terminal ID for audit log (e.g. TERMINAL-1, TERMINAL-2)"
    )

    args = parser.parse_args()

    initialize_database()

    if args.init:
        print("[OK] Database initialized.")
        sys.exit(0)

    if args.seed:
        from scripts.seed import seed
        seed()
        sys.exit(0)

    if not args.mode:
        parser.print_help()
        print("\n[ERROR] Please specify --mode")
        sys.exit(1)

    os.environ["DTR_TERMINAL"] = args.terminal

    match args.mode:
        case "employee":
            from modes.employee import run
            run()
        case "supervisor":
            from modes.supervisor import run
            run()
        case "admin":
            from modes.admin import run
            run()


if __name__ == "__main__":
    main()