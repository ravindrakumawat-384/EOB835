import redis
from celery.signals import task_prerun, task_success, task_failure
from app.common.config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize Redis client
# Using from_url to handle the REDIS_URL from settings
redis_client = redis.from_url(settings.REDIS_URL)

ACTIVE_TASKS_KEY = "active_tasks"

@task_prerun.connect
def on_task_prerun(task_id, task, *args, **kwargs):
    """
    On Celery task start, store the task ID in a Redis set named active_tasks.
    Enforces uniqueness using SADD.
    """
    try:
        # SADD returns 1 if element was added, 0 if it already existed
        added = redis_client.sadd(ACTIVE_TASKS_KEY, task_id)
        if added:
            logger.info(f"Task {task_id} ({task.name}) added to {ACTIVE_TASKS_KEY}")
        else:
            logger.warning(f"Task {task_id} ({task.name}) already exists in {ACTIVE_TASKS_KEY}")
    except Exception as e:
        logger.error(f"Failed to add task {task_id} to Redis: {e}")

@task_success.connect
def on_task_success(sender, **kwargs):
    """
    On successful task completion, remove the task ID from active_tasks.
    """
    task_id = sender.request.id
    try:
        removed = redis_client.srem(ACTIVE_TASKS_KEY, task_id)
        if removed:
            logger.info(f"Task {task_id} successfully completed and removed from {ACTIVE_TASKS_KEY}")
        else:
            logger.warning(f"Task {task_id} was not found in {ACTIVE_TASKS_KEY} on success")
    except Exception as e:
        logger.error(f"Failed to remove task {task_id} from Redis on success: {e}")

@task_failure.connect
def on_task_failure(task_id, exception, traceback, einfo, *args, **kwargs):
    """
    On task failure, crash, timeout, or exception, do NOT remove the task ID from Redis.
    Redis must be the single source of truth for running/failed tasks.
    """
    logger.error(f"Task {task_id} failed. Keeping it in {ACTIVE_TASKS_KEY} as per requirements. Error: {exception}")
    # We explicitly do nothing here to keep the task_id in the set.
