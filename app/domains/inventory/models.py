import enum
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import (
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class MovementType(str, enum.Enum):
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    ADJUSTMENT = "ADJUSTMENT"


class InventoryItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "inventory_items"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    minimum_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    unit_selling_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    @hybrid_property
    def total_selling_price(self) -> Decimal:
        return Decimal(self.quantity) * Decimal(str(self.unit_selling_price or 0))

    movements = relationship(
        "StockMovement",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    material_requirements = relationship(
        "OrderMaterialRequirement",
        back_populates="inventory_item",
    )


class StockMovement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stock_movements"

    MONEY = Decimal("0.01")

    item_id: Mapped[str] = mapped_column(
        ForeignKey(
            "inventory_items.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType),
        nullable=False,
    )

    # Original unit selling price before discount.
    unit_selling_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # Overall fixed monetary discount allocated to this movement.
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )

    # Original dimension input, e.g. "3x2x2, 4x5x3".
    dimension_input: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recorded_by: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    production_folder_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "production_folders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    order_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    @hybrid_property
    def gross_total_selling_price(self) -> Decimal:
        return (
            Decimal(self.quantity) * Decimal(str(self.unit_selling_price or 0))
        ).quantize(self.MONEY, rounding=ROUND_HALF_UP)

    @hybrid_property
    def total_selling_price(self) -> Decimal:
        return (
            self.gross_total_selling_price - Decimal(str(self.discount_amount or 0))
        ).quantize(self.MONEY, rounding=ROUND_HALF_UP)

    item = relationship(
        "InventoryItem",
        back_populates="movements",
    )

    recorder = relationship("User")

    production_folder = relationship(
        "ProductionFolder",
        back_populates="inventory_movements",
    )

    order = relationship(
        "Order",
        back_populates="inventory_movements",
    )


class OrderMaterialRequirement(UUIDMixin, TimestampMixin, Base):
    """
    Defines the inventory materials required by a print order.

    required_quantity:
        Total quantity required for the order.

    consumed_quantity:
        Quantity already deducted from inventory.

    remaining_quantity:
        Quantity still required.

    discount_amount:
        One fixed monetary discount applied to the entire
        required material quantity.
    """

    __tablename__ = "order_material_requirements"

    MONEY = Decimal("0.01")

    order_id: Mapped[str] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    inventory_item_id: Mapped[str] = mapped_column(
        ForeignKey(
            "inventory_items.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    required_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    consumed_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Original unit selling price before discount.
    unit_selling_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # One fixed monetary discount for the entire requirement.
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        server_default="0.00",
        nullable=False,
    )

    dimension_input: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    @hybrid_property
    def remaining_quantity(self) -> int:
        return max(
            self.required_quantity - self.consumed_quantity,
            0,
        )

    @hybrid_property
    def gross_required_cost(self) -> Decimal:
        return (
            Decimal(self.required_quantity) * Decimal(str(self.unit_selling_price or 0))
        ).quantize(self.MONEY, rounding=ROUND_HALF_UP)

    @hybrid_property
    def required_cost(self) -> Decimal:
        return (
            self.gross_required_cost - Decimal(str(self.discount_amount or 0))
        ).quantize(self.MONEY, rounding=ROUND_HALF_UP)

    @property
    def consumed_discount(self) -> Decimal:
        """
        Allocate the overall discount proportionally to.

        the quantity already consumed.

        When all quantity is consumed, allocate the full
        discount to avoid rounding discrepancies.
        """
        if self.required_quantity <= 0:
            return Decimal("0.00")

        consumed = min(
            max(self.consumed_quantity, 0),
            self.required_quantity,
        )

        if consumed == 0:
            return Decimal("0.00")

        if consumed == self.required_quantity:
            return Decimal(str(self.discount_amount or 0)).quantize(
                self.MONEY,
                rounding=ROUND_HALF_UP,
            )

        return (
            Decimal(str(self.discount_amount or 0))
            * Decimal(consumed)
            / Decimal(self.required_quantity)
        ).quantize(self.MONEY, rounding=ROUND_HALF_UP)

    @property
    def consumed_cost(self) -> Decimal:
        consumed = min(
            max(self.consumed_quantity, 0),
            self.required_quantity,
        )

        gross_cost = Decimal(consumed) * Decimal(str(self.unit_selling_price or 0))

        return (gross_cost - self.consumed_discount).quantize(
            self.MONEY,
            rounding=ROUND_HALF_UP,
        )

    @property
    def remaining_cost(self) -> Decimal:
        return (self.required_cost - self.consumed_cost).quantize(
            self.MONEY, rounding=ROUND_HALF_UP
        )

    @property
    def remaining_discount(self) -> Decimal:
        return (
            Decimal(str(self.discount_amount or 0)) - self.consumed_discount
        ).quantize(self.MONEY, rounding=ROUND_HALF_UP)

    order = relationship(
        "Order",
        back_populates="material_requirements",
    )

    inventory_item = relationship(
        "InventoryItem",
        back_populates="material_requirements",
    )
