import json
import time
import redis
from app.common.config import settings

def test_redis_orchestration():
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    PROCESSING_JOB_IDS = "processing_job_ids"
    JOB_STATE_PREFIX = "job_state:"
    
    # Clean up before test
    r.delete(PROCESSING_JOB_IDS)
    for key in r.keys(f"{JOB_STATE_PREFIX}*"):
        r.delete(key)
    
    job_id = "test_job_123"
    job_key = f"{JOB_STATE_PREFIX}{job_id}"
    
    print(f"--- Testing Job Start ---")
    is_new = r.sadd(PROCESSING_JOB_IDS, job_id)
    print(f"Is new job: {is_new}")
    r.set(job_key, json.dumps({"status": "RUNNING", "last_run": time.time(), "retry_count": 0}))
    
    print(f"--- Testing Duplicate Job ---")
    is_new_dup = r.sadd(PROCESSING_JOB_IDS, job_id)
    print(f"Is new job (duplicate): {is_new_dup}")
    
    print(f"--- Testing Job Success ---")
    r.srem(PROCESSING_JOB_IDS, job_id)
    r.delete(job_key)
    print(f"Job removed from Redis: {not r.sismember(PROCESSING_JOB_IDS, job_id)}")
    
    print(f"--- Testing Job Failure ---")
    r.sadd(PROCESSING_JOB_IDS, job_id)
    r.set(job_key, json.dumps({"status": "FAILED", "last_run": time.time(), "retry_count": 1}))
    print(f"Job in Redis after failure: {r.sismember(PROCESSING_JOB_IDS, job_id)}")
    state = json.loads(r.get(job_key))
    print(f"Job status: {state['status']}, Retry count: {state['retry_count']}")
    
    print(f"--- Testing Retry Logic ---")
    # Simulate scheduler run
    is_new_retry = r.sadd(PROCESSING_JOB_IDS, job_id)
    print(f"Is new job (retry): {is_new_retry}") # Should be 0 because it's already in SET
    
    if not is_new_retry:
        state = json.loads(r.get(job_key))
        if state['status'] == 'FAILED' and state['retry_count'] < 3:
            print(f"Eligible for retry: True")
            
    # Clean up after test
    r.delete(PROCESSING_JOB_IDS)
    r.delete(job_key)

if __name__ == "__main__":
    test_redis_orchestration()
