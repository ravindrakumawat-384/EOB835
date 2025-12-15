from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from bson import ObjectId

import app.common.db.db as db_module
from ..services.crud import (
    list_team_members,
    create_team_member,
    update_team_member,
    delete_team_member,
)
from ..services.auth_deps import get_current_user, require_role
from ..utils.logger import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/settings/users", tags=["settings-users"])


# -------------------- SCHEMAS --------------------
class InviteUser(BaseModel):
    name: str
    email: str
    role: str

class UpdateUser(BaseModel):
    name: str
    email: str
    role: str
    status: bool
    userId: str

class TableHeaderAction(BaseModel):
    type: str
    icon: str
    styleClass: str


class TableHeader(BaseModel):
    field: Optional[str] = None
    label: str
    actions: Optional[List[TableHeaderAction]] = None


# if there is no action then field is mandatory


# class UserItem(BaseModel):
#     name: str
#     email: str
#     role: str
#     status: str

class UserItem(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str


class TeamMembersTableData(BaseModel):
    tableHeaders: List[TableHeader]
    tableData: List[UserItem]


class RolePermission(BaseModel):
    role: str
    description: str
    userCount: int


class UsersResponse(BaseModel):
    teamMembersTableData: TeamMembersTableData
    rolePermissions: List[RolePermission]
    success: str


# -------------------- UTILS --------------------
async def serialize_usr(doc: dict) -> UserItem:
    if not doc:
        return None

    user = await db_module.db.users.find_one({"id": doc["user_id"]}, {"_id": 0})
    logger.info(f"Fetched user for user_id: {user}")

    status = "active" if user.get("is_active") else "inactive"

    return UserItem(
        id=user["id"],
        name=user["full_name"],
        email=user["email"],
        role=doc.get("role"),
        status=status,
    )


# -------------------- GET USERS --------------------
@router.get("/", response_model=UsersResponse)
async def get_users():
    try:
        # TODO: Replace with actual logged-in user
        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4"

        org = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        org_id = org.get("org_id")

        # fetch org members
        members = (
            await db_module.db.organization_memberships.find(
                {"org_id": org_id}, {"_id": 0}
            ).to_list(length=None)
        )

        # serialize all members
        all_users = [await serialize_usr(doc) for doc in members]

        table_headers = [
            {"field": "name", "label": "Name"},
            {"field": "email", "label": "Email"},
            {"field": "role", "label": "Role"},
            {"field": "status", "label": "Status"},
            {
                "label": "Actions",
                "actions": [
                    {
                        "type": "edit",
                        "icon": "pi pi-pencil",
                        "styleClass": "p-button-text p-button-sm",
                    },
                    {
                        "type": "delete",
                        "icon": "pi pi-trash",
                        "styleClass": "p-button-text p-button-sm p-button-danger",
                    },
                ],
            },
        ]

        # EXAMPLE static permissions (replace with your actual logic)
        role_permissions = [
            RolePermission(
                role="admin",
                description="Full access to all features and settings",
                userCount=sum(1 for u in all_users if u.role == "admin"),
            ),
            RolePermission(
                role="reviewer",
                description="Basic read/write access",
                userCount=sum(1 for u in all_users if u.role == "reviewer"),
            ),

            RolePermission(
                role="viewer",
                description="Basic read",
                userCount=sum(1 for u in all_users if u.role == "viewer"),
            ),
        ]

        return UsersResponse(
            teamMembersTableData=TeamMembersTableData(
                tableHeaders=[TableHeader(**h) for h in table_headers],
                tableData=all_users,
            ),
            rolePermissions=role_permissions,
            success="User & teams details fetched successfully",
        )

    except Exception as e:
        logger.error(f"Failed to fetch team members: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch team members")


# -------------------- ADD USER --------------------
@router.post("/")
async def post_user(payload: Dict[str, Any]):
    try:
        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4"  # admin

        # find new user
        usr = await db_module.db.users.find_one({"email": payload["email"]}, {"_id": 0})
        if not usr:
            raise HTTPException(status_code=404, detail="User not found")

        add_user_id = usr["id"]

        org = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        org_id = org.get("org_id")

        payload_update = {
            "org_id": org_id,
            "user_id": add_user_id,
            "role": payload["role"],
        }

        member = await create_team_member(payload_update)
        logger.info(f"Created team member: {member}")

        return {"message": "User added successfully", "member": member}

    except Exception as e:
        logger.error(f"Failed to create team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to create team member")


# -------------------- UPDATE USER --------------------
@router.patch("/")
async def patch_user(payload: Dict[str, Any]):
    try:
        print()
        print("payload in patch_user:", payload)
        print()
        updated = await update_team_member(payload)

        if not updated:
            raise HTTPException(status_code=404, detail="Member not found")

        return {"Success": "User updated successfully"}

    except Exception as e:
        logger.error(f"Failed to update user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")


# -------------------- DELETE USER --------------------
@router.delete("/{member_id}")
async def del_user(member_id: str):
    try:
        admin_id = "6f64216e-7fbd-4abc-b676-991a121a95e4"

        org = await db_module.db.organization_memberships.find_one({"user_id": admin_id})
        org_id = org.get("org_id")

        deleted = await delete_team_member(member_id, org_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Member not found")

        return {"message": "User deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete team member")
