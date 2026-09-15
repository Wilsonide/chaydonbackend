from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.permissions import (
    RequireDesignTeam,
    RequireSuperAdmin,
    RequireSuperAdminOrGraphicLead,
)
from app.domains.production.models import ProductionStatus
from app.domains.production.schemas import (
    ProductionCreate,
    ProductionFileResponse,
    ProductionResponse,
    ProductionUpdate,
)
from app.domains.production.service import ProductionService
from app.shared.pagination import Pagination
from app.shared.responses import PaginatedResponse

router = APIRouter(
    prefix="/production",
    tags=["Production"],
)

service = ProductionService()


# ============================================================
# CREATE PRODUCTION FOLDER
# ============================================================


@router.post(
    "",
    response_model=ProductionResponse,
)
async def create_production_folder(
    data: ProductionCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdmin),
    ],
):
    return await service.create(
        db,
        data,
        str(current_user.id),
    )


# ============================================================
# GET ALL PRODUCTION FOLDERS
# ============================================================


@router.get(
    "",
    response_model=PaginatedResponse[ProductionResponse],
)
async def get_production_folders(
    pagination: Pagination,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
    search: str | None = None,
    status: ProductionStatus | None = None,
):
    return await service.get_all(
        db,
        pagination,
        search,
        status,
    )


# ============================================================
# GET SINGLE PRODUCTION FOLDER
# ============================================================


@router.get(
    "/{folder_id}",
    response_model=ProductionResponse,
)
async def get_production_folder(
    folder_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
):
    return await service.get_by_id(
        db,
        folder_id,
    )


# ============================================================
# UPDATE PRODUCTION FOLDER
# ============================================================


@router.patch(
    "/{folder_id}",
    response_model=ProductionResponse,
)
async def update_production_folder(
    folder_id: str,
    data: ProductionUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
):
    return await service.update(
        db,
        folder_id,
        data,
        str(current_user.id),
    )


# ============================================================
# UPLOAD PRODUCTION FILE
# ============================================================


@router.post(
    "/{folder_id}/files",
    response_model=ProductionFileResponse,
)
async def upload_file(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireDesignTeam),
    ],
    folder_id: str,
    file: UploadFile = File(...),
):
    return await service.upload_file(
        db,
        folder_id,
        file,
        str(current_user.id),
    )


# ============================================================
# DELETE PRODUCTION FILE
# ============================================================


@router.delete(
    "/files/{file_id}",
)
async def delete_file(
    file_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
):
    return await service.delete_file(
        db,
        file_id,
        str(current_user.id),
    )
