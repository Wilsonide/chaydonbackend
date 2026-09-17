from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.users.credential_model import UserCredential
from app.domains.users.models import User, UserRole


class UserCredentialRepository:
    async def get_by_user_id(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> UserCredential | None:
        result = await db.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        db: AsyncSession,
        credential_id: UUID,
    ) -> UserCredential | None:
        result = await db.execute(
            select(UserCredential).where(UserCredential.id == credential_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        credential: UserCredential,
    ) -> UserCredential:
        db.add(credential)
        await db.flush()
        return credential

    async def delete(
        self,
        db: AsyncSession,
        credential: UserCredential,
    ) -> None:
        await db.delete(credential)
        await db.flush()

    async def get_staff_users(
        self,
        db: AsyncSession,
        search: str | None = None,
        include_super_admin: bool = False,
    ) -> list[User]:
        staff_roles = [
            UserRole.FRONT_DESK,
            UserRole.GRAPHIC_LEAD,
            UserRole.GRAPHIC_DESIGNER,
        ]

        if include_super_admin:
            staff_roles.append(UserRole.SUPER_ADMIN)

        query = (
            select(User)
            .options(
                selectinload(User.credential),
            )
            .where(User.role.in_(staff_roles))
        )

        if search:
            search_value = f"%{search.strip()}%"

            query = query.where(
                User.first_name.ilike(search_value)
                | User.last_name.ilike(search_value)
                | User.username.ilike(search_value)
                | User.email.ilike(search_value)
            )

        query = query.order_by(
            User.first_name.asc(),
            User.last_name.asc(),
        )

        result = await db.execute(query)

        return list(result.scalars().all())
