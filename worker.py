"""
Celery worker entry point.

This file is used to start Celery workers and beat scheduler.

COMMANDS:

1. Start Celery Worker:
   celery -A worker.celery_app worker --loglevel=info

2. Start Celery Beat (scheduler):
   celery -A worker.celery_app beat --loglevel=info

3. Start both Worker + Beat in one process (for development only):
   celery -A worker.celery_app worker --beat --loglevel=info

IMPORTANT:
- For production, run worker and beat as separate processes
- FastAPI (uvicorn) runs independently
- Do NOT start Celery from FastAPI code
"""

from app.celery_config import celery_app

# Import tasks to register them
from app.tasks import file_processor

# This allows running: celery -A worker.celery_app worker
if __name__ == '__main__':
    celery_app.start()
