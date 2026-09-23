from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.orders.models import (
    OrderStatus,
    OrderType,
)

# ============================================================
# CREATE ORDER
# ============================================================


class OrderCreate(BaseModel):
    customer_id: UUID

    order_type: OrderType = OrderType.DESIGN

    title: str

    description: str | None = None

    total_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        decimal_places=2,
    )

    due_date: date | None = None


# ============================================================
# UPDATE ORDER
# ============================================================


class OrderUpdate(BaseModel):
    title: str | None = None

    description: str | None = None

    order_type: OrderType | None = None

    status: OrderStatus | None = None

    total_amount: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
    )

    due_date: date | None = None


# ============================================================
# CUSTOMER RESPONSE
# ============================================================


class OrderCustomerResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    name: str

    phone: str

    email: str | None


# ============================================================
# ORDER FILE RESPONSE
# ============================================================


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


# ============================================================
# ORDER RESPONSE
# ============================================================


class OrderResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    customer_id: UUID

    customer: OrderCustomerResponse

    order_type: OrderType

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
