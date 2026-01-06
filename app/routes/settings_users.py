
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import secrets
from datetime import timedelta
from ..services.auth_deps import get_current_user, require_role
from ..utils.logger import get_logger
from app.common.db.pg_db import get_pg_conn
import psycopg2.extras
from ..services.email_service import send_email_stub, send_invite_email
from ..utils.auth_utils import hash_password
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

class UserItem(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str
    is_logged: bool
    is_current_user: bool


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
async def serialize_usr(doc: dict, current_user_id: str) -> UserItem:
    if not doc:
        return None
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, full_name, email, is_active, last_login_at FROM users WHERE id = %s LIMIT 1", (doc["user_id"],))
            user = cur.fetchone()
            logger.info(f"Fetched user for user_id: {user}")
            status = "active" if user and user.get("is_active") else "inactive"
            
            last_login_at=user.get("last_login_at")
            is_logged = False if not last_login_at else True
            
            return UserItem(
                id=user["id"] if user else doc["user_id"],
                name=user["full_name"] if user else "",
                email=user["email"] if user else "",
                role=doc.get("role"),
                status=status,
                is_logged=is_logged,
                is_current_user=user["id"] == current_user_id
            )


# -------------------- GET USERS -----------------
@router.get("/get_users", response_model=UsersResponse, )
async def get_users(user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get org_id for current user
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]
                # Get all memberships for org
                cur.execute("SELECT user_id, role FROM organization_memberships WHERE org_id = %s", (org_id,))
                members = cur.fetchall()
                # Exclude the current user from members
                # all_users = [await serialize_usr(doc) for doc in members if doc["user_id"] != user_id]
                all_users = [await serialize_usr(doc,user_id) for doc in members]
                
                print()
                print("all_users-----> ", all_users)
                print()

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
        role_permissions = [
            RolePermission(
                role="admin",
                description="Full access to all features and settings",
                userCount=sum(1 for u in all_users if u and u.role == "admin"),
            ),
            RolePermission(
                role="reviewer",
                description="Basic read/write access",
                userCount=sum(1 for u in all_users if u and u.role == "reviewer"),
            ),
            RolePermission(
                role="viewer",
                description="Basic read",
                userCount=sum(1 for u in all_users if u and u.role == "viewer"),
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
@router.post("/invite_user")
async def invite_user(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
    # try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get org_id for current user
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]

                # Get organization
                cur.execute("SELECT name, timezone FROM organizations WHERE id = %s LIMIT 1", (org_id,))
                org = cur.fetchone()
                if not org:
                    logger.warning("Organization not found for org_id: %s", org_id)
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_name = org["name"]

                # Check if user exists
                cur.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (payload["email"],))
                usr = cur.fetchone()
                if not usr:
                    # Create new user
                    import uuid
                    new_user_id = str(uuid.uuid4())
                    password = hash_password("Password@123")
                    cur.execute(
                        "INSERT INTO users (id, email, full_name, password_hash, is_active, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, NOW(), NOW())",
                        (new_user_id, payload["email"], payload.get("name", ""), password, False)
                    )
                    add_user_id = new_user_id


                    # Generate invite token and expiration
                    invite_token = secrets.token_urlsafe(32)
                    expires_at = datetime.utcnow() + timedelta(minutes=60)
                    # Store invite token and expiration in refresh_tokens table
                    cur.execute(
                        "INSERT INTO refresh_tokens (jti, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
                        (invite_token, add_user_id, datetime.utcnow(), expires_at)
                    )

                    # Send invite email with expiration info
                    temp_pass = "Password@123"
                    # invite_link = f"https://your-app-url.com/invite?token={invite_token}"
                    # email_body = f"Hello {payload.get('name', '')},\nYou have been invited to join {org_name}. Please use this link to set your password and activate your account.\n\nInvite Link: {invite_link}\nThis link will expire in 24 hours."
                    # send_invite_email(payload["email"], temp_pass, payload.get("name", ""), org_name, email_body=email_body)

                    send_invite_email(payload["email"], temp_pass, payload.get("name", ""), org_name, invite_token)
                else:
                    raise HTTPException(status_code=500, detail="User already exists. Please use a different email.")
                # Insert new membership with generated UUID for id
                membership_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO organization_memberships (id, org_id, user_id, role, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (membership_id, org_id, add_user_id, payload["role"], datetime.utcnow())
                )
                member_id = cur.fetchone()["id"]

                # # Fetch last_login_at for the new user
                # cur.execute("SELECT last_login_at FROM users WHERE id = %s LIMIT 1", (add_user_id,))
                # user_row = cur.fetchone()
                # last_login_at = user_row["last_login_at"] if user_row else None
                # is_logged = False if not last_login_at else True
                
                conn.commit()
            logger.info(f"Created team member: {member_id}")
            
            

            return {"success": "User added successfully"}
    # except Exception as e:
    #     logger.error(f"Failed to create team member: {e}")
    #     raise HTTPException(status_code=500, detail="Failed to create team member.")


# -------------------- UPDATE USER --------------------
@router.patch("/patch_user", dependencies=[Depends(require_role(["Admin"]))])
async def patch_user(payload: Dict[str, Any]):
    try:
        member_id = payload.get("userId")
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET full_name = %s, email = %s, is_active = %s WHERE id = %s",
                    (payload["name"], payload["email"], payload["status"], member_id)
                )
                cur.execute(
                    "UPDATE organization_memberships SET role = %s WHERE user_id = %s",
                    (payload["role"], member_id)
                )
                conn.commit()
        return {"success": "User updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")


# -------------------- DELETE USER --------------------
@router.delete("/{member_id}")
async def del_user(member_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        user_id = user.get("id")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get org_id for current user
                cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                org = cur.fetchone()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
                org_id = org["org_id"]
                # Delete membership
                # cur.execute(
                #     "DELETE FROM organization_memberships WHERE user_id = %s AND org_id = %s",
                #     (member_id, org_id)
                # )
                cur.execute(
                    "DELETE FROM users WHERE id = %s",
                    (member_id,)
                )
                conn.commit()
        return {"message": "User deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete team member: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete team member")
