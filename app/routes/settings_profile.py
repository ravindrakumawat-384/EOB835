import psycopg2
from app.common.db.pg_db import get_pg_conn
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
from datetime import datetime
import os

logger = get_logger(__name__)

router = APIRouter(prefix="/settings/profile", tags=["settings-profile"])


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


class UserProfileResponse(Dict[str, Any]):
    """User profile response model"""
    pass


class UpdateProfileRequest(Dict[str, Any]):
    """Update profile request model"""
    pass


@router.get("/", response_model=Dict[str, Any])
async def get_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
# async def get_user_profile():
    """
    Get user profile information including:
    - Profile Photo
    - Personal Information (first name, last name, email, phone)
    - Organization
    - Location
    - Timezone
    - Date Format
    """
    try:
        # user_id = "7dd718f4-b3fb-4167-bb6c-0f8facc3f775" # grv
        # user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv
        user_id = user.get("id")
        print("User ID:", user_id)
        logger.info(f"Fetching user profile for user_id: {user_id}")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,))
                user_data = cur.fetchone()
                cur.execute("SELECT * FROM user_profiles WHERE user_id = %s LIMIT 1", (user_id,))
                user_prof_data = cur.fetchone()
                if not user_data:
                    logger.warning(f"User not found: {user_id}")
                    raise HTTPException(status_code=404, detail="User not found")
                full_name = user_data.get("full_name", "")
                parts = full_name.strip().split()
                first_name = parts[0] if parts else ""
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                cur.execute("SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                membership = cur.fetchone()
                if not membership:
                    logger.warning(f"Organization membership not found for user_id: {user_id}")
                    raise HTTPException(status_code=404, detail="Organization membership not found")
                org_id = membership.get("org_id")
                role = membership.get("role")
                cur.execute("SELECT name FROM organizations WHERE id = %s LIMIT 1", (org_id,))
                org = cur.fetchone()
                org_name = org.get("name") if org else None
        profile_data = {
            "personalDetails": {
                "firstName": first_name,
                "lastName": last_name,
                "email": user_data.get("email", ""),
                "phone": user_prof_data.get("mobile", "N/A") if user_prof_data else "N/A",
                "organization": org_name,
                "location": user_prof_data.get("location", "N/A") if user_prof_data else "N/A",
                "timezone": user_prof_data.get("timezone", "pt") if user_prof_data else "pt",
                "dateFormat": user_prof_data.get("date_format", "MM/DD/YYYY") if user_prof_data else "MM/DD/YYYY"
            },
            "profileDetails": {
                "email": user_data.get("email", ""),
                "role": role,
                "status": "Active" if user_data.get("is_active", True) else "Inactive",
            }
        }
        logger.info(f"User profile fetched successfully for user_id: {user_id}")
        return profile_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")


@router.patch("/", response_model=Dict[str, Any])
async def update_user_profile(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
# async def update_user_profile(payload: Dict[str, Any]):
    """
    Update user profile information including:
    - Personal Information (first name, last name, phone)
    - Location
    - Timezone
    - Date Format
    - Profile Photo
    """
    print("payload-------------- :", payload)
    try:
        print("payload   update_user_profile:", payload)

        # user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv
        user_id = user.get("id")
        print("User ID:", user_id)
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                # Update user details
                if "firstName" in payload and "lastName" in payload:
                    full_name = f"{payload['firstName']} {payload['lastName']}"
                    cur.execute("UPDATE users SET full_name = %s WHERE id = %s", (full_name, user_id))
                if "phone" in payload:
                    cur.execute("UPDATE user_profiles SET mobile = %s WHERE user_id = %s", (payload["phone"], user_id))
                if "location" in payload:
                    cur.execute("UPDATE user_profiles SET location = %s WHERE user_id = %s", (payload["location"], user_id))
                if "timezone" in payload:
                    cur.execute("UPDATE user_profiles SET timezone = %s WHERE user_id = %s", (payload["timezone"], user_id))
                if "dateFormat" in payload:
                    cur.execute("UPDATE user_profiles SET date_format = %s WHERE user_id = %s", (payload["dateFormat"], user_id))
                # Update organization name if provided
                if "organization" in payload:
                    cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                    membership = cur.fetchone()
                    if membership:
                        cur.execute("UPDATE organizations SET name = %s WHERE id = %s", (payload["organization"], membership[0]))
                conn.commit()
        logger.info(f"User profile updated successfully for user_id: {user_id}")
        return {"success": "User profile updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user profile")



# GET API to return the actual uploaded profile image file
# @router.post("/upload-profile-pic", response_model=Dict[str, Any])
@router.get("/profile-pic")
async def get_profile_pic(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get the actual uploaded profile picture file for the user.
    """
    try:
        # user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4"  # TODO: Replace with Depends(get_current_user)
        user_id = user.get("id")
        print("User ID:", user_id)
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT profile_pic_path FROM user_profiles WHERE user_id = %s LIMIT 1", (user_id,))
                user_prof_data = cur.fetchone()
                if not user_prof_data or not user_prof_data.get("profile_pic_path"):
                    logger.warning(f"Profile picture not found for user_id: {user_id}")
                    raise HTTPException(status_code=404, detail="Profile picture not found")
                file_path = user_prof_data["profile_pic_path"]
        if not os.path.exists(file_path):
            logger.warning(f"Profile picture file not found on disk: {file_path}")
            raise HTTPException(status_code=404, detail="Profile picture file not found")
        # Guess content type from file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif ext == ".png":
            media_type = "image/png"
        elif ext == ".gif":
            media_type = "image/gif"
        else:
            media_type = "application/octet-stream"
        return FileResponse(file_path, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile picture")
    

# @router.patch("/upload-profile-pic", response_model=Dict[str, Any])
# async def update_user_profile(payload: Dict[str, Any]):

@router.post("/upload-profile-pic", response_model=Dict[str, Any])
async def upload_profile_pic(file: UploadFile = File(...), user: Dict[str, Any] = Depends(get_current_user)   ):
    """
    Upload a profile picture for the user. Accepts Angular File object, validates type/size, saves file, updates MongoDB.
    Allowed types: JPG, PNG, GIF. Max size: 2MB.
    """
    try:
        # user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4"  # TODO: Replace with Depends(get_current_user)
        user_id = user.get("id")
        print("User ID:", user_id)
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM user_profiles WHERE user_id = %s LIMIT 1", (user_id,))
                user_prof_data = cur.fetchone()
                if not user_prof_data:
                    logger.warning(f"User not found: {user_id}")
                    raise HTTPException(status_code=404, detail="User not found")
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/gif"]
        if file.content_type not in allowed_types:
            logger.warning(f"Invalid file type: {file.content_type}")
            raise HTTPException(status_code=400, detail="Invalid file type. Only JPG, PNG, GIF allowed.")
        # Validate file size (max 2MB)
        contents = await file.read()
        if len(contents) > 2 * 1024 * 1024:
            logger.warning(f"File too large: {len(contents)} bytes")
            raise HTTPException(status_code=400, detail="File too large. Max size is 2MB.")
        # Save uploaded file to disk
        upload_dir = "uploaded_profile_pics"
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{user_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(contents)
        # Update user profile_pic_path in PostgreSQL
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_profiles SET profile_pic_path = %s, updated_at = %s WHERE user_id = %s",
                    (file_path, datetime.utcnow(), user_id)
                )
                conn.commit()
        logger.info(f"Profile picture uploaded for user_id: {user_id}, path: {file_path}")
        return {"success": True, "profile_pic_path": file_path}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")
    




