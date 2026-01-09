from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
from jose import jwt, JWSError
from ..common.config import settings
from uuid import uuid4
from ..services.email_service import send_reset_email
from jose import JWTError, ExpiredSignatureError
import bcrypt
from ..utils.logger import get_logger

logger = get_logger(__name__)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt, truncating to 72 bytes as required.

    We intentionally avoid using passlib's bcrypt handler here because some
    environments have a mismatched `bcrypt` package that causes import-time
    errors in passlib's version checks. Using the bcrypt library directly
    avoids that issue and ensures consistent behavior.
    """
    # Normalize to bytes and truncate to 72 bytes (bcrypt limit)
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    else:
        password_bytes = password
    if len(password_bytes) > 72:
        # Truncate at byte-level to satisfy bcrypt requirement
        password_bytes = password_bytes[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored bcrypt hash, truncating to 72 bytes."""
    if isinstance(password, str):
        password_bytes = password.encode("utf-8")
    else:
        password_bytes = password
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except Exception as e:
        logger.exception("Password verification failed: %s", e)
        return False



def _now() -> datetime:
    return datetime.utcnow()


# Token blocklist (in-memory for now)
# _token_blocklist = set()

# def block_token(token: str):
#     _token_blocklist.add(token)

# def is_token_blocked(token: str) -> bool:
#     return token in _token_blocklist

def create_access_token(subject: str, extra: Dict[str, Any] | None = None) -> str:
    """
    subject: user id (string)
    extra: additional claims
    """
    now = _now()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid4()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def create_refresh_token(subject: str) -> str:
    now = _now()
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def create_reset_token(subject: str, email) -> str:
    """Short-lived token used for password reset"""
    exp = datetime.utcnow() + timedelta(hours=1)
    iat = datetime.utcnow()

    reset_payload = {"sub": subject, "exp": exp, "iat": iat, "type": "reset"}
    reset_token = jwt.encode(reset_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    # send reset email (async/email service handles errors)
    try:
        send_reset_email(email, reset_token)
    except Exception as e:
        logger.exception("Failed to send reset email to %s: %s", email, e)
        # still return a success-ish message to avoid exposing email send issues
    return {"message": "Password reset link has been sent to your email."}


def decode_token(token: str) -> Dict[str, Any]:
    logger.debug("Decoding token")
    try:
        # Decode while verifying signature but not exp; we'll enforce exp with 60s leeway manually
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False, "verify_exp": False},
        )
        # Manual expiration check with 60s grace period
        exp = payload.get("exp")
        if exp is not None:
            now = int(datetime.utcnow().timestamp())
            if now > int(exp) + 60:
                logger.debug("Token expired (beyond leeway)")
                raise ExpiredSignatureError("Token expired")
        return payload
    except ExpiredSignatureError:
        logger.info("Token has expired")
        raise JWTError("Token expired")
    except JWTError:
        logger.info("Token decoding failed (invalid)")
        raise JWTError("Invalid token")
    except Exception as e:
        logger.exception("Token decoding failed (unknown error): %s", e)
        raise JWTError("Invalid token")
