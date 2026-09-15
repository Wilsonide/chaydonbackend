from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.orders.models import OrderStatus


class OrderCreate(BaseModel):
    customer_id: UUID
    title: str
    description: str | None = None
    total_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        decimal_places=2,
    )
    due_date: date | None = None


class OrderUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: OrderStatus | None = None
    total_amount: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
    )
    due_date: date | None = None


class OrderCustomerResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    name: str
    phone: str
    email: str | None


class OrderFileResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    file_name: str
    file_url: str
    file_type: str | None
    uploaded_by: UUID
    created_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    customer_id: UUID
    customer: OrderCustomerResponse
    title: str
    description: str | None
    status: OrderStatus
    total_amount: Decimal
    due_date: date | None
    files: list[OrderFileResponse] = Field(
        default_factory=list,
    )
    created_at: datetime
    updated_at: datetime
