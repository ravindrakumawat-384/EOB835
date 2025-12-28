import psycopg2
from app.common.db.pg_db import get_pg_conn
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from app.common.config import settings
from typing import Dict, Any, Optional
from ..services.auth_deps import get_current_user
from ..utils.logger import get_logger
from datetime import datetime
import os
from app.services.s3_service import S3Service

logger = get_logger(__name__)

router = APIRouter(prefix="/settings/profile", tags=["settings-profile"])


# S3 configuration (replace with your actual credentials and bucket)
S3_BUCKET = settings.S3_BUCKET
AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY 
AWS_REGION = settings.AWS_REGION
s3_client = S3Service(S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)

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
    # - Timezone
    # - Date Format
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
                # "timezone": user_prof_data.get("timezone", "pt") if user_prof_data else "pt",
                # "dateFormat": user_prof_data.get("date_format", "MM/DD/YYYY") if user_prof_data else "MM/DD/YYYY"
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
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
        print("Updating user profile...")
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
                # if "timezone" in payload:
                    # cur.execute("UPDATE user_profiles SET timezone = %s WHERE user_id = %s", (payload["timezone"], user_id))
                # if "dateFormat" in payload:
                    # cur.execute("UPDATE user_profiles SET date_format = %s WHERE user_id = %s", (payload["dateFormat"], user_id))

                if "organization" in payload:
                    cur.execute("SELECT org_id FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                    membership = cur.fetchone()
                    if membership:
                        cur.execute("UPDATE organizations SET name = %s WHERE id = %s", (payload["organization"], membership[0]))
                conn.commit()
        logger.info(f"successfullysuccessfullysuccessfullysuccessfully: {user_id}")
        return {"success": "successfullysuccessfullysuccessfullysuccessfullysuccessfully"}
        
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
    Return a presigned S3 URL for the user's profile picture, or a default placeholder if not set.
    """
    try:
        user_id = user.get("id")
        logger.info(f"Fetching profile picture for user_id: {user_id}")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT profile_pic_path FROM user_profiles WHERE user_id = %s LIMIT 1", (user_id,))
                user_prof_data = cur.fetchone()
        profile_pic_path = user_prof_data.get("profile_pic_path") if user_prof_data else None
        if not profile_pic_path:
            # Optionally, return a default image URL or None
            logger.warning(f"Profile picture not found for user_id: {user_id}")
            return {"profile_pic_url": None, "message": "Profile picture not found"}
        try:
            presigned_url = s3_client.generate_presigned_image_url(profile_pic_path)
            if not presigned_url:
                logger.error(f"Failed to generate presigned URL for user_id: {user_id}")
                raise HTTPException(status_code=500, detail="Failed to generate profile picture URL")
            return {"profile_pic_url": presigned_url}
        except Exception as s3_error:
            logger.error(f"Error generating presigned URL: {str(s3_error)}")
            raise HTTPException(status_code=500, detail="Failed to generate profile picture URL")
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
        content = await file.read()
        if len(content) > 2 * 1024 * 1024:
            logger.warning(f"File too large: {len(content)} bytes")
            raise HTTPException(status_code=400, detail="File too large. Max size is 2MB.")
        

        
        # Save uploaded file to S3
        # filename = f"{user_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
        # s3_client.upload_fileobj(file.file, S3_BUCKET, filename)
        # file_path = f"s3://{S3_BUCKET}/{filename}"
        responses = []
        # 5. Save file and metadata (to S3)
        s3_path = s3_client.upload_file(content, file.filename)
        if not s3_path:
            responses.append({"filename": file.filename, "status": "error", "message": "Failed to upload to S3"})
            # continue


        # Update user profile_pic_path in PostgreSQL
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_profiles SET profile_pic_path = %s, updated_at = %s WHERE user_id = %s",
                    (s3_path, datetime.utcnow(), user_id)
                )
                conn.commit()
        logger.info(f"Profile picture uploaded for user_id: {user_id}, path: {s3_path}")
        return {"success": True, "profile_pic_path": s3_path}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")
    




