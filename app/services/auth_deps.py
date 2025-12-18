# app/services/auth_deps.py
from fastapi import Depends, HTTPException, status
from typing import Dict, Any
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..utils.auth_utils import decode_token  # existing
from ..common.db.db import db
import app.common.db.db as db_module
from jose import jwt, JWTError
from ..utils.logger import get_logger
logger = get_logger(__name__)

bearer = HTTPBearer()


async def get_current_user(token: HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str, Any]:
    try:
        print("Decoding token-------->>> ")
        print("Decoding token:", token.credentials)
        payload = decode_token(token.credentials)
        print("Decoded payload:", payload)
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError as e:
        print("Token decoding failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        print("Token decoding failed (unknown error)")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    print("User ID from token:", user_id)
    user = await db_module.db.users.find_one({"id": user_id})
    print("Fetched user from DB:", user)
    if not user:
        print("User not found in DB")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def is_admin(user: Dict[str, Any]) -> bool:
    """
    Returns True if the user is an Admin.
    """
    return user.get("role") == "Admin"

def require_role(allowed_roles: list[str]):
    async def checker(user: Dict[str, Any] = Depends(get_current_user)):
        # role = user.get("role", "viewer")
        user_id = user.get("id")
        logger.info("Fetching general settings for user", user_id=user_id)
        membership = await db_module.db.organization_memberships.find_one({"user_id": user_id})
        role = membership.get("role")
        print(f"User role: {role}")
        # Admins have access to all functionality
        if role == "admin":
            return user
        if role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker



