from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
from ..services.auth_deps import get_current_user
import app.common.db.db as db_module
from ..utils.logger import get_logger
from datetime import datetime
from bson import ObjectId

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
        user_id = "12bec674-ae9f-4878-ae56-8ad25b0d76e3"
        logger.info(f"Fetching user profile for user_id: {user_id}")

        # Get user details
        user_data = await db_module.db.users.find_one({"id": user_id})
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
        
        # Extract profile information
        profile_data = {
            "profilePhoto": {
                "email": user_data.get("email", ""),
                "role": role,
                "status": "Active" if user_data.get("is_active", True) else "Inactive",
                # "photoPath": user_data.get("photo_path"),
            },
            "personalInformation": {
                "firstName": first_name,
                "lastName": last_name,
                "email": user_data.get("email", ""),
                "phoneNumber": user_data.get("phone_number", "N/A"),
            },
            "organization": org_name,
            "location": user_data.get("location", "N/A"),
            "timezone": user_data.get("timezone", "pt"),
            "dateFormat": user_data.get("date_format", "MM/DD/YYYY"),
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
        user_id = "efd59952-d01f-4872-94cb-4232349655b8"
        
        # Get user details
        user_data = await db_module.db.users.find_one({"id": user_id})
        
        if not user_data:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prepare update data
        update_data = {}
        
        # Update personal information
        if "personalInformation" in payload:
            personal_info = payload.get("personalInformation", {})
            if "firstName" in personal_info:
                update_data["first_name"] = personal_info["firstName"]
            if "lastName" in personal_info:
                update_data["last_name"] = personal_info["lastName"]
            if "phoneNumber" in personal_info:
                update_data["phone_number"] = personal_info["phoneNumber"]
        
        # Update location, timezone, date format
        if "location" in payload:
            update_data["location"] = payload["location"]
        if "timezone" in payload:
            update_data["timezone"] = payload["timezone"]
        if "dateFormat" in payload:
            update_data["date_format"] = payload["dateFormat"]
        
        # Update profile photo
        if "photoPath" in payload:
            update_data["photo_path"] = payload["photoPath"]
        
        # Add timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update user in database
        if update_data:
            await db_module.db.users.update_one({"id": user_id}, {"$set": update_data})
            logger.info(f"User profile updated for user_id: {user_id}")
        
        # Get updated user data
        updated_user = await db_module.db.users.find_one({"id": user_id})
        
        # Get organization membership and role
        membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        org_id = membership.get("org_id")
        role = membership.get("role")
        
        # Get organization details
        org = await db_module.db.organizations.find_one({"id": org_id})
        org = clean_mongo_doc(org)
        org_name = org.get("name") if org else None
        
        # Return updated profile data
        profile_data = {
            "profilePhoto": {
                "firstName": updated_user.get("first_name", ""),
                "lastName": updated_user.get("last_name", ""),
                "email": updated_user.get("email", ""),
                "role": role,
                "status": "Active" if updated_user.get("is_active", True) else "Inactive",
                "photoPath": updated_user.get("photo_path"),
            },
            "personalInformation": {
                "firstName": updated_user.get("first_name", ""),
                "lastName": updated_user.get("last_name", ""),
                "email": updated_user.get("email", ""),
                "phoneNumber": updated_user.get("phone_number", ""),
            },
            "organization": org_name,
            "location": updated_user.get("location", ""),
            "timezone": updated_user.get("timezone", "UTC"),
            "dateFormat": updated_user.get("date_format", "MM/DD/YYYY"),
        }
        logger.info(f"User profile updated successfully for user_id: {user_id}")
        return profile_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user profile")
