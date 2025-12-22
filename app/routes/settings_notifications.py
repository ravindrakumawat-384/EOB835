
import psycopg2
from app.common.db.pg_db import get_pg_conn
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/settings/notifications", tags=["settings-notifications"])

# DB = init_db()


async def serialize_usr(doc: dict) -> dict:
    """
    Convert MongoDB document into JSON-safe organization object.
    """
    if not doc:
        return None

    # # user = db_module.db.users.find_one({"user_id": doc["user_id"]})
    # user = await db_module.db.users.find_one({"id": doc["user_id"]},{"_id": 0})
    # logger.info(f"Fetched user for user_id: {user}")
    # print("user status----> ", user["is_active"])
    # if user["is_active"]== True:
    #     status = "Active"
    # else:
    #     status = "Inactive"
    

    notification_preference = {
        "upload_completed": doc.get("upload_completed"),
        "review_required": doc.get("review_required"),
        "exceptions_detected": doc.get("exceptions_detected"),
        "export_ready": doc.get("export_ready"),
    }

    print("notification_preference:", notification_preference)

    return {
        "success": True,
        "message": "Notification preferences fetched successfully",
        "notification_preference" : notification_preference,
    }


@router.get("/", response_model=Dict[str, Any])
async def get_notifications(user: Dict[str, Any] = Depends(get_current_user)):
# async def get_notifications():
    try:
        # user_id = "7dd718f4-b3fb-4167-bb6c-0f8facc3f775" # grv
        # user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv
        user_id = user.get("id")
        print("User ID:", user_id)
        logger.info(f"Fetching notification preferences for user_id: {user_id}")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT upload_completed, review_required, export_ready, exceptions_detected FROM notification_preferences WHERE user_id = %s LIMIT 1", (user_id,))
                pref = cur.fetchone()
                print("pref---------->  ", pref)
                if not pref:
                    logger.warning(f"Preferences not found for user_id: {user_id}")
                    raise HTTPException(status_code=404, detail="Preferences not found")
                all_pref = {
                    "upload_completed": pref["upload_completed"],
                    "review_required": pref["review_required"],
                    "export_ready": pref["export_ready"],
                    "exceptions_detected": pref["exceptions_detected"]
                }
        logger.debug(f"Notification preferences data: {all_pref}")
        logger.info(f"Notification preferences fetched for user_id: {user_id}")
        return all_pref
    except Exception as e:
        logger.error(f"Failed to fetch notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch notification preferences")



@router.patch("/", response_model=Dict[str, Any])
async def upsert_notifications(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
# async def upsert_notifications(payload: Dict[str, Any]):
    try:
        # user_id = "7dd718f4-b3fb-4167-bb6c-0f8facc3f775" # grv
        # user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv
        user_id = user.get("id")
        print("User ID:", user_id)
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM notification_preferences WHERE user_id = %s LIMIT 1", (user_id,))
                exists = cur.fetchone()
                if exists:
                    cur.execute(
                        "UPDATE notification_preferences SET upload_completed = %s, review_required = %s, export_ready = %s, exceptions_detected = %s, updated_at = NOW() WHERE user_id = %s",
                        (payload.get("upload_completed"), payload.get("review_required"), payload.get("export_ready"), payload.get("exceptions_detected"), user_id)
                    )
                else:
                    cur.execute(
                        "INSERT INTO notification_preferences (user_id, upload_completed, review_required, export_ready, exceptions_detected, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,NOW(),NOW())",
                        (user_id, payload.get("upload_completed"), payload.get("review_required"), payload.get("export_ready"), payload.get("exceptions_detected"))
                    )
                conn.commit()
        logger.info(f"Notification preferences upserted for user_id: {user_id}")
        return {"success": True, "message": "Notification preferences upserted"}
    except Exception as e:
        logger.error(f"Failed to upsert notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert notification preferences")
