
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from ..services.crud import list_team_members, create_team_member, update_team_member, delete_team_member
from ..services.auth_deps import get_current_user, require_role
from ..utils.logger import get_logger
import app.common.db.db as db_module
from bson import ObjectId
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter(prefix="/settings/users", tags=["settings-users"])


class InviteUser(BaseModel):
    full_name : str
    email: str
    role: str


# def clean_mongo_doc(doc):
#     if not doc:
#         return None
#     doc = dict(doc)
#     doc.pop('_id', None)
    
#     # convert ObjectId fields (if any)
#     for key, val in doc.items():
#         if isinstance(val, ObjectId):
#             doc[key] = str(val)
#     return doc


async def serialize_usr(doc: dict) -> dict:
    """
    Convert MongoDB document into JSON-safe organization object.
    """
    if not doc:
        return None

    # user = db_module.db.users.find_one({"user_id": doc["user_id"]})
    user = await db_module.db.users.find_one({"id": doc["user_id"]},{"_id": 0})
    logger.info(f"Fetched user for user_id: {user}")
    print("user status----> ", user["is_active"])
    if user["is_active"]== True:
        status = "Active"
    else:
        status = "Inactive"

    user_details = {
        "full_name": user["full_name"],
        "email": user["email"],
        "role": doc.get("role"),
        "status": status,
    }

    return {
        "success": True,
        "message": "Users fetched successfully",
        "user_details" : user_details,
    }


@router.get("/", response_model=List[Dict[str, Any]])
# async def get_users(user: Dict[str, Any] = Depends(get_current_user)):
async def get_users():
    try:    
        # org_id = user.get("organization_id")
        # members = await list_team_members(org_id)

        # user_id = "bbfa1ab8-45bc-428c-8283-0815d33779db"
        user_id = "8d8b7dff-a988-41ed-a63d-d59eb6d9ac0d"

        org = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        print("org:", org)
        print("org:", org)
        print("org:", org)
        print("org:", org)
        print("org:", org)
        try: 
            print("Enter in getting organisation")
            print("Enter in getting organisation")
            print("Enter in getting organisation")
            org_id = org["org_id"]
            print("org_id:", org_id) 
            org_id = org.get("org_id") 
            print("org_id:", org_id) 
        except:
            print("Enter in organisation")
            print("Enter in organisation")
            print("Enter in organisation")
            org_id = None

        # remove MongoDB ObjectId --> {"_id": 0}
        all_members2 = await db_module.db.organization_memberships.find({"org_id": org_id},{"_id": 0}).to_list(length=None) 
        print("all_members2:", all_members2)

        all_users = []
        for doc in all_members2:
            all_users.append(await serialize_usr(doc))
        
        print("all_users:", all_users)

        return all_users
    
    
    except Exception as e:
        logger.error(f"Failed to fetch team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch team members")


# @router.post("/", dependencies=[Depends(require_role(["Admin"]))])
@router.post("/")
# async def post_user(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
async def post_user(payload: Dict[str, Any]):
    try:
        print("payload:", payload)
        user_id = "8d8b7dff-a988-41ed-a63d-d59eb6d9ac0d"
        # admin will add user to the organisation member table
        # payload["organization_id"] = user.get("organization_id") or user.get("org_id")
        add_user_id = "b7e9f26d-7537-43bc-b9fc-7aa7a6de7a51"
        usr = await db_module.db.users.find_one({"email": payload["email"]},{"_id": 0})
        print("usr", usr)
        print("usr.user_id", usr["id"])
        add_user_id = usr["id"]
        print("add_user_id", add_user_id)
        print("add_user_id", add_user_id)
        print("add_user_id", add_user_id)
        print("add_user_id", add_user_id)
        print("add_user_id", add_user_id)
        print("add_user_id", add_user_id)
        org = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        org_id = org.get("org_id")  

        payload_update = {
            "org_id": org_id,
            "user_id": add_user_id,
            "role": payload["role"],}
        
        print("payload after org_id & user_id added:", payload_update)
        
        member = await create_team_member(payload_update)
        logger.info(f"Created team member for org_id: {payload_update['org_id']}")
        return member
    except Exception as e:
        logger.error(f"Failed to create team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to create team member")


# @router.put("/{member_id}", dependencies=[Depends(require_role(["Admin"]))])
# async def put_user(member_id: str, payload: Dict[str, Any]):
@router.patch("/")
async def patch_user(payload: Dict[str, Any]):
    try:
        # print("member_id:", member_id)
        print("payload:", payload)
        updated = await update_team_member(payload)
        if not updated:
            logger.warning(f"Member not found: {payload.get('userId')}")
            raise HTTPException(status_code=404, detail="Member not found")
        logger.info(f"Updated team member: {payload["userId"]}")
        return {"message": "User Updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update User detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to update team member")


# @router.delete("/{member_id}", dependencies=[Depends(require_role(["Admin"]))])
@router.delete("/{member_id}")
async def del_user(member_id: str):
    try:
        admin_id = "de34a061-54d0-4e87-8f43-bbf5fe98a3c6" #Admin id
        org = await db_module.db.organization_memberships.find_one({"user_id": admin_id})
        org_id = org["org_id"]
        print("org_id:", org_id)
        print("org_id:", org_id)
        print("org_id:", org_id)
        print("org_id:", org_id)

        deleted = await delete_team_member(member_id, org_id)
        if not deleted:
            logger.warning(f"Member not found: {member_id}")
            raise HTTPException(status_code=404, detail="Member not found")
        logger.info(f"Deleted team member: {member_id}")
        return {"Message": "User deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete team member")
