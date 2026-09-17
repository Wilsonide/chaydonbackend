from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.credential_encryption import encrypt_password
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.domains.auth.models import RefreshSession
from app.domains.dashboard.repository import now_ng
from app.domains.users.credential_model import UserCredential
from app.domains.users.models import User
from app.domains.users.repository import UserRepository


class AuthService:
    def __init__(self):
        self.repo = UserRepository()

    async def register(
        self,
        db: AsyncSession,
        data,
    ) -> User:
        """
        Register a new user.

        The password is stored in two forms:

        1. password_hash:
        bcrypt hash used for authentication.

        2. password_encrypted:
        encrypted copy used by the authorized Super Admin
        credential-management system.
        """
        # ---------------------------------------------------------
        # Check username
        # ---------------------------------------------------------
        existing_username = await self.repo.get_by_username(
            db,
            data.username,
        )

        if existing_username:
            raise ValueError("Username already exists")

        # ---------------------------------------------------------
        # Check email
        # ---------------------------------------------------------
        existing_email = await self.repo.get_by_email(
            db,
            data.email,
        )

        if existing_email:
            raise ValueError("Email already exists")

        # ---------------------------------------------------------
        # Clean the password
        # ---------------------------------------------------------
        password = data.password

        if not password:
            raise ValueError("Password cannot be empty")

        if len(password.encode("utf-8")) > 72:
            raise ValueError(
                "Password cannot exceed 72 bytes because bcrypt is limited to 72 bytes."
            )

        # ---------------------------------------------------------
        # Create user
        # ---------------------------------------------------------
        user = User(
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=data.email.strip().lower(),
            username=data.username.strip(),
            password_hash=hash_password(password),
            role=data.role,
            is_active=True,
        )

        db.add(user)

        # Get the generated UUID before creating the credential.
        await db.flush()

        # ---------------------------------------------------------
        # Create recoverable encrypted credential
        # ---------------------------------------------------------
        credential = UserCredential(
            user_id=user.id,
            password_encrypted=encrypt_password(password),
        )

        db.add(credential)

        # ---------------------------------------------------------
        # Commit both records together
        # ---------------------------------------------------------
        try:
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        await db.refresh(user)

        return user

    async def login(
        self,
        db: AsyncSession,
        username: str,
        password: str,
    ):
        """
        Authenticate a user.

        Returns:
            access_token
            refresh_token

        The router is responsible for placing the refresh token
        inside the HttpOnly cookie.

        """
        user = await self.repo.get_by_username(
            db,
            username.strip(),
        )

        if not user:
            return None

        if not user.is_active:
            raise ValueError("Your account is inactive")

        password_valid = verify_password(
            password,
            user.password_hash,
        )

        if not password_valid:
            return None

        # --------------------------------------------
        # Update user presence
        # --------------------------------------------

        current_time = now_ng()

        user.last_login_at = current_time
        user.last_activity_at = current_time
        user.is_online = True

        # --------------------------------------------
        # Create tokens
        # --------------------------------------------

        access_token = create_access_token(str(user.id))

        refresh_token, jti = create_refresh_token(str(user.id))

        # Refresh-session expiration stays in UTC
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        refresh_session = RefreshSession(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            revoked=False,
        )

        db.add(refresh_session)

        await db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def refresh(self, db: AsyncSession, refresh_token: str):
        print("\n========== REFRESH DEBUG ==========")

        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

            print("1. JWT DECODE: SUCCESS")
            print("2. PAYLOAD:", payload)

        except JWTError as exc:
            print("1. JWT DECODE: FAILED")
            print("JWT ERROR:", repr(exc))
            print("===================================\n")
            return None

        if payload.get("type") != "refresh":
            print("3. TOKEN TYPE FAILED:", payload.get("type"))
            print("===================================\n")
            return None

        user_id = payload.get("sub")
        jti = payload.get("jti")

        print("3. TOKEN TYPE: refresh")
        print("4. USER ID:", user_id)
        print("5. JTI:", jti)

        if not user_id or not jti:
            print("6. USER/JTI FAILED")
            print("===================================\n")
            return None

        result = await db.execute(
            select(RefreshSession).where(RefreshSession.jti == jti)
        )

        session = result.scalar_one_or_none()

        print("6. SESSION FOUND:", bool(session))

        if not session:
            print("SESSION NOT FOUND FOR JTI:", jti)
            print("===================================\n")
            return None

        print("7. SESSION REVOKED:", session.revoked)
        print("8. SESSION EXPIRES:", session.expires_at)

        if session.revoked:
            print("9. FAILED: SESSION IS REVOKED")
            print("===================================\n")
            return None

        now = datetime.now(UTC)

        print("9. NOW UTC:", now)
        print("10. EXPIRES UTC:", session.expires_at)

        if session.expires_at <= now:
            print("11. FAILED: SESSION EXPIRED")

            session.revoked = True
            await db.commit()

            print("===================================\n")
            return None

        print("11. SESSION NOT EXPIRED")

        print(
            "12. SESSION USER ID:",
            session.user_id,
        )

        print(
            "13. TOKEN USER ID:",
            user_id,
        )

        if str(session.user_id) != str(user_id):
            print("14. FAILED: USER ID MISMATCH")
            print("===================================\n")
            return None

        user = await self.repo.get_by_id(db, user_id)

        print("14. USER FOUND:", bool(user))

        if not user:
            print("15. FAILED: USER NOT FOUND")
            print("===================================\n")
            return None

        print("15. USER ACTIVE:", user.is_active)

        if not user.is_active:
            print("16. FAILED: USER INACTIVE")
            print("===================================\n")
            return None

        # Rotate refresh token
        session.revoked = True

        new_access_token = create_access_token(str(user.id))

        new_refresh_token, new_jti = create_refresh_token(str(user.id))

        new_session = RefreshSession(
            user_id=user.id,
            jti=new_jti,
            expires_at=(now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)),
            revoked=False,
        )

        db.add(new_session)

        await db.commit()

        print("16. REFRESH SUCCESS")
        print("===================================\n")

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
        }

    async def logout(
        self,
        db: AsyncSession,
        refresh_token: str,
    ) -> bool:
        """
        Revoke the refresh session associated with the refresh token.

        The router is responsible for deleting the
        HttpOnly cookie.
        """
        # -------------------------------------------------
        # 1. Decode refresh token
        # -------------------------------------------------

        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

        except JWTError:
            return False

        # -------------------------------------------------
        # 2. Make sure it is a refresh token
        # -------------------------------------------------

        if payload.get("type") != "refresh":
            return False

        # -------------------------------------------------
        # 3. Get jti
        # -------------------------------------------------

        jti = payload.get("jti")

        if not jti:
            return False

        # -------------------------------------------------
        # 4. Find session
        # -------------------------------------------------

        result = await db.execute(
            select(RefreshSession).where(RefreshSession.jti == jti)
        )

        session = result.scalar_one_or_none()

        if not session:
            return False

        # -------------------------------------------------
        # 5. Revoke session
        # -------------------------------------------------

        if not session.revoked:
            session.revoked = True

            await db.commit()

        return True
