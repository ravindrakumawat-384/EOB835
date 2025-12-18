from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
from jose import jwt, JWSError
from ..common.config import settings
from uuid import uuid4
from ..services.email_service import send_reset_email
from jose import JWTError, ExpiredSignatureError


_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


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
    now = _now()
    print("got  email-------> ", email)
    print("got  email-------> ", email)
    print("got  email-------> ", email)
    # expire = now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    # payload = {
    #     "sub": subject,
    #     "type": "reset",
    #     "exp": int(expire.timestamp()),
    #     "iat": int(now.timestamp()),
    #     "jti": str(uuid4()),
    # }
    # reset_payload = {"sub": subject, "exp": expire.isoformat(), "iat": now.isoformat(), "type": "reset"}


    # now = datetime.utcnow()
    print("subject---> ", subject)
    print("subject---> ", subject)
    print("subject---> ", subject)
    # exp = now + timedelta(hours=1)
    exp = datetime.utcnow() + timedelta(hours=1)
    iat = datetime.utcnow()


    reset_payload = {"sub": subject, "exp": exp, "iat": iat, "type": "reset"}
    reset_token = jwt.encode(reset_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    print()
    print("reset_token---> ", reset_token)
    print()
    # reset_link = f"https://your-frontend/reset-password?token={reset_token}"

    send_reset_email(email, reset_token)
    # sent = send_reset_email(user["email"], token)
    return {"message": "Password reset link has been sent to your email."}



    # print(f"[create_reset_token] iat: {payload['iat']} ({datetime.utcfromtimestamp(payload['iat'])}), exp: {payload['exp']} ({datetime.utcfromtimestamp(payload['exp'])})")
    return jwt.encode(reset_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    # return jwt.encode(payload["jti"])
    # return payload["jti"]


def decode_token(token: str) -> Dict[str, Any]:
    print("Enter in Decoding token:")
    print("Enter in Decoding token:", token)
    print("Return decode token===> ")
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
                print("Token expired (beyond leeway)")
                raise ExpiredSignatureError("Token expired")
        return payload
    except ExpiredSignatureError:
        print("Token expired")
        raise JWTError("Token expired")
    except JWTError:
        print("Token decoding failed (invalid)")
        raise JWTError("Invalid token")
    except Exception as e:
        print("Token decoding failed (unknown error)")
        raise JWTError("Invalid token")
