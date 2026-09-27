from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.orders.models import (
    OrderStatus,
    OrderType,
)

# ============================================================
# ORDER INVENTORY ITEM
# ============================================================


class OrderInventoryItemCreate(BaseModel):
    """
    Inventory material selected while creating an order.

    Examples:

        Plain quantity:
            quantity = 12

        Dimension input:
            input_quantity = "3*4"

        For a feet-based inventory item:
            "3*4" -> 12 feet
    """

    inventory_item_id: UUID

    # Used when the frontend already has a plain numeric quantity.
    quantity: int | None = Field(
        default=None,
        gt=0,
    )

    # What the staff actually typed.
    #
    # Examples:
    #   "12"
    #   "3*4"
    #   "3 x 4"
    #   "3×4"
    input_quantity: str | None = None


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

    inventory_items: list[OrderInventoryItemCreate] = Field(
        default_factory=list,
    )


# ============================================================
# UPDATE ORDER
# ============================================================


class OrderInventoryItemUpdate(BaseModel):
    inventory_item_id: UUID
    input_quantity: str = Field(
        min_length=1,
        max_length=100,
    )


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

    inventory_items: list[OrderInventoryItemUpdate] | None = None


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
