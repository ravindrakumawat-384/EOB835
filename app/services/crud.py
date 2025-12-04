from typing import Any
from ..common.db.db import db
from ..common.db.models import Organization, User, OrganizationMembership, UserPreferences, Notification, EmailEvent, RetentionPolicy
from ..common.db.models import TeamMember, AuditLog
# --------------------------------------
from typing import Optional, List, Dict, Any
from datetime import datetime

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



# Organization settings
async def get_org_settings(org_id: str) -> Optional[Dict[str, Any]]:
    return await db.organization_settings.find_one({"organization_id": org_id})


async def upsert_org_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    data["updated_at"] = now
    await db.organization_settings.update_one(
        {"organization_id": data["organization_id"]}, {"$set": data}, upsert=True
    )
    return await get_org_settings(data["organization_id"])


# Team members
async def list_team_members(org_id: str) -> List[Dict[str, Any]]:
    cursor = db.team_members.find({"organization_id": org_id})
    return await cursor.to_list(length=None)


async def create_team_member(payload: Dict[str, Any]) -> Dict[str, Any]:
    member = TeamMember(**payload).dict()
    await db.team_members.insert_one(member)
    return member


async def update_team_member(member_id: str, payload: Dict[str, Any]) -> int:
    payload["updated_at"] = datetime.utcnow()
    res = await db.team_members.update_one({"id": member_id}, {"$set": payload})
    return res.modified_count


async def delete_team_member(member_id: str) -> int:
    res = await db.team_members.delete_one({"id": member_id})
    return res.deleted_count


# Notification prefs
async def get_notification_pref(user_id: str) -> Optional[Dict[str, Any]]:
    return await db.notification_preferences.find_one({"user_id": user_id})


async def upsert_notification_pref(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload["updated_at"] = datetime.utcnow()
    await db.notification_preferences.update_one(
        {"user_id": payload["user_id"]}, {"$set": payload}, upsert=True
    )
    return await get_notification_pref(payload["user_id"])


# Audit logs
async def list_audit_logs(
    org_id: str,
    user_name: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    q = {"organization_id": org_id}
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