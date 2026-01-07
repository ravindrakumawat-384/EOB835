import psycopg2
import psycopg2.extras
from app.common.db.pg_db import get_pg_conn
# app/services/auth_deps.py
from fastapi import Depends, HTTPException, status
from typing import Dict, Any
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..utils.auth_utils import decode_token  # existing
from jose import jwt, JWTError
from ..utils.logger import get_logger
logger = get_logger(__name__)

bearer = HTTPBearer()


async def get_current_user(token: HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str, Any]:
    try:
        logger.debug("Decoding token for authentication")
        payload = decode_token(token.credentials)
        logger.debug("Decoded payload for token: %s", {k: payload.get(k) for k in ("sub", "exp", "sid")})
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is expired")
    except JWTError as e:
        msg = str(e).lower()
        logger.info("Token decode failed: %s", msg)
        if "expired" in msg:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception as e:
        msg = str(e).lower()
        logger.exception("Token decoding failed (unknown error): %s", msg)
        if "expired" in msg:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is expired")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    logger.debug("User ID from token: %s", user_id)
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,))
            user = cur.fetchone()
            if not user:
                logger.info("User not found in DB for id %s", user_id)
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            # If token contains session id (sid), ensure it is still active in refresh_tokens
            sid = payload.get("sid")
            if sid:
                cur.execute("SELECT 1 FROM refresh_tokens WHERE jti = %s AND user_id = %s LIMIT 1", (sid, user_id))
                session_row = cur.fetchone()
                if not session_row:
                    logger.info("Session invalidated for user %s (sid=%s)", user_id, sid)
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session is expired")
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
        logger.info(f"Fetching general settings for user {user_id}")
        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT role FROM organization_memberships WHERE user_id = %s LIMIT 1", (user_id,))
                membership = cur.fetchone()
                role = membership.get("role") if membership else None
                print(f"User role: {role}")
                # Admins have access to all functionality
                if role == "admin":
                    return user
                if role not in allowed_roles:
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
                return user
    return checker



