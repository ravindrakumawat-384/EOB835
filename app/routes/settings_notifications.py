
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.crud import get_notification_pref, upsert_notification_pref
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
from app.common.db.db import init_db
import app.common.db.db as db_module

logger = get_logger(__name__)
router = APIRouter(prefix="/settings/notifications", tags=["settings-notifications"])

DB = init_db()


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

        # pref = await get_notification_pref(user_id)
        # pref = DB.db.organizations.find({}, {"_id": 0})  # remove MongoDB ObjectId

        # org = await DB.db.organization_memberships.find_one({"user_id": user_id})
        # org = await db_module.db.organizations.find_one({"user_id": user_id})
        # org_id = org["org_id"]
        # print("org:", org)
        # print("org:", org)

        pref = await db_module.db.notification_preferences.find_one({"user_id": user_id},{"_id": 0})
        print()
        print("pref---------->  ", pref)

        all_pref = {
            "upload_completed" : pref["upload_completed"],
            "review_required" : pref["review_required"],
            "export_ready" : pref["export_ready"],
            "exceptions_detected" : pref["exceptions_detected"]
        }
        
        
        logger.debug(f"Notification preferences data: {all_pref}")
        if not all_pref:
            logger.warning(f"Preferences not found for user_id: {user_id}")
            raise HTTPException(status_code=404, detail="Preferences not found")
        
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
        
        # payload["user_id"] = user_id

        saved = await upsert_notification_pref(payload,user_id)
        logger.info(f"Notification preferences upserted for user_id: {user_id}")
        return saved
    except Exception as e:
        logger.error(f"Failed to upsert notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert notification preferences")
