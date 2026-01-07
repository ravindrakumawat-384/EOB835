from typing import Any
from fastapi import APIRouter, HTTPException, status, Depends, Body
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
import app.common.db.db as db_module
from ..utils.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
)
from ..services.email_service import send_email_stub, send_reset_email
from ..common.config import settings
from ..common.db.models import OrganizationMembership
from ..services.auth_deps import get_current_user
from fastapi import Request
import bson
import psycopg2
from jose import jwt, JWTError
from typing import Dict, Any
from app.common.db.db import init_db
from app.common.db.pg_db import get_pg_conn
DB = init_db()


from ..utils.logger import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class UserDetails(BaseModel):
    id: str | None = None
    email: str | None = None
    full_name: str | None = None
    org_id: str | None = None
    role: str | None = None

# class OrganizationDetails(BaseModel):
#     org_id: str | None = None
#     role: str | None = None

class TokenResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    # user: UserDetails | None = None
    # organization: OrganizationDetails | None = None

class LoginResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]

    # user: UserDetails | None = None
    # organization: OrganizationDetails | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RequestResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


async def _get_user_by_email(email: str) -> dict | None:
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))
            user_row = cur.fetchone()
            return user_row


async def _get_user_by_id(user_id: str) -> dict | None:
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,))
            return cur.fetchone()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> Any:
    existing = await _get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_id = payload.email + "-" + str(int(datetime.utcnow().timestamp()))
    now = datetime.utcnow()
    # Truncate password to 72 bytes for bcrypt compatibility
    password = payload.password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, email, password_hash, full_name, is_active, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (user_id, payload.email, hash_password(password), payload.full_name, True, now, now)
            )
            # Create refresh token as session identifier and store it (single session per user)
            refresh = create_refresh_token(user_id)
            decoded_refresh = decode_token(refresh)
            sid = decoded_refresh.get("jti")
            cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
            cur.execute(
                "INSERT INTO refresh_tokens (jti, user_id, created_at, expires_at) VALUES (%s,%s,%s,%s)",
                (sid, user_id, now, datetime.fromtimestamp(decoded_refresh.get("exp")))
            )
            conn.commit()
    access = create_access_token(user_id, extra={"sid": sid})
    return {"message": "user created", "access_token": access, "refresh_token": refresh}


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> Any:
    user = await _get_user_by_email(payload.email)
    print("user-----> ", user)
    # Truncate password to 72 bytes for bcrypt compatibility
    password = payload.password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    if not user or not verify_password(password, user["password_hash"]):
        print("111")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials. Please check email and password.")

    # Invitation link expiration logic
    if not user.get("is_active", True) and not user.get("last_login_at"):
        logger.debug("User appears to be invited and not yet activated: %s", user.get("id"))
        # User is invited but not yet activated — verify invite token is present and not expired
        with get_pg_conn() as conn:
            logger.debug("User appears to be invited and not yet activated: %s", user.get("id"))
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT expires_at FROM refresh_tokens WHERE user_id = %s ORDER BY expires_at DESC LIMIT 1",
                    (user["id"],)
                )
                invite_token_row = cur.fetchone()
        if not invite_token_row:
            logger.info("Invite token not found for user %s — blocking login", user["id"])
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation link expired or invalid. Please contact your admin for a new invite.")
        expires_at = invite_token_row["expires_at"]
        logger.debug("Invite token expires_at: %s", expires_at)
        # Compare with timezone-aware UTC to avoid naive vs aware datetime TypeError
        if expires_at < datetime.now(timezone.utc):
            logger.info("Invitation link expired at %s — blocking login", expires_at)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitation link has expired. Please contact your admin for a new invite.")
        # invite token exists and is still valid — allow login to proceed (user will be activated below)
        logger.info("Invite token valid for user %s — allowing first-time login", user["id"])


    # Create a refresh token and use its jti as the session id (sid)
    refresh = create_refresh_token(user["id"])
    dec = decode_token(refresh)
    sid = dec.get("jti")
    now = datetime.utcnow()
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            # Update last_login_at and enforce single session: remove existing refresh tokens for this user
            cur.execute(
                "UPDATE users SET is_active = TRUE, last_login_at = %s WHERE id = %s",
                (now, user["id"])
            )
            cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user["id"],))
            cur.execute(
                "INSERT INTO refresh_tokens (jti, user_id, created_at, expires_at) VALUES (%s,%s,%s,%s)",
                (sid, user["id"], now, datetime.fromtimestamp(dec.get("exp")))
            )
            # Get org details
            cur.execute("SELECT org_id, role FROM organization_memberships WHERE user_id = %s LIMIT 1", (user["id"],))
            org_details = cur.fetchone()
            conn.commit()
    # Create access token that includes sid so we can validate active session on requests
    access = create_access_token(user["id"], extra={"sid": sid})

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 30
    if org_details:
        org_id = org_details[0]
        role = org_details[1]
    else:
        org_id = "N/A"
        role = "N/A"
    user_details = {
        "id": user.get("id"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "org_id": org_id,
        "role": role,
    }
    return {
        "message": "Login Successful",
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": expires_in,
        "user": user_details,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> Any:
    try:
        print("Enter in Referesh payload----------->", payload)
        decoded = decode_token(payload.refresh_token)
        print("decoded", decoded)
        
    # except Exception:z
    #     raise HTTPException(status_code=401, detail="Invalid refresh token")

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    jti = decoded.get("jti")
    print("jti", jti)

    jti = decoded["jti"]
    print("jti-----> ", jti)
    user_id = decoded["sub"]
    print("user_id-----> ", user_id)

    # check refresh token blacklisted
    # blacklisted = await db_module.db.refresh_token_blacklist.find_one({"jti": jti})
    # if blacklisted:
    #     raise HTTPException(status_code=401, detail="Refresh token revoked")


    # check refresh token exists (rotation / blacklist)
    with get_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM refresh_tokens WHERE jti = %s LIMIT 1", (jti,))
            stored = cur.fetchone()
            if not stored:
                raise HTTPException(status_code=401, detail="Refresh token revoked or not found")
            # rotate: delete old refresh, issue a new one
            cur.execute("DELETE FROM refresh_tokens WHERE jti = %s", (jti,))
            new_refresh = create_refresh_token(user_id)
            new_dec = decode_token(new_refresh)
            # insert rotated refresh token
            cur.execute(
                "INSERT INTO refresh_tokens (jti, user_id, created_at, expires_at) VALUES (%s,%s,%s,%s)",
                (new_dec.get("jti"), user_id, datetime.utcnow(), datetime.fromtimestamp(new_dec.get("exp")))
            )
            conn.commit()
    # Create access token associated with this refresh jti (session id)
    access = create_access_token(user_id, extra={"sid": new_dec.get("jti")})
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "expires_in": expires_in,
        "token_type": "bearer",
        "msg": "Token refreshed successfully"
    }


@router.post("/request-password-reset")
async def request_password_reset(payload: RequestResetRequest) -> Any:
    user = await _get_user_by_email(payload.email)
    # Always return success to avoid user enumeration

    if not user:
        # For non-existent users, just log (do not send real email)
        await send_email_stub(
            to_email=payload.email,
            subject="Password reset request",
            template_name="password_reset_requested",
            payload={"note": "user not found"},
        )
        return {"message": "If an account exists, a reset email was sent."}

    print("payload.email----> ", payload.email)
    print("user[id]", user["id"])
    token = create_reset_token(user["id"], payload.email)

    # logger.info(f"Reset Token generated: {token.get("jti")}")
    print()
    print("token token token token ---> ", token)
    print()


    # Send real email with token
    # sent = send_reset_email(user["email"], token)
    # if not sent:
    #     # Optionally, log or handle email send failure
    #     await send_email_stub(
    #         to_email=user["email"],
    #         subject="Password reset link (FAILED TO SEND)",
    #         template_name="password_reset",
    #         payload={"note": "SMTP send failed", "user_id": user["id"]},
    #     )
    # # return {"message": "If an account exists, a reset email was sent."}
    return {"message": "Password reset link has been sent to your email."}
    

@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest) -> Any:
    # verify token
    print("enter in Reset Password")
    print("enter in Reset Password")
    print("enter in Reset Password")
    print("payload ---> ", payload)
    print("payload.token ---> ", payload.token)
    # try:
    #     from datetime import datetime
    #     now_utc = datetime.utcnow()
    #     # logger.info(f"[reset-password] current UTC: {now_utc} ({int(now_utc.timestamp())})")
    #     logger.info(f"Reset Token provided: {payload}")
    #     token_clean = payload.token.strip()
    #     print("token_clean---> ", token_clean)
    #     # logger.info(f"JWT Secret: {settings.JWT_SECRET}")
    #     # logger.info(f"JWT Algorithm: {settings.JWT_ALGORITHM}")
    #     # logger.info(f"Decoding token: {token_clean}")
    #     decoded = decode_token(token_clean)
    #     logger.info(f"Decoded reset token: {decoded}")
    #     print("decoded--> ",decoded)
    #     iat = decoded.get("iat")
    #     print("iat--> ",iat)
    #     exp = decoded.get("exp")
    #     print("exp--> ",exp)

    #     if iat:
    #         logger.info(f"[reset-password] iat: {iat} ({datetime.utcfromtimestamp(iat)})")
    #     if exp:
    #         logger.info(f"[reset-password] exp: {exp} ({datetime.utcfromtimestamp(exp)})")

    # except Exception as exc:
    #     import traceback
    #     logger.error(f"JWT decode error: {type(exc).__name__} {str(exc)}")
    #     logger.error(traceback.format_exc())
    #     raise HTTPException(status_code=400, detail=f"Invalid or expired token: {type(exc).__name__}: {str(exc)}")

    # if decoded.get("type") != "reset":
    #     raise HTTPException(status_code=400, detail="Invalid token type")

    # user_id = decoded.get("sub")
    # print("user_id", user_id)
    # user = await _get_user_by_id(user_id)
    # print("user--> ", user)
    # if not user:
    #     raise HTTPException(status_code=400, detail="User not found")

    # # update password
    # print("payload.new_password", payload.new_password)
    # new_hash = hash_password(payload.new_password)
    # print("new_hash", new_hash)
    # await db_module.db.users.update_one({"id": user_id}, {"$set": {"password_hash": new_hash, "updated_at": datetime.utcnow()}})

    # # Optionally, revoke all refresh tokens for this user (security)
    # await db_module.db.refresh_tokens.delete_many({"user_id": user_id})

    # # log email event that password was changed (dev notification)
    # await send_email_stub(
    #     to_email=user["email"],
    #     subject="Your password was changed",
    #     template_name="password_changed",
    #     payload={"user_id": user_id},
    # )

    # return {"message": "Password changed successfully"}

    token = payload.token
    print("token",token)

    new_password = payload.new_password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    print("new_password", new_password)

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="token and new_password required")
    try:

        data = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        print("data", data)

    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    
    print("data.get(type)", data.get("type"))
    if data.get("type") != "reset":
        raise HTTPException(status_code=400, detail="Not a reset token")
    
    user_id = data["sub"]
    print("user_id", user_id)
    # db = get_db()
    # user = await db.users.find_one({"id": user_id})
    with get_pg_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,))
            user = cur.fetchone()
            if not user:
                raise HTTPException(status_code=400, detail="Invalid token")
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                (hash_password(new_password), datetime.utcnow(), user_id)
            )
            conn.commit()
    return {"detail": "Password reset successful"}



# Logout endpoint
@router.post("/logout")
async def logout(payload: LogoutRequest, request: Request):
    """
    Invalidate the provided refresh token (logout user).
    """
    try:
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            logger.warning("Logout attempted with non-refresh token.")
            raise HTTPException(status_code=400, detail="Invalid token type for logout.")
        jti = decoded.get("jti")
        # Remove the refresh token from DB (blacklist/rotation)
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM refresh_tokens WHERE jti = %s", (jti,))
                conn.commit()
        return {"message": "Logged out successfully."}
    except Exception as exc:
        logger.error(f"Logout error: {type(exc).__name__}: {str(exc)}")
        raise HTTPException(status_code=400, detail=f"Logout failed: {type(exc).__name__}: {str(exc)}")
    

# change-password endpoint
@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, user: dict = Depends(get_current_user)):
# async def change_password(payload: ChangePasswordRequest):
    """
    Allow authenticated user to change their password.
    Verifies old password, updates to new password, and revokes all refresh tokens for security.
    """ 
    try:
        user_id = user.get("id")
        print("User ID:", user_id)

        with get_pg_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s LIMIT 1", (user_id,))
                user_row = cur.fetchone()
                if not user_row:
                    logger.error(f"User not found: {user_id}")
                    raise HTTPException(status_code=404, detail="User not found")
                # Verify old password
                old_password = payload.old_password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
                if not verify_password(old_password, user_row["password_hash"]):
                    logger.warning(f"Change password failed: invalid old password for user {user_row['id']}")
                    raise HTTPException(status_code=400, detail="Invalid old password")
                # Update password
                new_password = payload.new_password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
                new_hash = hash_password(new_password)
                cur.execute(
                    "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                    (new_hash, datetime.utcnow(), user_row["id"])
                )
                # Revoke all refresh tokens for this user
                cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_row["id"],))
                conn.commit()
        await send_email_stub(
            to_email=user_row["email"],
            subject="Your password was changed",
            template_name="password_changed",
            payload={"user_id": user_row["id"]},
        )
        logger.info(f"Password changed successfully for user {user_row['id']}")
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to change password")