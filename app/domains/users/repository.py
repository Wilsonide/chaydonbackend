from sqlalchemy import select

from app.domains.users.models import User, UserRole


class UserRepository:
    async def get_by_username(
        self,
        db,
        username: str,
    ):
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        db,
        email: str,
    ):
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        db,
        user_id,
    ):
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        db,
        user,
    ):
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_graphic_designers(
        self,
        db,
    ):
        result = await db.execute(
            select(User)
            .where(
                User.role == UserRole.GRAPHIC_DESIGNER,
                User.is_active.is_(True),
            )
            .order_by(
                User.first_name.asc(),
                User.last_name.asc(),
            )
        )

        return list(result.scalars().all())
