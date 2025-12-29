from celery import Celery
from celery.schedules import crontab

# Initialize Celery app
celery_app = Celery(
    'eob_processor',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['app.tasks.file_processor']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Beat schedule - runs every 5 minutes
    beat_schedule={
        'process-pending-files-every-1-minute': {
            'task': 'app.tasks.file_processor.process_pending_files',
            'schedule': 60.0,  # Every 1 minute (in seconds)
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['app.tasks'])

