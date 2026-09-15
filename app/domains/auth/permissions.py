from fastapi import Depends, HTTPException, status

from app.domains.auth.dependencies import get_current_user
from app.domains.users.models import User, UserRole


def require_role(*allowed_roles: UserRole):
    async def checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return checker


RequireSuperAdmin = require_role(
    UserRole.SUPER_ADMIN,
)

RequireFrontDesk = require_role(
    UserRole.SUPER_ADMIN,
    UserRole.FRONT_DESK,
)

RequireGraphicLead = require_role(
    UserRole.GRAPHIC_LEAD,
)

RequireGraphicDesigner = require_role(
    UserRole.GRAPHIC_DESIGNER,
)

RequireSuperAdminOrFrontDesk = require_role(
    UserRole.SUPER_ADMIN,
    UserRole.FRONT_DESK,
)

RequireSuperAdminOrGraphicLead = require_role(
    UserRole.SUPER_ADMIN,
    UserRole.GRAPHIC_LEAD,
)

RequireDesignTeam = require_role(
    UserRole.SUPER_ADMIN,
    UserRole.GRAPHIC_LEAD,
    UserRole.GRAPHIC_DESIGNER,
)
