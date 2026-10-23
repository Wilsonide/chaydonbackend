from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domains.inventory.models import MovementType


class InventoryCreate(BaseModel):
    name: str
    category: str
    unit: str
    quantity: int = Field(default=0, ge=0)
    minimum_quantity: int = Field(default=0, ge=0)
    unit_selling_price: Decimal = Field(ge=0, decimal_places=2)
    description: str | None = None


class InventoryUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    minimum_quantity: int | None = Field(default=None, ge=0)
    unit_selling_price: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
    )
    description: str | None = None


class StockMovementCreate(BaseModel):
    quantity: int = Field(gt=0)
    movement_type: MovementType
    reason: str | None = None
    production_folder_id: UUID | None = None
    unit_selling_price: Decimal | None = Field(
        default=None,
        ge=0,
        decimal_places=2,
    )


class ManualAdjustment(BaseModel):
    new_quantity: int = Field(ge=0)
    reason: str = Field(min_length=1)


class ProductionConsumption(BaseModel):
    item_id: UUID
    quantity: int = Field(gt=0)
    reason: str | None = "Consumed during production"


# ============================================================
# PRINT ORDER MATERIAL REQUIREMENTS
# ============================================================


class OrderMaterialRequirementCreate(BaseModel):
    inventory_item_id: UUID
    required_quantity: int = Field(gt=0)


class OrderMaterialRequirementUpdate(BaseModel):
    required_quantity: int = Field(gt=0)


class OrderMaterialRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    inventory_item_id: UUID

    required_quantity: int
    consumed_quantity: int
    remaining_quantity: int

    # Original unit price before discount.
    unit_selling_price: Decimal

    # Fixed discount per unit.
    discount_amount: Decimal = Decimal("0.00")

    # Price per unit after discount.
    discounted_unit_selling_price: Decimal

    # Original input, e.g. "3x2x2, 4x5x3".
    # None is valid for older records.
    dimension_input: str | None = None

    required_cost: Decimal
    consumed_cost: Decimal

    created_at: datetime
    updated_at: datetime


class OrderMaterialCalculationResponse(BaseModel):
    order_id: UUID
    total_required_cost: Decimal
    total_consumed_cost: Decimal
    total_remaining_cost: Decimal
    requirements: list[OrderMaterialRequirementResponse]


# ============================================================
# INVENTORY
# ============================================================


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    unit: str
    quantity: int
    minimum_quantity: int

    unit_selling_price: Decimal
    total_selling_price: Decimal

    description: str | None
    created_at: datetime
    updated_at: datetime


# ============================================================
# STOCK MOVEMENT HISTORY
# ============================================================


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    quantity: int
    movement_type: MovementType

    # Original price before discount.
    unit_selling_price: Decimal

    # Fixed discount applied per unit.
    discount_amount: Decimal = Decimal("0.00")

    # Final price per unit.
    discounted_unit_selling_price: Decimal

    # Total quantity multiplied by discounted unit price.
    total_selling_price: Decimal

    # Original dimension expression, when recorded.
    dimension_input: str | None = None

    reason: str | None
    recorded_by: UUID
    production_folder_id: UUID | None
    order_id: UUID | None
    created_at: datetime


# ============================================================
# LOW STOCK
# ============================================================


class LowStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    unit: str
    quantity: int
    minimum_quantity: int
    unit_selling_price: Decimal
    total_selling_price: Decimal


# ============================================================
# INVENTORY DASHBOARD
# ============================================================


class InventoryDashboardResponse(BaseModel):
    total_items: int
    total_stock_units: int
    total_inventory_value: Decimal
    low_stock_items: int
    categories: int
