from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.crud import get_org_settings, upsert_org_settings
from ..services.auth_deps import get_current_user, require_role
import app.common.db.db as db_module

router = APIRouter(prefix="/settings/general", tags=["settings-general"])


@router.get("/", response_model=Dict[str, Any])
async def read_general_settings():
    print("Fetching general settings for user:")
    print("Fetching general settings for user:")
    print("Fetching general settings for user:")
    print("Fetching general settings for user:")

    user_id = "0eb0c564-1670-42b1-a392-22bedc1c599e"
    print(f"User ID: {user_id}")

    # user = await db_module.db.users.find_one({"user_id": user_id})
    # print(f"User: {user}")
    # org_id = user.get("organization_id") or user.get("org_id")


    org = await db_module.db.organizations.find_one({"user_id": user_id})


    cfg = await get_org_settings(org_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Settings not found")
    return cfg


@router.put("/", dependencies=[Depends(require_role(["Admin"]))])
async def put_general_settings(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    org_id = user.get("organization_id") or user.get("org_id")
    payload["organization_id"] = org_id
    updated = await upsert_org_settings(payload)
    return updated
