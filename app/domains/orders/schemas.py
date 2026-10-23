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
            input_quantity = "3x2"

        Dimensions with copies:
            input_quantity = "3x2x2"

        Multiple expressions:
            input_quantity = "3x2x2, 4x5x3"

    Dimension expressions are calculated only for inventory
    items measured in feet.

    discount_amount is a fixed monetary discount per unit,
    not a percentage.
    """

    inventory_item_id: UUID

    # Used when the frontend provides a plain numeric quantity.
    quantity: int | None = Field(
        default=None,
        gt=0,
    )

    # Exact quantity or dimension expression entered by staff.
    input_quantity: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    # Fixed discount applied to each inventory unit.
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        decimal_places=2,
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

    inventory_items: list[OrderInventoryItemCreate] = Field(
        default_factory=list,
    )


# ============================================================
# UPDATE ORDER
# ============================================================


class OrderInventoryItemUpdate(BaseModel):
    inventory_item_id: UUID

    # Preserve the exact staff input when updating an order.
    input_quantity: str = Field(
        min_length=1,
        max_length=500,
    )

    # Fixed discount per inventory unit.
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        decimal_places=2,
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
