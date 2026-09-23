import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskStatus(str, enum.Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    APPROVED = "APPROVED"


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    production_folder_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "production_folders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    assigned_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    designer_charge: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority),
        default=TaskPriority.MEDIUM,
        nullable=False,
    )

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        default=TaskStatus.UNASSIGNED,
        nullable=False,
        index=True,
    )

    deadline: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------------
    # PRODUCTION FOLDER
    # ------------------------------------------------------------

    production_folder = relationship(
        "ProductionFolder",
        back_populates="tasks",
        lazy="selectin",
    )

    # ------------------------------------------------------------
    # ASSIGNED DESIGNER
    # ------------------------------------------------------------

    assigned_designer = relationship(
        "User",
        foreign_keys=[assigned_to],
        lazy="selectin",
    )

    # ------------------------------------------------------------
    # TASK COMMENTS
    # ------------------------------------------------------------

    comments = relationship(
        "TaskComment",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskComment.created_at.asc()",
    )


class TaskComment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "task_comments"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    attachment_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    attachment_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    attachment_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    attachment_public_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_revision_request: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_approval: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # ------------------------------------------------------------
    # TASK
    # ------------------------------------------------------------

    task = relationship(
        "Task",
        back_populates="comments",
    )

    # ------------------------------------------------------------
    # COMMENT AUTHOR
    # ------------------------------------------------------------

    user = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
