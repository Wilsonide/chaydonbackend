from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
from jose import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """
    Hash a user's password using bcrypt.

    bcrypt only uses the first 72 bytes of a password.
    """
    pwd_bytes = password.encode("utf-8")[:72]

    salt = bcrypt.gensalt()

    hashed_password = bcrypt.hashpw(
        password=pwd_bytes,
        salt=salt,
    )

    return hashed_password.decode("utf-8")


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    password_bytes = plain_password.encode("utf-8")[:72]

    return bcrypt.checkpw(
        password=password_bytes,
        hashed_password=hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: str) -> str:
    """
    Create a short-lived access token.

    The access token is returned to the frontend and should
    be kept in memory rather than localStorage.
    """
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """
    Create a refresh token and unique session ID (jti).

    The JWT is placed inside an HttpOnly cookie.

    Only the jti is stored in the database so that the
    refresh session can be revoked without storing the
    raw refresh token.
    """
    jti = str(uuid4())

    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": expire,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token, jti
