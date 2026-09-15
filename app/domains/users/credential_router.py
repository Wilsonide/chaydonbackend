from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.permissions import RequireSuperAdmin
from app.domains.users.credential_schemas import (
    StaffCredentialDetailResponse,
    StaffCredentialResponse,
    StaffPasswordUpdate,
    StaffRoleUpdate,
    StaffStatusUpdate,
)
from app.domains.users.credential_service import UserCredentialService

router = APIRouter(
    prefix="/users/credentials",
    tags=["Staff Credentials"],
)

service = UserCredentialService()


@router.get(
    "",
    response_model=list[StaffCredentialResponse],
)
async def get_staff_credentials(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
):
    """
    Return staff credential records.

    Passwords are not decrypted in the list endpoint.
    The password is retrieved individually through the detail endpoint.
    """

    users = await service.list_staff(
        db,
        search=search,
    )

    response = []

    for user in users:
        response.append(
            StaffCredentialResponse(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                username=user.username,
                role=user.role,
                is_active=user.is_active,
                password=None,
            )
        )

    return response


@router.get(
    "/{user_id}",
    response_model=StaffCredentialDetailResponse,
)
async def get_staff_credential(
    user_id: UUID,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
):
    """
    Return one staff member including the decrypted password.

    This endpoint is restricted to Super Admin.
    """

    return await service.get_staff_credential(
        db,
        user_id,
    )


@router.patch(
    "/{user_id}/password",
    response_model=StaffCredentialDetailResponse,
)
async def change_staff_password(
    user_id: UUID,
    data: StaffPasswordUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
):
    return await service.set_password(
        db,
        user_id,
        data.password,
    )


@router.patch(
    "/{user_id}/role",
    response_model=StaffCredentialResponse,
)
async def change_staff_role(
    user_id: UUID,
    data: StaffRoleUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
):
    user = await service.update_role(
        db,
        user_id,
        data.role,
    )

    return StaffCredentialResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        password=None,
    )


@router.patch(
    "/{user_id}/status",
    response_model=StaffCredentialResponse,
)
async def change_staff_status(
    user_id: UUID,
    data: StaffStatusUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
):
    user = await service.update_status(
        db,
        user_id,
        data.is_active,
    )

    return StaffCredentialResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        password=None,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_staff(
    user_id: UUID,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
):
    await service.delete_staff(
        db,
        user_id,
    )
