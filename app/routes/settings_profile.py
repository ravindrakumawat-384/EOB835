from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import Dict, Any, Optional
from ..services.auth_deps import get_current_user
import app.common.db.db as db_module
from ..utils.logger import get_logger
from datetime import datetime
import os
from bson import ObjectId

from app.common.db.db import init_db
DB = init_db()

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
# async def get_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
async def get_user_profile():
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
        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv

        print("user_id-----> ", user_id)
        
        logger.info(f"Fetching user profile for user_id: {user_id}")

        # Get user details
        user_data = await db_module.db.users.find_one({"id": user_id})
        user_prof_data = await db_module.db.user_profiles.find_one({"user_id": user_id})
        if not user_data:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        full_name = user_data.get("full_name")
        parts = full_name.strip().split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        # Get organization membership and role
        membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        if not membership:
            logger.warning(f"Organization membership not found for user_id: {user_id}")
            raise HTTPException(status_code=404, detail="Organization membership not found")
        
        org_id = membership.get("org_id")
        role = membership.get("role")
        
        # Get organization details
        org = await db_module.db.organizations.find_one({"id": org_id})
        org = clean_mongo_doc(org)
        org_name = org.get("name") if org else None
        print("org_name-----> ", org_name)


        profile_data = {
            "personalDetails": {
                "firstName": first_name,
                "lastName": last_name,
                "email": user_data.get("email", ""),
                "phone": user_prof_data.get("mobile", "N/A"),
                "organization": org_name,
                "location": user_prof_data.get("location", "N/A"),
                "timezone": user_prof_data.get("timezone", "pt"),
                "dateFormat": user_prof_data.get("date_format", "MM/DD/YYYY")
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
# async def update_user_profile(payload: Dict[str, Any], user: Dict[str, Any] = Depends(get_current_user)):
async def update_user_profile(payload: Dict[str, Any]):
    """
    Update user profile information including:
    - Personal Information (first name, last name, phone)
    - Location
    - Timezone
    - Date Format
    - Profile Photo
    """
    try:
        print("payload   update_user_profile:", payload)

        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv
        
        # Get user details
        user_data = await db_module.db.users.find_one({"id": user_id})
        
        if not user_data:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = await db_module.db.users.find_one({"id": user_id})
        print("user_data------------------> ", user_data)


        # updating user details information in user model
        # usr = await DB.users.find_one({"email": payload["email"]},{"_id": 0})
        # print("usr------------------> ", usr)
        # print("usr[id]------------------> ", usr["id"])

        update_user = {}
        update_user_prof = {}
        # if "personalDetails" in payload:
        if payload:
            print("payload found")
            print("payload----->>>>> ", payload)
            print("payload[firstName]----->>>>> ", payload["firstName"])
            print("payload[organization]----->>>>> ", payload["organization"])
            # full_name = user_data.get("full_name")
            # parts = full_name.strip().split()
            # first_name = parts[0] if parts else ""
            # last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

            if "firstName" in payload and "lastName" in payload:
                full_name = f"{payload['firstName']} {payload['lastName']}"
                update_user["full_name"] = full_name

            # if "email" in payload:
            #     update_user["email"] = payload["email"]
            
            if "phoneNumber" in payload["phoneNumber"]:
                update_user_prof["phoneNumber"] = payload["phoneNumber"]
            
            if "location" in payload:
                update_user_prof["location"] = payload["location"]

            if "timezone" in payload:
                update_user_prof["timezone"] = payload["timezone"]
                # update_data["updated_at"] = datetime.utcnow()

            if "dateFormat" in payload:
                update_user_prof["dateFormat"] = payload["dateFormat"]

            print("update_user---> ", update_user)
            await DB.users.update_one({"id": user_id}, {"$set": update_user})
            await DB.user_profiles.update_one({"user_id": user_id}, {"$set": update_user_prof})


            # Update organization membership
            org_update = {}            
            if "organization" in payload["organization"]: 
                org_update["organization"] = payload["organization"]
            print("org_update---> ", org_update)

            # Get organization membership and role            
            membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})
            # org = await db_module.db.organizations.find_one({"id": membership.get("org_id")})

            await DB.organizations.update_one({"id": membership.get("org_id")}, {"$set": org_update})
        
            # Update profile photo
            # if "photoPath" in payload:
                # update_data["photo_path"] = payload["photoPath"]
        
        logger.info(f"User profile updated successfully for user_id: {user_id}")
        return {"success":"User profile updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user profile")


# GET API to retrieve the user's profile picture path
@router.get("/profile-pic", response_model=Dict[str, Any])
async def get_profile_pic():
    """
    Get the profile picture path for the user.
    """
    try:
        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4"  # TODO: Replace with Depends(get_current_user)
        user_prof_data = await db_module.db.user_profiles.find_one({"user_id": user_id})
        if not user_prof_data or not user_prof_data.get("profile_pic_path"):
            logger.warning(f"Profile picture not found for user_id: {user_id}")
            raise HTTPException(status_code=404, detail="Profile picture not found")
        return {"profile_pic_path": user_prof_data["profile_pic_path"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile picture")
    

# @router.patch("/upload-profile-pic", response_model=Dict[str, Any])
# async def update_user_profile(payload: Dict[str, Any]):
@router.post("/upload-profile-pic", response_model=Dict[str, Any]) # TODO: Replace with Depends(get_current_user)
async def upload_profile_pic(file: UploadFile = File(...)): 
    """
    Upload a profile picture for the user. Stores file and updates user profile_pic_path in MongoDB.

    Update user profile information including:
    - Personal Information (first name, last name, phone)
    - Location
    - Timezone
    - Date Format
    - Profile Photo
    """
    try:
        user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv
    
        # Get user details
        user_prof_data = await db_module.db.user_profiles.find_one({"user_id": user_id})
        
        if not user_prof_data:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_prof_data = await db_module.db.user_profiles.find_one({"user_id": user_id})
        print("user_prof_data------------------> ", user_prof_data)

        # Save uploaded file to disk (or cloud storage)
        upload_dir = "uploaded_profile_pics"
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"{user_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Update user profile_pic_path in MongoDB
        await DB.user_profiles.update_one({"user_id": user_id}, {"$set": {"profile_pic_path": file_path, "updated_at": datetime.utcnow()}})
        logger.info(f"Profile picture uploaded for user_id: {user_id}, path: {file_path}")
        return {"success": True, "profile_pic_path": file_path}
    except Exception as e:
        logger.error(f"Failed to upload profile picture: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")
    
