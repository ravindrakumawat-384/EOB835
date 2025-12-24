#!/bin/bash

# FastAPI Startup Script

echo "🔄 Starting FastAPI Application..."

cd /home/ditsdev370/Project/EOB835
source venv/bin/activate

echo ""
echo "=================================="
echo "🚀 Starting FastAPI on port 8000"
echo "=================================="
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
