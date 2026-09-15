from typing import Annotated

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.dependencies import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.permissions import RequireSuperAdmin
from app.domains.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
)
from app.domains.auth.service import AuthService
from app.domains.users.models import User

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

service = AuthService()


# ---------------------------------------------------------
# REGISTER
# ---------------------------------------------------------


@router.post("/register")
async def register(
    data: RegisterRequest,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        User,
        Depends(RequireSuperAdmin),
    ],
):
    try:
        return await service.register(
            db,
            data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------


@router.post(
    "/login",
    response_model=AuthResponse,
)
async def login(
    data: LoginRequest,
    response: Response,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
):
    try:
        result = await service.login(
            db,
            data.username,
            data.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    # -----------------------------------------------------
    # Store refresh token in HttpOnly cookie
    # -----------------------------------------------------

    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60),
        path="/auth",
        domain=settings.COOKIE_DOMAIN,
    )

    # -----------------------------------------------------
    # NEVER return refresh token to frontend
    # -----------------------------------------------------

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
    }


# ---------------------------------------------------------
# REFRESH
# ---------------------------------------------------------


@router.post(
    "/refresh",
    response_model=AuthResponse,
)
async def refresh(
    response: Response,
    refresh_token: Annotated[
        str | None,
        Cookie(),
    ],
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
):
    # -----------------------------------------------------
    # Browser must have refresh cookie
    # -----------------------------------------------------
    print("REFRESH TOKEN FROM COOKIE:", refresh_token)
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token not found",
        )

    result = await service.refresh(
        db,
        refresh_token,
    )

    if not result:
        # -------------------------------------------------
        # Remove invalid cookie
        # -------------------------------------------------

        response.delete_cookie(
            key="refresh_token",
            path="/auth",
            domain=settings.COOKIE_DOMAIN,
        )

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token",
        )

    # -----------------------------------------------------
    # Replace old refresh cookie with new one
    # -----------------------------------------------------

    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60),
        path="/auth",
        domain=settings.COOKIE_DOMAIN,
    )

    # -----------------------------------------------------
    # Return only access token
    # -----------------------------------------------------

    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
    }


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Annotated[
        str | None,
        Cookie(),
    ],
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
):
    # -----------------------------------------------------
    # Revoke refresh session if cookie exists
    # -----------------------------------------------------

    if refresh_token:
        await service.logout(
            db,
            refresh_token,
        )

    # -----------------------------------------------------
    # Delete browser cookie
    # -----------------------------------------------------

    response.delete_cookie(
        key="refresh_token",
        path="/auth",
        domain=settings.COOKIE_DOMAIN,
    )

    return {
        "message": "Logged out successfully",
    }


# ---------------------------------------------------------
# CURRENT USER
# ---------------------------------------------------------


@router.get("/me")
async def me(
    user: Annotated[
        User,
        Depends(get_current_user),
    ],
):
    return user


# ---------------------------------------------------------
# TEMPORARY SUPER ADMIN AUTHORIZATION TEST
# ---------------------------------------------------------
#
# Keep this only while debugging authorization.
# Remove it after confirming RequireSuperAdmin works.
#


@router.get("/test-superadmin")
async def test_superadmin(
    user: Annotated[
        User,
        Depends(RequireSuperAdmin),
    ],
):
    return {
        "message": "Superadmin access granted",
        "username": user.username,
        "role": user.role,
    }
