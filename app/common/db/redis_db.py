import redis
from app.common.config import settings

def get_redis_client():
    """
    Returns a Redis client instance.
    """
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
