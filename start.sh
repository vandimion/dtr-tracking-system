#!/bin/bash
# start.sh
# Launcher menu for DTR Tracking System.
# Run this instead of calling main.py directly.
# Usage: bash start.sh

clear

echo "================================================"
echo "       DTR TRACKING SYSTEM"
echo "================================================"
echo ""
echo "  [1] Employee   — Log your daily time record"
echo "  [2] Supervisor — View attendance dashboard"
echo "  [3] Admin      — Manage records and export"
echo "  [4] Initialize database"
echo "  [5] Seed sample data"
echo "  [Q] Quit"
echo ""
echo "================================================"
read -p "Select mode: " choice

case $choice in
    1)
        echo "Starting Employee mode..."
        python main.py --mode employee --terminal "TERMINAL-1"
        ;;
    2)
        echo "Starting Supervisor mode..."
        python main.py --mode supervisor --terminal "SUPERVISOR"
        ;;
    3)
        echo "Starting Admin mode..."
        python main.py --mode admin --terminal "ADMIN"
        ;;
    4)
        echo "Initializing database..."
        python main.py --init
        ;;
    5)
        echo "Seeding sample data..."
        python main.py --seed
        ;;
    q|Q)
        echo "Goodbye."
        exit 0
        ;;
    *)
        echo "Invalid option. Please run start.sh again."
        exit 1
        ;;
esac