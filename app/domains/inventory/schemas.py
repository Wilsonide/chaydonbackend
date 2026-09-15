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
    description: str | None = None


class InventoryUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit: str | None = None
    minimum_quantity: int | None = None
    description: str | None = None


class StockMovementCreate(BaseModel):
    quantity: int
    movement_type: MovementType
    reason: str | None = None
    production_folder_id: UUID | None = None


class ManualAdjustment(BaseModel):
    new_quantity: int
    reason: str


class ProductionConsumption(BaseModel):
    item_id: UUID
    quantity: int
    reason: str | None = "Consumed during production"


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    unit: str
    quantity: int
    minimum_quantity: int
    description: str | None
    created_at: datetime
    updated_at: datetime


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    quantity: int
    movement_type: MovementType
    reason: str | None
    recorded_by: UUID
    production_folder_id: UUID | None
    created_at: datetime


class LowStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    unit: str
    quantity: int
    minimum_quantity: int


class InventoryDashboardResponse(BaseModel):
    total_items: int
    total_stock_units: int
    low_stock_items: int
    categories: int
