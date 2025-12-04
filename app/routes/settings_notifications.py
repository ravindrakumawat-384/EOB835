
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.crud import get_notification_pref, upsert_notification_pref
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/settings/notifications", tags=["settings-notifications"])


@router.get("/", response_model=Dict[str, Any])
async def get_notifications(user: Dict[str, Any] = Depends(get_current_user)):
    try:
        logger.info(f"Fetching notification preferences for user_id: {user['id']}")
        pref = await get_notification_pref(user["id"])
        if not pref:
            logger.warning(f"Preferences not found for user_id: {user['id']}")
            raise HTTPException(status_code=404, detail="Preferences not found")
        logger.info(f"Notification preferences fetched for user_id: {user['id']}")
        return pref
    except Exception as e:
        logger.error(f"Failed to fetch notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch notification preferences")


@router.put("/", response_model=Dict[str, Any])
async def upsert_notifications(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    try:
        payload["user_id"] = user["id"]
        saved = await upsert_notification_pref(payload)
        logger.info(f"Notification preferences upserted for user_id: {user['id']}")
        return saved
    except Exception as e:
        logger.error(f"Failed to upsert notification preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to upsert notification preferences")
