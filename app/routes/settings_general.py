
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.crud import get_org_settings, upsert_org_settings
from ..services.auth_deps import get_current_user, require_role
import app.common.db.db as db_module
from datetime import datetime
from ..utils.logger import get_logger
logger = get_logger(__name__)

from bson import ObjectId

router = APIRouter(prefix="/settings/general", tags=["settings-general"])


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



@router.get("/", response_model=Dict[str, Any])
# async def read_general_settings(user: Dict[str, Any] = Depends(get_current_user)):
async def read_general_settings():
    try:
        logger.info("Fetching general settings for user")
        
        user_id = "8d8b7dff-a988-41ed-a63d-d59eb6d9ac0d"
        logger.debug(f"User ID: {user_id}")
        
        time_zone = "pt"  # Default time zone
        # time_zone = datetime.utcnow()
        print(f"Time Zone: {time_zone}")

        # user = await db_module.db.users.find_one({"user_id": user_id})
        # logger.debug(f"User: {user}")
        # org_id = user.get("organization_id") or user.get("org_id")

        membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        role = membership.get("role")
        print(f"User Role: {role}")
        org_id = membership.get("org_id") 
        print(f"org_id: {org_id}")

        org = await db_module.db.organizations.find_one({"id": org_id})
        org = clean_mongo_doc(org)

        print(f"Organization: {org}")
        org_name = org.get("name") if org else None
        print("org_name", org_name)
        # org_id = org.get("id") if org else None
        # cfg = await get_org_settings(org_id)
        # print(f"General Settings: {org}")
        # if not cfg:

        if not org:
            logger.warning("Settings not found for org_id: %s", org_id)
            raise HTTPException(status_code=404, detail="Settings not found")
        logger.info("General settings fetched successfully for org_id: %s", org_id)

        rp = await db_module.db.retention_policies.find_one({"org_id": org_id})
        print(f"Retention Policy: {rp}")
        retention_days = int(rp.get("retention_days")/30)
        

        # return org_name

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
            "retention_days" : str(retention_days),
        }

        generalSettings = {
            "organization": organization,
            "retention": retention,
        }

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
@router.patch("/")
async def patch_general_settings(payload: Dict[str, Any]):
    try:
        logger.info("Patching general settings for user")
        print("-------------------------------")
        print("payload:", payload)
        print("-------------------------------")
        user_id = "8d8b7dff-a988-41ed-a63d-d59eb6d9ac0d"
        
        membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        print("membership:", membership)
        # role = membership.get("role")
        org_id = membership.get("org_id")
        # logger.debug(f"User ID: {user_id}, Role: {role}, Org ID: {org_id}")
        org = await db_module.db.organizations.find_one({"id": org_id})

        # org = clean_mongo_doc(org)
        # print(f"Cleaned Org Data: {org}")

        if not org:
            logger.warning("Organization not found for org_id: %s", org_id)
            raise HTTPException(status_code=404, detail="Organization not found")

        # time_zone = datetime.utcnow()

        rp = await db_module.db.retention_policies.find_one({"org_id": org_id})
        # print(f"Retention Policy get : {rp}")
        retention_days = rp.get("retention_days")
        print("retention_days---> ", retention_days)

        # org["name"] = payload.get("personalInformation")

        update_data = {}
        rp_update_data = {}

    
        update_data["name"] = payload["organization"]["name"]
        update_data["timezone"] = payload["organization"]["timezone"]
        rp_update_data["retention_days"] = payload["retention"]["retention_days"]
      
        if update_data:
            await db_module.db.organizations.update_one({"id": org_id}, {"$set": update_data})
        if rp_update_data:
            print("enter in Rp udpate block")
            await db_module.db.retention_policies.update_one({"org_id": org_id}, {"$set": rp_update_data})
            logger.info(f"General settings updated for org_id: {org_id}")

        # payload["org_id"] = org_id
        # updated = await upsert_org_settings(payload)
        # logger.info(f"General settings updsated for org_id: {org_id}")

        generalSettings = {
                    "organization": update_data,
                    "retention": rp_update_data,
        }

        return {
            "generalSettings": generalSettings,
            # "org_id": org_id,
            # "role": role,
            "success": "General settings update successfully",
        }
    
    except Exception as e:
        logger.error(f"Failed to update general settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update general settings")




