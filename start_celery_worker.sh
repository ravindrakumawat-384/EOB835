#!/bin/bash

# Celery Worker Startup Script

echo "🔄 Starting Celery Worker..."

cd /home/ditsdev370/Project/EOB835
source venv/bin/activate

echo ""
echo "=================================="
echo "👷 Starting Celery Worker"
echo "=================================="
echo ""

celery -A worker.celery_app worker --loglevel=info
