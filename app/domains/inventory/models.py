import enum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
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

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    movements = relationship(
        "StockMovement",
        back_populates="item",
        cascade="all, delete-orphan",
    )


class StockMovement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stock_movements"

    item_id: Mapped[str] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
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

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recorded_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    production_folder_id: Mapped[str | None] = mapped_column(
        ForeignKey("production_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    item = relationship(
        "InventoryItem",
        back_populates="movements",
    )

    recorder = relationship("User")

    production_folder = relationship(
        "ProductionFolder",
        back_populates="inventory_movements",
    )
