from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.tasks.models import (
    TaskPriority,
    TaskStatus,
)

# ============================================================
# CREATE TASK
# ============================================================


class TaskCreate(BaseModel):
    production_folder_id: UUID
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: datetime | None = None


# ============================================================
# UPDATE TASK
# ============================================================


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: TaskPriority | None = None
    deadline: datetime | None = None


# ============================================================
# DESIGNER STATUS UPDATE
# ============================================================


class DesignerTaskUpdate(BaseModel):
    status: TaskStatus


# ============================================================
# COMMENT USER
# ============================================================


class TaskCommentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    username: str
    role: str


# ============================================================
# CREATE COMMENT
# ============================================================


class TaskCommentCreate(BaseModel):
    message: str | None = None


# ============================================================
# COMMENT RESPONSE
# ============================================================


class TaskCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user: TaskCommentUserResponse

    message: str | None

    attachment_url: str | None
    attachment_name: str | None
    attachment_type: str | None

    is_revision_request: bool
    is_approval: bool

    created_at: datetime


# ============================================================
# TASK ASSIGNEE
# ============================================================


class TaskAssigneeResponse(BaseModel):
    """
    Information about the designer assigned to a task.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    username: str


# ============================================================
# PRODUCTION FOLDER SUMMARY
# ============================================================


class TaskProductionFolderResponse(BaseModel):
    """
    Descriptive production-folder information shown with a task.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    production_number: int
    folder_number: str
    title: str
    requirements: str | None
    status: str
    created_at: datetime


# ============================================================
# TASK RESPONSE
# ============================================================


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    production_folder_id: UUID
    assigned_by: UUID
    assigned_to: UUID | None

    production_folder: TaskProductionFolderResponse

    assignee: TaskAssigneeResponse | None = Field(
        default=None,
        validation_alias="assigned_designer",
        serialization_alias="assignee",
    )

    title: str
    description: str | None

    priority: TaskPriority
    status: TaskStatus

    deadline: datetime | None

    created_at: datetime


# ============================================================
# TASK REVIEW
# ============================================================


class TaskReview(BaseModel):
    approve: bool
    message: str | None = None


# ============================================================
# TASK ASSIGNMENT
# ============================================================


class TaskAssignment(BaseModel):
    assigned_to: UUID
