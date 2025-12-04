
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.crud import get_org_settings, upsert_org_settings
from ..services.auth_deps import get_current_user, require_role
import app.common.db.db as db_module
from ..utils.logger import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/settings/general", tags=["settings-general"])


@router.get("/", response_model=Dict[str, Any])
async def read_general_settings():
    try:
        logger.info("Fetching general settings for user")
        user_id = "0eb0c564-1670-42b1-a392-22bedc1c599e"
        logger.debug(f"User ID: {user_id}")
        # user = await db_module.db.users.find_one({"user_id": user_id})
        # logger.debug(f"User: {user}")
        # org_id = user.get("organization_id") or user.get("org_id")
        org = await db_module.db.organizations.find_one({"user_id": user_id})
        org_id = org.get("id") if org else None
        cfg = await get_org_settings(org_id)
        if not cfg:
            logger.warning("Settings not found for org_id: %s", org_id)
            raise HTTPException(status_code=404, detail="Settings not found")
        logger.info("General settings fetched successfully for org_id: %s", org_id)
        return cfg
    except Exception as e:
        logger.error(f"Failed to fetch general settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch general settings")


@router.put("/", dependencies=[Depends(require_role(["Admin"]))])
async def put_general_settings(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    try:
        org_id = user.get("organization_id") or user.get("org_id")
        payload["organization_id"] = org_id
        updated = await upsert_org_settings(payload)
        logger.info(f"General settings updated for org_id: {org_id}")
        return updated
    except Exception as e:
        logger.error(f"Failed to update general settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update general settings")
