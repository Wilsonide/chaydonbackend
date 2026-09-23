from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domains.inventory.models import MovementType


class InventoryCreate(BaseModel):
    name: str
    category: str
    unit: str
    quantity: int = 0
    minimum_quantity: int = 0
    unit_selling_price: float
    description: str | None = None


class InventoryUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    minimum_quantity: int | None = None
    unit_selling_price: float | None = None
    description: str | None = None


class StockMovementCreate(BaseModel):
    quantity: int
    movement_type: MovementType
    reason: str | None = None
    production_folder_id: UUID | None = None
    unit_selling_price: float | None = None


class ManualAdjustment(BaseModel):
    new_quantity: int
    reason: str


class ProductionConsumption(BaseModel):
    item_id: UUID
    quantity: int
    reason: str | None = "Consumed during production"


# ============================================================
# PRINT ORDER MATERIAL REQUIREMENTS
# ============================================================


class OrderMaterialRequirementCreate(BaseModel):
    inventory_item_id: UUID
    required_quantity: int


class OrderMaterialRequirementUpdate(BaseModel):
    required_quantity: int


class OrderMaterialRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    inventory_item_id: UUID
    required_quantity: int
    consumed_quantity: int
    remaining_quantity: int
    unit_selling_price: float
    required_cost: float
    consumed_cost: float
    created_at: datetime
    updated_at: datetime


class OrderMaterialCalculationResponse(BaseModel):
    order_id: UUID
    total_required_cost: float
    total_consumed_cost: float
    total_remaining_cost: float
    requirements: list[OrderMaterialRequirementResponse]


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    unit: str
    quantity: int
    minimum_quantity: int
    unit_selling_price: float
    total_selling_price: float
    description: str | None
    created_at: datetime
    updated_at: datetime


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    quantity: int
    movement_type: MovementType
    unit_selling_price: float
    total_selling_price: float
    reason: str | None
    recorded_by: UUID
    production_folder_id: UUID | None
    order_id: UUID | None
    created_at: datetime


class LowStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    unit: str
    quantity: int
    minimum_quantity: int
    unit_selling_price: float
    total_selling_price: float


class InventoryDashboardResponse(BaseModel):
    total_items: int
    total_stock_units: int
    total_inventory_value: float
    low_stock_items: int
    categories: int
