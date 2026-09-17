from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_encryption import (
    decrypt_password,
    encrypt_password,
)
from app.core.security import hash_password
from app.domains.users.credential_model import UserCredential
from app.domains.users.credential_repository import (
    UserCredentialRepository,
)
from app.domains.users.models import User, UserRole
from app.domains.users.repository import UserRepository


class UserCredentialService:
    def __init__(self):
        self.repo = UserCredentialRepository()
        self.user_repo = UserRepository()

    async def _get_user(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> User:
        user = await self.user_repo.get_by_id(
            db,
            user_id,
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found.",
            )

        return user

    def _is_staff_role(
        self,
        role: UserRole,
    ) -> bool:
        return role in {
            UserRole.FRONT_DESK,
            UserRole.GRAPHIC_LEAD,
            UserRole.GRAPHIC_DESIGNER,
        }

    async def list_staff(
        self,
        db: AsyncSession,
        search: str | None = None,
    ):
        return await self.repo.get_staff_users(
            db,
            search=search,
            include_super_admin=False,
        )

    async def get_staff_credential(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> dict:
        user = await self._get_user(
            db,
            user_id,
        )

        if not self._is_staff_role(user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin credentials cannot be managed here.",
            )

        credential = await self.repo.get_by_user_id(
            db,
            user.id,
        )

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No recoverable credential exists for this staff member. "
                    "Set a new password first."
                ),
            )

        password = decrypt_password(credential.password_encrypted)

        return {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "password": password,
        }

    async def set_password(
        self,
        db: AsyncSession,
        user_id: UUID,
        password: str,
    ) -> dict:
        user = await self._get_user(
            db,
            user_id,
        )

        if not self._is_staff_role(user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin credentials cannot be changed here.",
            )

        password = password.strip()

        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password cannot be empty.",
            )

        if len(password.encode("utf-8")) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Password cannot exceed 72 bytes because "
                    "bcrypt is limited to 72 bytes."
                ),
            )

        user.password_hash = hash_password(password)

        encrypted_password = encrypt_password(password)

        credential = await self.repo.get_by_user_id(
            db,
            user.id,
        )

        if credential:
            credential.password_encrypted = encrypted_password
        else:
            credential = UserCredential(
                user_id=user.id,
                password_encrypted=encrypted_password,
            )

            await self.repo.create(
                db,
                credential,
            )

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return await self.get_staff_credential(
            db,
            user.id,
        )

    async def update_role(
        self,
        db: AsyncSession,
        user_id: UUID,
        role: UserRole,
    ) -> User:
        user = await self._get_user(
            db,
            user_id,
        )

        if user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin role cannot be changed here.",
            )

        if role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=("You cannot promote staff to Super Admin from this page."),
            )

        user.role = role

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        await db.refresh(user)

        return user

    async def update_status(
        self,
        db: AsyncSession,
        user_id: UUID,
        is_active: bool,
    ) -> User:
        user = await self._get_user(
            db,
            user_id,
        )

        if user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin status cannot be changed here.",
            )

        user.is_active = is_active

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        await db.refresh(user)

        return user

    async def delete_staff(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> None:
        user = await self._get_user(
            db,
            user_id,
        )

        if user.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin accounts cannot be deleted here.",
            )

        await db.delete(user)

        try:
            await db.commit()

        except Exception:
            await db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This staff member cannot be deleted because "
                    "other records still reference this account. "
                    "Deactivate the account instead."
                ),
            )
