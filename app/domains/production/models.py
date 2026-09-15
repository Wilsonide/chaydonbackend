import enum

import cloudinary.utils
from sqlalchemy import Enum, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ProductionStatus(str, enum.Enum):
    CREATED = "CREATED"
    WAITING_FOR_REQUIREMENTS = "WAITING_FOR_REQUIREMENTS"
    READY_FOR_DESIGN = "READY_FOR_DESIGN"
    IN_DESIGN = "IN_DESIGN"
    DESIGN_REVIEW = "DESIGN_REVIEW"
    APPROVED_FOR_PRINT = "APPROVED_FOR_PRINT"
    PRINTING = "PRINTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProductionFolder(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "production_folders"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    production_number: Mapped[int] = mapped_column(
        Integer,
        Identity(),
        unique=True,
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    requirements: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[ProductionStatus] = mapped_column(
        Enum(ProductionStatus),
        default=ProductionStatus.CREATED,
        nullable=False,
        index=True,
    )

    order = relationship(
        "Order",
        back_populates="production_folder",
    )

    files = relationship(
        "ProductionFile",
        back_populates="production_folder",
        cascade="all, delete-orphan",
    )

    activities = relationship(
        "ProductionActivity",
        back_populates="production_folder",
        cascade="all, delete-orphan",
        order_by="ProductionActivity.created_at.desc()",
    )
    tasks = relationship(
        "Task",
        back_populates="production_folder",
        cascade="all, delete-orphan",
    )
    inventory_movements = relationship(
        "StockMovement",
        back_populates="production_folder",
    )

    @property
    def folder_number(self) -> str:
        return f"PF-{self.created_at.year}-{self.production_number:04d}"


class ProductionFile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "production_files"

    production_folder_id: Mapped[str] = mapped_column(
        ForeignKey("production_folders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    public_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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

    uploaded_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    production_folder = relationship(
        "ProductionFolder",
        back_populates="files",
    )


class ProductionActivity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "production_activities"

    production_folder_id: Mapped[str] = mapped_column(
        ForeignKey(
            "production_folders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    production_folder = relationship(
        "ProductionFolder",
        back_populates="activities",
    )
