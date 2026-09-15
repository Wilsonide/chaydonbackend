from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.domains.users.models import UserRole


class StaffCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str
    username: str
    role: UserRole
    is_active: bool

    password: str | None = None


class StaffRoleUpdate(BaseModel):
    role: UserRole


class StaffPasswordUpdate(BaseModel):
    password: str


class StaffStatusUpdate(BaseModel):
    is_active: bool


class StaffCredentialDetailResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    username: str
    role: UserRole
    is_active: bool
    password: str
