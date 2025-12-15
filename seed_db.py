"""
seed_db.py

Populate MongoDB with sample data for:
- organizations
- users
- organization_memberships
- user_preferences
- notifications
- email_events
- retention_policies

Run:
    python seed_db.py
"""

import asyncio 
from app.common.db.db import init_db
from app.common.db.models import (
    Organization,
    User,
    UserProfile,
    OrganizationMembership,
    UserPreferences,
    Notification,
    NotificationPreferences,
    EmailEvent,
    RetentionPolicy,


)
from datetime import datetime
import bcrypt

DB = None


def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode()


async def seed():
    global DB
    DB = init_db()

    # Clean (CAUTION: only for dev)
    await DB.organizations.delete_many({})
    await DB.users.delete_many({})
    await DB.user_profiles.delete_many({})
    await DB.organization_memberships.delete_many({})
    await DB.user_preferences.delete_many({})
    await DB.notifications.delete_many({})
    await DB.notification_preferences.delete_many({})
    await DB.email_events.delete_many({})
    await DB.retention_policies.delete_many({})

    # Organizations
    org1 = Organization(name="Acme Health", slug="acme-health")
    org2 = Organization(name="MediCo", slug="medico")
    org3 = Organization(name="Billing Info", slug="billing-info")
    org4 = Organization(name="Ditstek", slug="ditstek")

    await DB.organizations.insert_many([org1.dict(), org2.dict(), org3.dict(), org4.dict()])
    print("Inserted organizations")

    # Users
    u1 = User(email="admin@acme.example", password_hash=hash_password("password123"), full_name="Acme Admin")
    u2 = User(email="reviewer@acme.example", password_hash=hash_password("password123"), full_name="Acme Reviewer")

    u3 = User(email="eob@yopmail.com", password_hash=hash_password("Test@123"), full_name="Gourav Choudhary")
    u4 = User(email="kumawatr196@gmail.com", password_hash=hash_password("Test@123"), full_name="Ravindra Kumawat")

    u5 = User(email="manish@yopmail.com", password_hash=hash_password("Test@123"), full_name="Manish Singh")
    u6 = User(email="rahul@yopmail.com", password_hash=hash_password("Test@123"), full_name="Rahul pareek")

    akash = User(email="akash@gmail.com", password_hash=hash_password("Test@123"), full_name="Akash Soni")
    aman = User(email="aman@gmail.com", password_hash=hash_password("Test@123"), full_name="Aman kumar")


    await DB.users.insert_many([u1.dict(), u2.dict(), u3.dict(), u4.dict(), u5.dict(), u6.dict(), akash.dict(), aman.dict()])
    print("1 ------------- Inserted users")

    up1 = UserProfile(user_id=u1.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")
    up2 = UserProfile(user_id=u2.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")

    up3 = UserProfile(user_id=u3.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")
    up4 = UserProfile(user_id=u4.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")

    up5 = UserProfile(user_id=u5.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")
    up6 = UserProfile(user_id=u6.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")

    aksh_prf = UserProfile(user_id=akash.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")
    amn_prf = UserProfile(user_id=aman.id, mobile="1234567890", profile_pic_path=None, location="New York", timezone="EST",  date_format="MM/DD/YYYY")


    await DB.user_profiles.insert_many([up1.dict(), up2.dict(), up3.dict(), up4.dict(), up5.dict(), up6.dict(), aksh_prf.dict(), amn_prf.dict()])
    print("12 ------------- Inserted users in User profile ")

    # Memberships
    m1 = OrganizationMembership(org_id=org1.id, user_id=u1.id, role="admin", joined_at=datetime.utcnow())
    m2 = OrganizationMembership(org_id=org1.id, user_id=u2.id, role="reviewer", joined_at=datetime.utcnow())

    m3 = OrganizationMembership(org_id=org4.id, user_id=u3.id, role="admin", joined_at=datetime.utcnow())
    m4 = OrganizationMembership(org_id=org4.id, user_id=u4.id, role="admin", joined_at=datetime.utcnow())

    await DB.organization_memberships.insert_many([m1.dict(), m2.dict(), m3.dict(), m4.dict()])
    print("2 ---------- Inserted memberships")

    # Preferences
    pref = UserPreferences(user_id=u1.id, org_id=org1.id, prefs_json={"default_page": "dashboard"})
    await DB.user_preferences.insert_one(pref.dict())
    print("3 ----------- Inserted user preferences")

    # Notifications
    note = Notification(org_id=org1.id, user_id=u1.id, type="file_processed",
                        title="File processed", message="EOB file ABC.pdf processed with low confidence", data_json={"file_id": "abc123"})
    await DB.notifications.insert_one(note.dict())
    print("4 ----------- Inserted notifications")

    # NotificationPreferences Adding notification preferences
    n1 = NotificationPreferences(user_id=u3.id, upload_completed=False, review_required=False, export_ready=False, exceptions_detected=False)
    n2 = NotificationPreferences(user_id=u4.id, upload_completed=False, review_required=False, export_ready=False, exceptions_detected=False)

    await DB.notification_preferences.insert_many([n1.dict(), n2.dict()])
    print("44444 ----------- Inserted notification preferences")

    # Email events
    ev = EmailEvent(org_id=org1.id, to_email="support@acme.example", subject="Processing failed", status="queued")
    await DB.email_events.insert_one(ev.dict())
    print("5 ---------- Inserted email events")

    # Retention policies
    # rp1 = RetentionPolicy(org_id=org1.id, entity_type="ocr_result", retention_days=365, delete_mode="soft")
    # rp2 = RetentionPolicy(org_id=org4.id, entity_type="ocr_result", retention_days=365, delete_mode="soft")
    # await DB.retention_policies.insert_many(rp1.dict(), rp2.dict() )

    rp1 = RetentionPolicy(org_id=org1.id, entity_type="ocr_result", retention_days=12,delete_mode="soft")
    rp2 = RetentionPolicy(org_id=org4.id,entity_type="ocr_result", retention_days=36, delete_mode="soft")
    await DB.retention_policies.insert_many([rp1.dict(), rp2.dict()])
    print("6 ---------- Inserted Retention Policyies events")

    # create empty refresh_tokens collection and an index
    await DB.refresh_tokens.delete_many({})
    await DB.refresh_tokens.create_index("jti", unique=True)

    user_example = User(email="dev@acme.example", password_hash=hash_password("1212"), full_name="Dev User")
    await DB.users.insert_one(user_example.dict())
    print("Inserted example dev user (email=dev@acme.example password=changeme)")


    print("Seeding complete")


if __name__ == "__main__":
    asyncio.run(seed())
