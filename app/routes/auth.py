
from typing import Any
from fastapi import APIRouter, HTTPException, status, Depends, Body
from pydantic import BaseModel, EmailStr
from datetime import datetime
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
from jose import jwt, JWTError

from app.common.db.db import init_db
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
    return await db_module.db.users.find_one({"email": email})


async def _get_user_by_id(user_id: str) -> dict | None:
    return await db_module.db.users.find_one({"id": user_id})


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> Any:
    existing = await _get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_doc = {
        "email": payload.email,
        "password_hash": hash_password(payload.password),
        "full_name": payload.full_name,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        # generate id consistent with earlier model (we used uuid4 str in models.py)
        "id": payload.email + "-" + str(int(datetime.utcnow().timestamp())),  # small dev id
    }
    await db_module.db.users.insert_one(user_doc)
    # For convenience, create a refresh token entry
    access = create_access_token(user_doc["id"])
    refresh = create_refresh_token(user_doc["id"])
    # persist the refresh token (by jti) for rotation / blacklisting
    decoded_refresh = decode_token(refresh)
    refresh_doc = {
        "jti": decoded_refresh.get("jti"),
        "user_id": user_doc["id"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.fromtimestamp(decoded_refresh.get("exp")),
    }
    await db_module.db.refresh_tokens.insert_one(refresh_doc)
    return {"message": "user created", "access_token": access, "refresh_token": refresh}


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> Any:
    user = await _get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials. Please check username and password")

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User inactive")

    access = create_access_token(user["id"])
    refresh = create_refresh_token(user["id"])

    
    print()
    print("access", access)
    print()
    print("refresh", refresh)
    print()

    # store refresh token (rotation)
    dec = decode_token(refresh)
    refresh_doc = {
        "jti": dec.get("jti"),
        "user_id": user["id"],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.fromtimestamp(dec.get("exp")),
    }
    await db_module.db.refresh_tokens.insert_one(refresh_doc)

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    # org_details = OrganizationMembership.find_one({"email": user["email"]})

    user_id = user.get("id")
    print("User ID:", user_id)

    # org_details = db_module.db.organization_memberships.find_one({"user_id": user_id})
    org_details = await db_module.db.organization_memberships.find_one({"user_id": user_id})

    if org_details:
        org_id = org_details.get("org_id")
        role = org_details.get("role")

    else:
        print(" N/A")
        org_id = "N/A"
        role = "N/A"

    print("org_id------>>>> ", org_id)
    print("role------>>>> ", role)

    # Add user details to response
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
    stored = await db_module.db.refresh_tokens.find_one({"jti": jti})
    print("stored", stored)
    if not stored:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")

    # # Blacklist old token
    # await db_module.db.refresh_token_blacklist.insert_one({
    #     "jti": jti,
    #     "revoked_at": datetime.utcnow(),
    # })
    
    user_id = decoded.get("sub")
    print(":user_id", user_id)

    # rotate: delete old refresh, issue a new one
    await db_module.db.refresh_tokens.delete_one({"jti": jti})

    # Create new refresh token
    new_refresh = create_refresh_token(user_id)
    print("new_refresh", new_refresh)
    new_dec = decode_token(new_refresh)
    print("new_dec", new_dec)
    await db_module.db.refresh_tokens.insert_one(
        {
            "jti": new_dec.get("jti"),
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.fromtimestamp(new_dec.get("exp")),
        }
    )

    # Create new access token
    access = create_access_token(user_id)
    print("access", access)
    
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    print("expires_in",expires_in)

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

    # print("token GeneRateddddd ---> ", token)
    
    # logger.info(f"Reset Token generated: {token}")
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

    new_password = payload.new_password
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
    user = await db_module.db.users.find_one({"id": user_id})
    print("user", user)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    
    await DB.users.update_one({"id": user_id}, {"$set": {"password_hash": hash_password(new_password), "updated_at": datetime.utcnow()}})
    print("Done Done Done Done Done Done Done")
    print("Done Done Done Done Done Done Done")
    print("Done Done Done Done Done Done Done")
    print("Done Done Done Done Done Done Done")
    print("Done Done Done Done Done Done Done")
    # await send_reset_confirmation_email(user["email"], user.get("full_name", ""))
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
        result = await db_module.db.refresh_tokens.delete_one({"jti": jti})
        if result.deleted_count == 0:
            logger.info(f"Logout: refresh token not found or already invalidated (jti={jti})")
        else:
            logger.info(f"Logout: refresh token invalidated (jti={jti})")
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
        # user_id = "7dd718f4-b3fb-4167-bb6c-0f8facc3f775" # grv
        # user_id = "b6ee4982-b5ec-425f-894d-4324adce0f36" # rv
        # user_id = "b73536ad-eba2-4d48-9306-5e479fbf8058" # rv
        # user_id = "6f64216e-7fbd-4abc-b676-991a121a95e4" # rv
        user_id = user.get("id")
        print("User ID:", user_id)

        try:
            user = await _get_user_by_id(user_id)
        except:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify old password
        if not verify_password(payload.old_password, user["password_hash"]):
            logger.warning(f"Change password failed: invalid old password for user {user['id']}")
            raise HTTPException(status_code=400, detail="Invalid old password")

        # Update password
        new_hash = hash_password(payload.new_password)
        await db_module.db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": new_hash, "updated_at": datetime.utcnow()}})

        # Revoke all refresh tokens for this user
        await db_module.db.refresh_tokens.delete_many({"user_id": user["id"]})

        # Log email event (dev notification)
        await send_email_stub(
            to_email=user["email"],
            subject="Your password was changed",
            template_name="password_changed",
            payload={"user_id": user["id"]},
        )

        logger.info(f"Password changed successfully for user {user['id']}")
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to change password")