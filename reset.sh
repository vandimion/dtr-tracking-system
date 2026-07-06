#!/bin/bash
# reset.sh
# Daily reset script — clears flags for a fresh day.
# Schedule this with cron to run automatically at midnight.
#
# To schedule via cron (runs at 11:59 PM daily):
#   crontab -e
#   59 23 * * * /path/to/your/project/reset.sh >> /path/to/logs/reset.log 2>&1

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"

echo "================================================" >> "$LOG_DIR/reset.log"
echo "Daily reset started: $(date)" >> "$LOG_DIR/reset.log"

python "$(dirname "$0")/main.py" --mode admin 2>&1

echo "Daily reset complete: $(date)" >> "$LOG_DIR/reset.log"