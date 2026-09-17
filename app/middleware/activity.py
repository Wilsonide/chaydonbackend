from datetime import UTC, datetime, timedelta

from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.domains.users.models import User

ACTIVITY_UPDATE_INTERVAL = timedelta(seconds=60)


class ActivityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        authorization = request.headers.get("Authorization")

        if not authorization or not authorization.startswith("Bearer "):
            return response

        token = authorization[7:]

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

            if payload.get("type") != "access":
                return response

            user_id = payload.get("sub")

            if not user_id:
                return response

            current_time = datetime.now(UTC)

            async with AsyncSessionLocal() as db:
                user = await db.get(User, user_id)

                if not user:
                    return response

                # Only write activity when the previous update
                # is older than the configured interval.
                should_update = (
                    user.last_activity_at is None
                    or current_time - user.last_activity_at >= ACTIVITY_UPDATE_INTERVAL
                )

                if should_update:
                    user.last_activity_at = current_time
                    user.is_online = True

                    await db.commit()

        except Exception:
            pass

        return response
