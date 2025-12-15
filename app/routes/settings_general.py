
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.crud import get_org_settings, upsert_org_settings
from ..services.auth_deps import get_current_user, require_role
import app.common.db.db as db_module
from datetime import datetime
from pydantic import BaseModel
from ..utils.logger import get_logger
logger = get_logger(__name__)

from bson import ObjectId

router = APIRouter(prefix="/settings/general", tags=["settings-general"])


class UpdateGeneral(BaseModel):
    name: str
    timezone: str
    retention_days: str
    org_id: str


def clean_mongo_doc(doc):
    if not doc:
        return None
    doc = dict(doc)
    doc.pop('_id', None)
    
    # convert ObjectId fields (if any)
    for key, val in doc.items():
        if isinstance(val, ObjectId):
            doc[key] = str(val)
    return doc



@router.get("", response_model=Dict[str, Any])
async def read_general_settings(user: Dict[str, Any] = Depends(get_current_user)):
# async def read_general_settings():
    try:
        logger.info("Fetching general settings for user")        
        # user_id = "7dd718f4-b3fb-4167-bb6c-0f8facc3f775" # grv
        # user_id = "b6ee4982-b5ec-425f-894d-4324adce0f36" #rv
        print('user=====', user.get("id"))
        print('user=====', user.get("id"))
        print('user=====', user.get("id"))
        print('user=====', user.get("id"))
        print('user=====', user.get("id"))
        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv


        logger.debug(f"User ID: {user_id}")
        
        time_zone = "pt"  # Default time zone
        # time_zone = datetime.utcnow()

        # user = await db_module.db.users.find_one({"user_id": user_id})
        # logger.debug(f"User: {user}")
        # org_id = user.get("organization_id") or user.get("org_id")

        membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})

        role = membership.get("role")
        org_id = membership.get("org_id") 
        org = await db_module.db.organizations.find_one({"id": org_id})
        org = clean_mongo_doc(org)
        org_name = org.get("name") if org else None

        # org_id = org.get("id") if org else None
        # cfg = await get_org_settings(org_id)
        # print(f"General Settings: {org}")
        # if not cfg:

        if not org:
            logger.warning("Settings not found for org_id: %s", org_id)
            raise HTTPException(status_code=404, detail="Settings not found")
        logger.info("General settings fetched successfully for org_id: %s", org_id)

        rp = await db_module.db.retention_policies.find_one({"org_id": org_id})
        
        # retention_days = int(rp.get("retention_days")/30)
        retention_days = str(rp.get("retention_days"))
        

        organization = {
            "name": org_name,
            "timezone": time_zone,
            # "id": org.get("id"),
            # "slug": org.get("slug"),
            # "status": org.get("status"),
            # "settings_json": org.get("settings_json", {}),
        }

        retention = {
            # "retentionPolicy" : f"{retention_days} Months",
            "retention_days" : retention_days,
        }

        generalSettings = {
            "organization": organization,
            "retention": retention,
        }

        logger.debug(f"General Settings Data: {generalSettings}")
        return {
            "generalSettings": generalSettings,
            "org_id": org_id,
            "role": role,
            "success" : "General settings fetched successfully",
        }


    except Exception as e:
        logger.error(f"Failed to fetch general settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch general settings")


# @router.put("/", dependencies=[Depends(require_role(["Admin"]))])
@router.patch("")
async def patch_general_settings(payload: Dict[str, Any]):
    try:
        # user_id = "7dd718f4-b3fb-4167-bb6c-0f8facc3f775" # grv
        # user_id = "b6ee4982-b5ec-425f-894d-4324adce0f36" #rv
        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv

        
        membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})

        org_id = membership.get("org_id")
        org = await db_module.db.organizations.find_one({"id": org_id})

        if not org:
            logger.warning("Organization not found for org_id: %s", org_id)
            raise HTTPException(status_code=404, detail="Organization not found")

        rp = await db_module.db.retention_policies.find_one({"org_id": org_id})

        update_data = {}
        rp_update_data = {}
    
        update_data["name"] = payload["organization"]["name"]
        update_data["timezone"] = payload["organization"]["timezone"]
        rp_update_data["retention_days"] = payload["retention"]["retention_days"]
      
        if update_data:
            await db_module.db.organizations.update_one({"id": org_id}, {"$set": update_data})

        if rp_update_data:
            await db_module.db.retention_policies.update_one({"org_id": org_id}, {"$set": rp_update_data})

        # payload["org_id"] = org_id
        # updated = await upsert_org_settings(payload)
        # logger.info(f"General settings updsated for org_id: {org_id}")

        generalSettings = {
                    "organization": update_data,
                    "retention": rp_update_data,
        }

        logger.debug(f"Updated General Settings Data: {generalSettings}")

        return {
            "generalSettings": generalSettings,
            # "org_id": org_id,
            # "role": role,
            "success": "General settings update successfully",
        }
    
    except Exception as e:
        logger.error(f"Failed to update general settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update general settings")




