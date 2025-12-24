#!/bin/bash

# Celery Beat Startup Script
# This ensures only ONE beat scheduler runs at a time

echo "🔄 Starting Celery Beat Scheduler..."

# Kill any existing beat processes
echo "Checking for existing beat processes..."
pkill -f "celery.*beat" 2>/dev/null && echo "✓ Killed existing beat processes" || echo "✓ No existing beat processes found"

# Remove old schedule file
echo "Removing old schedule file..."
rm -f celerybeat-schedule* 2>/dev/null && echo "✓ Removed old schedule file" || echo "✓ No old schedule file found"

# Wait a moment for cleanup
sleep 1

# Activate virtual environment and start beat
cd /home/ditsdev370/Project/EOB835
source venv/bin/activate

echo ""
echo "=================================="
echo "🎯 Starting Celery Beat (3 min schedule)"
echo "=================================="
echo ""

celery -A worker.celery_app beat --loglevel=info
