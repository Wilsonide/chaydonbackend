from pydantic import BaseModel, EmailStr

from app.domains.users.models import UserRole


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    username: str
    password: str
    role: UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AuthResponse(BaseModel):
    access_token: str

    token_type: str = "bearer"
