from typing import Any
from ..common.db.db import db
import app.common.db.db as db_module
from app.common.db.db import init_db
from ..common.db.models import Organization, User, OrganizationMembership, UserPreferences, Notification, EmailEvent, RetentionPolicy
from ..common.db.models import TeamMember, AuditLog
# --------------------------------------
from typing import Optional, List, Dict, Any
from datetime import datetime

from bson import ObjectId

DB = init_db()
# will import as per need OrganizationSettings, NotificationPreferences



# Note: db must be initialised via init_db() before calling these.


async def insert_org(org: Organization) -> Any:
    await db.organizations.insert_one(org.dict())
    return org.dict()


async def get_org_by_id(org_id: str) -> Any:
    return await db.organizations.find_one({"id": org_id})


async def insert_user(user: User) -> Any:
    await db.users.insert_one(user.dict())
    return user.dict()


async def get_user_by_email(email: str) -> Any:
    return await db.users.find_one({"email": email})


# add other helpers as needed...
async def insert_membership(m: OrganizationMembership) -> Any:
    await db.organization_memberships.insert_one(m.dict())
    return m.dict()


async def insert_pref(p: UserPreferences) -> Any:
    await db.user_preferences.insert_one(p.dict())
    return p.dict()


async def insert_notification(n: Notification) -> Any:
    await db.notifications.insert_one(n.dict())
    return n.dict()


async def insert_email_event(e: EmailEvent) -> Any:
    await db.email_events.insert_one(e.dict())
    return e.dict()


async def insert_retention(r: RetentionPolicy) -> Any:
    await db.retention_policies.insert_one(r.dict())
    return r.dict()





# ======================


def clean_mongo_doc(doc):
    # if not doc:
    #     return None
    # doc = dict(doc)
    # doc.pop('_id', None)
    
    # # convert ObjectId fields (if any)
    # for key, val in doc.items():
    #     if isinstance(val, ObjectId):
    #         doc[key] = str(val)
    # return doc

    if doc is None:
        return None

    if isinstance(doc, list):
        return [clean_mongo_doc(item) for item in doc]

    if isinstance(doc, ObjectId):
        return str(doc)

    if not isinstance(doc, dict):
        return doc

    cleaned = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            cleaned[key] = str(value)
        else:
            cleaned[key] = clean_mongo_doc(value)
    return cleaned



# Organization settings
async def get_org_settings(org_id: str) -> Optional[Dict[str, Any]]:
    print(f"Fetching org settings for org_id: {org_id}")
    print(f"Fetching org settings for org_id: {org_id}")
    print(f"Fetching org settings for org_id: {org_id}")
    # return await db.organization_settings.find_one({"organization_id": org_id})
    return await db_module.db.organizations.find_one({"id": org_id})


async def upsert_org_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    print()
    data["updated_at"] = now 
    # await db.organization_settings.update_one(
    print(f"Updating org settings for org_id: {data['org_id']}")

    org = await db_module.db.organizations.find_one({"id": data['org_id']})
    org = clean_mongo_doc(org)
    print()
    print(f"Existing org data: {org}")
    
    print("data on payload:", data)
    print("data[id]", data["id"])

    await db_module.db.organizations.update_one(
        {"id": data["id"]}, {"$set": data}, upsert=True
    )
    return await get_org_settings(data["id"])


# Team members
async def list_team_members(org_id: str) -> List[Dict[str, Any]]:
    cursor = db.team_members.find({"id": org_id})
    return await cursor.to_list(length=None)


async def create_team_member(payload: Dict[str, Any]) -> Dict[str, Any]:
    # member = TeamMember(**payload).dict()
    print("Creating team member with payload:", payload)
    # member = OrganizationMembership(**payload).dict()
    # print("Member to insert:", member)
    # await db.organization_memberships.insert_one(member)
    # print("Member inserted:", member)

    print("payload[org_id]", payload["org_id"])
    invt_usr = OrganizationMembership(org_id=payload["org_id"], user_id=payload["user_id"], role=payload["role"])
    #To-do
    # # will add created_at=datetime.utcnow(), updated_at=datetime.utcnow()
    await DB.organization_memberships.insert_one(invt_usr.dict())

    return {"success": "User Added successfully"}


# async def update_team_member(member_id: str, payload: Dict[str, Any]) -> int:
async def update_team_member(payload: Dict[str, Any]) -> int:
    print("Updating team member with payload:", payload)

    user_id = payload.get("userId")
    print("user_id:", user_id)

    # Build update data with only the fields we want to update
    update_data = {}
    if "fullName" in payload:
        update_data["full_name"] = payload["fullName"]
    if "email" in payload:
        update_data["email"] = payload["email"]
    # Convert status string to boolean
    if "status" in payload:
        status_value = payload["status"]
        if isinstance(status_value, str):
            update_data["is_active"] = status_value.lower() in ["active", "true", "1"]
        else:
            update_data["is_active"] = bool(status_value)
    
    # update_data["updated_at"] = datetime.utcnow()
    
    print("Update data:", update_data)




    # payload["updated_at"] = datetime.utcnow()
    # res = await db.team_members.update_one({"id": member_id}, {"$set": payload})
    # usr_updt = User(full_name=payload["fullName"], is_active=payload["status"])
    # print("usr_updt form:", usr_updt.dict())
    res = await DB.users.update_one({"id": payload["userId"]}, {"$set": update_data})
    print("res:", res)
    print("Update result:", res.modified_count)
    return res.modified_count


async def delete_team_member(member_id: str, org_id: str) -> int:
    print("member_id", member_id)
    print("org_id",org_id)
    res = await DB.organization_memberships.delete_one({"user_id": member_id, "org_id": org_id})
    return res.deleted_count


# Notification prefs
async def get_notification_pref(user_id: str) -> Optional[Dict[str, Any]]:
    return await db.notification_preferences.find_one({"user_id": user_id})


async def upsert_notification_pref(payload: Dict[str, Any]) -> Dict[str, Any]:
    print("payload recvd-----> ", payload)
    print()
    payload["updated_at"] = datetime.utcnow()
    
    update_data = {}
    if "upload_completed" in payload:
        update_data["upload_completed"] = payload["upload_completed"]
    if "review_required" in payload:
        update_data["review_required"] = payload["review_required"]
    if "export_ready" in payload:
        update_data["export_ready"] = payload["export_ready"]
    if "exceptions_detected" in payload:
        update_data["exceptions_detected"] = payload["exceptions_detected"]

    # # Convert status string to boolean
    # if "status" in payload:
    #     status_value = payload["status"]
    #     if isinstance(status_value, str):
    #         update_data["is_active"] = status_value.lower() in ["active", "true", "1"]
    #     else:
    #         update_data["is_active"] = bool(status_value)


    await DB.notification_preferences.update_one({"user_id": payload["user_id"]}, {"$set": payload}, upsert=True)
    print("Inserted to notification preferences  Successfully")
    print("Inserted to notification preferences  Successfully")
    print("Inserted to notification preferences  Successfully")

    # return await get_notification_pref(payload["user_id"])
    return {"Message": "Notification Preferences Updated Successfully"}


# Audit logs
async def list_audit_logs(
    org_id: str,
    user_name: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    q = {"id": org_id}
    if user_name:
        q["user_name"] = user_name
    if category:
        q["category"] = category
    cursor = db.audit_logs.find(q).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=None)


async def create_audit_log(payload: Dict[str, Any]) -> Dict[str, Any]:
    log = AuditLog(**payload).dict()
    await db.audit_logs.insert_one(log)
    return log