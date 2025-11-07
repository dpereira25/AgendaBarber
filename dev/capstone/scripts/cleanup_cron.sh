#!/bin/bash
"""
Shell script wrapper for the cleanup cron job.

This script sets up the environment and runs the Django management command
for cleaning up expired temporary reservations.

Usage:
    ./scripts/cleanup_cron.sh

Or add to crontab:
    */5 * * * * /path/to/project/scripts/cleanup_cron.sh
"""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Set Django settings module
export DJANGO_SETTINGS_MODULE=capstone.settings

# Run the cleanup command
python manage.py cleanup_temp_reservations

# Log the result
echo "$(date): Cleanup completed" >> logs/cleanup.log