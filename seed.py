import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.domains.users.models import User, UserRole


async def seed():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == "SUPERytrtu-ADMIN")
        )

        existing_user = result.scalar_one_or_none()

        if existing_user:
            print("SUPER-ADMIN already exists.")
            return

        user = User(
            first_name="Wilsonide",
            last_name="Admin",
            email="admimn@printflow.com",
            username="SUPERytrtu-ADMIN",
            password_hash=hash_password("Admin@123"),
            role=UserRole.GRAPHIC_DESIGNER,
            is_active=True,
        )

        db.add(user)

        await db.commit()

        print("DEs created successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
