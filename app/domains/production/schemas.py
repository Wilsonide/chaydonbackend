from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.production.models import ProductionStatus
from app.domains.tasks.models import TaskPriority, TaskStatus

# ============================================================
# CREATE
# ============================================================


class ProductionCreate(BaseModel):
    order_id: UUID
    title: str
    requirements: str | None = None


# ============================================================
# UPDATE
# ============================================================


class ProductionUpdate(BaseModel):
    title: str | None = None
    requirements: str | None = None
    status: ProductionStatus | None = None


# ============================================================
# PRODUCTION FILE
# ============================================================


class ProductionFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_url: str
    public_id: str | None
    file_type: str | None
    resource_type: str
    uploaded_by: UUID
    created_at: datetime


# ============================================================
# PRODUCTION ACTIVITY
# ============================================================


class ProductionActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    action: str
    description: str
    created_at: datetime


# ============================================================
# PRODUCTION TASK SUMMARY
# ============================================================


class ProductionTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    assigned_to: UUID | None
    priority: TaskPriority
    status: TaskStatus
    deadline: datetime | None


# ============================================================
# PRODUCTION RESPONSE
# ============================================================


class ProductionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    folder_number: str
    title: str
    requirements: str | None
    status: ProductionStatus
    created_at: datetime
    updated_at: datetime

    files: list[ProductionFileResponse] = []
    activities: list[ProductionActivityResponse] = []
    tasks: list[ProductionTaskResponse] = []
