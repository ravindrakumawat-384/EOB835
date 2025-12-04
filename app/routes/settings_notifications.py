from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.crud import get_notification_pref, upsert_notification_pref
from ..services.auth_deps import get_current_user

router = APIRouter(prefix="/settings/notifications", tags=["settings-notifications"])


@router.get("/", response_model=Dict[str, Any])
async def get_notifications(user: Dict[str, Any] = Depends(get_current_user)):
    pref = await get_notification_pref(user["id"])
    if not pref:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return pref


@router.put("/", response_model=Dict[str, Any])
async def upsert_notifications(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    payload["user_id"] = user["id"]
    saved = await upsert_notification_pref(payload)
    return saved
