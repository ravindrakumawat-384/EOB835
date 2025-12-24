from celery import Celery
from celery.schedules import crontab

# Initialize Celery app
celery_app = Celery(
    'eob_processor',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Beat schedule - runs every 3 minutes
    beat_schedule={
        'process-pending-files-every-3-minutes': {
            'task': 'app.tasks.file_processor.process_pending_files',
            'schedule': 180.0,  # Every 3 minutes (in seconds)
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['app.tasks'])

