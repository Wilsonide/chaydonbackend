from sqlalchemy import select

from app.domains.auth.models import RefreshToken


class RefreshRepository:
    async def create(self, db, token):
        db.add(token)
        await db.commit()
        await db.refresh(token)
        return token

    async def get(self, db, token):
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()
