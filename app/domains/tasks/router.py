from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.domains.auth.dependencies import (
    get_current_user,
)
from app.domains.auth.permissions import (
    RequireDesignTeam,
    RequireGraphicDesigner,
    RequireGraphicLead,
    RequireSuperAdminOrGraphicLead,
)
from app.domains.tasks.models import (
    TaskPriority,
    TaskStatus,
)
from app.domains.tasks.schemas import (
    DesignerTaskUpdate,
    TaskAssignment,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskResponse,
    TaskReview,
    TaskUpdate,
)
from app.domains.tasks.service import TaskService
from app.shared.pagination import Pagination
from app.shared.responses import PaginatedResponse

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)

service = TaskService()


# ============================================================
# CREATE TASK
# ============================================================


@router.post(
    "",
    response_model=TaskResponse,
)
async def create_task(
    data: TaskCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
):
    return await service.create(
        db,
        data,
        str(current_user.id),
    )


# ============================================================
# GET ALL TASKS
# ============================================================


@router.get(
    "",
    response_model=PaginatedResponse[TaskResponse],
)
async def get_all_tasks(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
    pagination: Pagination,
    search: str | None = Query(
        default=None,
    ),
    status: TaskStatus | None = Query(
        default=None,
    ),
    priority: TaskPriority | None = Query(
        default=None,
    ),
):
    return await service.get_all(
        db=db,
        page=pagination.page,
        limit=pagination.limit,
        search=search,
        status=status,
        priority=priority,
    )


# ============================================================
# GET TASKS FOR PRODUCTION FOLDER
# ============================================================


@router.get(
    "/folder/{folder_id}",
    response_model=PaginatedResponse[TaskResponse],
)
async def folder_tasks(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
    folder_id: str,
    pagination: Pagination,
    search: str | None = Query(
        default=None,
    ),
):
    return await service.get_folder_tasks(
        db=db,
        folder_id=folder_id,
        page=pagination.page,
        limit=pagination.limit,
        search=search,
    )


# ============================================================
# GET MY TASKS
# ============================================================


@router.get(
    "/my",
    response_model=PaginatedResponse[TaskResponse],
)
async def my_tasks(
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireGraphicDesigner),
    ],
    pagination: Pagination,
    search: str | None = Query(
        default=None,
    ),
):
    return await service.get_designer_tasks(
        db=db,
        user_id=str(current_user.id),
        page=pagination.page,
        limit=pagination.limit,
        search=search,
    )


# ============================================================
# ASSIGN / REASSIGN TASK
# ============================================================


@router.patch(
    "/{task_id}/assign",
    response_model=TaskResponse,
)
async def assign_task(
    task_id: str,
    data: TaskAssignment,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireGraphicLead),
    ],
):
    return await service.assign_task(
        db,
        task_id,
        data.assigned_to,
        str(current_user.id),
    )


# ============================================================
# GET SINGLE TASK
# ============================================================


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
)
async def get_task(
    task_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(),
    ],
):
    return await service.get_by_id(
        db,
        task_id,
    )


# ============================================================
# UPDATE TASK
# ============================================================


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
)
async def update_task(
    task_id: str,
    data: TaskUpdate,
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
        task_id,
        data,
        str(current_user.id),
    )


# ============================================================
# DELETE TASK
# ============================================================


@router.delete(
    "/{task_id}",
)
async def delete_task(
    task_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
):
    return await service.delete(
        db,
        task_id,
    )


# ============================================================
# UPDATE MY TASK STATUS
# ============================================================


@router.patch(
    "/{task_id}/status",
    response_model=TaskResponse,
)
async def update_my_task(
    task_id: str,
    data: DesignerTaskUpdate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireGraphicDesigner),
    ],
):
    return await service.designer_update_status(
        db,
        task_id,
        str(current_user.id),
        data.status,
    )


# ============================================================
# REVIEW TASK
# ============================================================


@router.post(
    "/{task_id}/review",
    response_model=TaskResponse,
)
async def review_task(
    task_id: str,
    data: TaskReview,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireSuperAdminOrGraphicLead),
    ],
):
    return await service.review_task(
        db,
        task_id,
        str(current_user.id),
        data.approve,
        data.message,
    )


# ============================================================
# ADD COMMENT
# ============================================================


@router.post(
    "/{task_id}/comments",
    response_model=TaskCommentResponse,
)
async def add_comment(
    task_id: str,
    data: TaskCommentCreate,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(get_current_user),
    ],
):
    return await service.add_comment(
        db,
        task_id,
        str(current_user.id),
        data.message,
    )


# ============================================================
# GET COMMENTS
# ============================================================


@router.get(
    "/{task_id}/comments",
    response_model=list[TaskCommentResponse],
)
async def get_comments(
    task_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    _: Annotated[
        object,
        Depends(get_current_user),
    ],
):
    return await service.get_comments(
        db,
        task_id,
    )


# ============================================================
# UPLOAD TASK ATTACHMENT
# ============================================================


@router.post(
    "/{task_id}/comments/with-attachment",
    response_model=TaskCommentResponse,
)
async def add_comment_with_attachment(
    task_id: str,
    message: Annotated[
        str | None,
        Form(),
    ] = None,
    file: Annotated[
        UploadFile | None,
        File(),
    ] = None,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ] = None,
    current_user: Annotated[
        object,
        Depends(get_current_user),
    ] = None,
):
    return await service.add_comment_with_attachment(
        db,
        task_id,
        str(current_user.id),
        message,
        file,
    )


# ============================================================
# DELETE TASK ATTACHMENT
# ============================================================


@router.delete(
    "/attachments/{comment_id}",
)
async def delete_attachment(
    comment_id: str,
    db: Annotated[
        AsyncSession,
        Depends(get_db),
    ],
    current_user: Annotated[
        object,
        Depends(RequireDesignTeam),
    ],
):
    return await service.delete_attachment(
        db,
        comment_id,
        str(current_user.id),
    )
