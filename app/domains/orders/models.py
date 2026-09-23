import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

# ============================================================
# ORDER TYPE
# ============================================================


class OrderType(str, enum.Enum):
    """
    Determines which production workflow an order follows.

    DESIGN:
        Order requires graphic/design work before printing.

    PRINT:
        Order is print-only and bypasses the designer/task workflow.
    """

    DESIGN = "DESIGN"
    PRINT = "PRINT"


# ============================================================
# ORDER STATUS
# ============================================================


class OrderStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    REVIEWING = "REVIEWING"
    READY_FOR_PRODUCTION = "READY_FOR_PRODUCTION"
    IN_PRODUCTION = "IN_PRODUCTION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# ============================================================
# ORDER
# ============================================================


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    # --------------------------------------------------------
    # CUSTOMER
    # --------------------------------------------------------

    customer_id: Mapped[str] = mapped_column(
        ForeignKey(
            "customers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # ORDER TYPE
    # --------------------------------------------------------

    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType),
        default=OrderType.DESIGN,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # ORDER INFORMATION
    # --------------------------------------------------------

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # --------------------------------------------------------
    # ORDER STATUS
    # --------------------------------------------------------

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.RECEIVED,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    # --------------------------------------------------------
    # FINANCIAL INFORMATION
    # --------------------------------------------------------

    total_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    # --------------------------------------------------------
    # DUE DATE
    # --------------------------------------------------------

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    customer = relationship(
        "Customer",
        back_populates="orders",
    )

    files = relationship(
        "OrderFile",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    production_folder = relationship(
        "ProductionFolder",
        back_populates="order",
        uselist=False,
    )

    payments = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    invoice = relationship(
        "Invoice",
        back_populates="order",
        uselist=False,
    )
    material_requirements = relationship(
        "OrderMaterialRequirement",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    inventory_movements = relationship(
        "StockMovement",
        back_populates="order",
    )


# ============================================================
# ORDER FILE
# ============================================================


class OrderFile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order_files"

    # --------------------------------------------------------
    # ORDER
    # --------------------------------------------------------

    order_id: Mapped[str] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # FILE INFORMATION
    # --------------------------------------------------------

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    public_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="image",
    )

    # --------------------------------------------------------
    # UPLOADER
    # --------------------------------------------------------

    uploaded_by: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    order = relationship(
        "Order",
        back_populates="files",
    )

    uploader = relationship(
        "User",
    )
