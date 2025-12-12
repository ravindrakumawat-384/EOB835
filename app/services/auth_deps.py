# app/services/auth_deps.py
from fastapi import Depends, HTTPException, status
from typing import Dict, Any
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..utils.auth_utils import decode_token  # existing
from ..common.db.db import db

bearer = HTTPBearer()


async def get_current_user(token: HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str, Any]:
    try:
        payload = decode_token(token.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user



def is_admin(user: Dict[str, Any]) -> bool:
    """
    Returns True if the user is an Admin.
    """
    return user.get("role") == "Admin"

def require_role(allowed_roles: list[str]):
    async def checker(user: Dict[str, Any] = Depends(get_current_user)):
        role = user.get("role", "viewer")
        # Admins have access to all functionality
        if role == "Admin":
            return user
        if role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker



