from typing import ClassVar

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.orders.models import (
    Order,
    OrderStatus,
)
from app.domains.orders.repository import OrderRepository
from app.domains.production.models import (
    ProductionActivity,
    ProductionFile,
    ProductionFolder,
    ProductionStatus,
)
from app.domains.production.repository import ProductionRepository
from app.domains.production.schemas import (
    ProductionCreate,
    ProductionUpdate,
)
from app.domains.tasks.models import (
    Task,
    TaskPriority,
    TaskStatus,
)
from app.services.cloudinary_service import CloudinaryService
from app.shared.responses import build_page

upload_service = CloudinaryService()


class ProductionService:
    # ============================================================
    # PRODUCTION STATUS → ORDER STATUS
    # ============================================================

    PRODUCTION_TO_ORDER_STATUS: ClassVar[dict[ProductionStatus, OrderStatus]] = {
        ProductionStatus.CREATED: OrderStatus.RECEIVED,
        ProductionStatus.WAITING_FOR_REQUIREMENTS: OrderStatus.REVIEWING,
        ProductionStatus.READY_FOR_DESIGN: OrderStatus.READY_FOR_PRODUCTION,
        ProductionStatus.IN_DESIGN: OrderStatus.IN_PRODUCTION,
        ProductionStatus.DESIGN_REVIEW: OrderStatus.IN_PRODUCTION,
        ProductionStatus.APPROVED_FOR_PRINT: OrderStatus.IN_PRODUCTION,
        ProductionStatus.PRINTING: OrderStatus.IN_PRODUCTION,
        ProductionStatus.COMPLETED: OrderStatus.COMPLETED,
        ProductionStatus.CANCELLED: OrderStatus.CANCELLED,
    }

    def __init__(self):
        self.repo = ProductionRepository()
        self.order_repo = OrderRepository()

    # ============================================================
    # SYNCHRONIZE PRODUCTION FOLDER + ORDER
    # ============================================================
    #
    # Workflow:
    #
    # Task
    #   ↓
    # Production Folder
    #   ↓
    # Order
    #
    # This method does NOT commit.
    #
    # The caller owns the transaction.
    # ============================================================

    async def _sync_workflow_status(
        self,
        db: AsyncSession,
        folder: ProductionFolder,
        actor_id: str,
    ) -> None:
        # --------------------------------------------------------
        # LOAD ORDER
        # --------------------------------------------------------

        order = await db.get(
            Order,
            folder.order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found for production folder",
            )

        # --------------------------------------------------------
        # LOAD TASK STATUSES
        # --------------------------------------------------------
        #
        # We query the database directly instead of relying on
        # folder.tasks because the task may have just been created
        # or modified in the current transaction.
        # --------------------------------------------------------

        result = await db.execute(
            select(Task.status).where(Task.production_folder_id == folder.id)
        )

        task_statuses = list(result.scalars().all())

        # --------------------------------------------------------
        # DETERMINE TASK STATE
        # --------------------------------------------------------

        all_approved = bool(task_statuses) and all(
            task_status == TaskStatus.APPROVED for task_status in task_statuses
        )

        any_review = any(
            task_status
            in {
                TaskStatus.SUBMITTED,
                TaskStatus.REVISION_REQUIRED,
            }
            for task_status in task_statuses
        )

        any_active = any(
            task_status
            in {
                TaskStatus.ASSIGNED,
                TaskStatus.IN_PROGRESS,
            }
            for task_status in task_statuses
        )

        # --------------------------------------------------------
        # PRESERVE TERMINAL / PRINTING STATES
        # --------------------------------------------------------
        #
        # Task synchronization controls the DESIGN phase.
        #
        # It must not accidentally move a folder backwards from:
        #
        # PRINTING
        # COMPLETED
        # CANCELLED
        #
        # just because a task was updated.
        # --------------------------------------------------------

        previous_folder_status = folder.status
        previous_order_status = order.status

        if folder.status in {
            ProductionStatus.COMPLETED,
            ProductionStatus.CANCELLED,
            ProductionStatus.PRINTING,
        }:
            new_folder_status = folder.status

        elif all_approved:
            new_folder_status = ProductionStatus.APPROVED_FOR_PRINT

        elif any_review:
            new_folder_status = ProductionStatus.DESIGN_REVIEW

        elif any_active:
            new_folder_status = ProductionStatus.IN_DESIGN

        else:
            new_folder_status = ProductionStatus.READY_FOR_DESIGN

        # --------------------------------------------------------
        # UPDATE PRODUCTION FOLDER
        # --------------------------------------------------------

        folder.status = new_folder_status

        # --------------------------------------------------------
        # SYNCHRONIZE ORDER
        # --------------------------------------------------------

        new_order_status = self.PRODUCTION_TO_ORDER_STATUS.get(folder.status)

        if new_order_status is not None:
            order.status = new_order_status

        # --------------------------------------------------------
        # RECORD SYNCHRONIZATION ACTIVITY
        # --------------------------------------------------------

        if (
            previous_folder_status != folder.status
            or previous_order_status != order.status
        ):
            db.add(
                ProductionActivity(
                    production_folder_id=folder.id,
                    user_id=actor_id,
                    action="WORKFLOW_SYNCED",
                    description=(
                        "Workflow synchronized. "
                        f"Production: "
                        f"{previous_folder_status.value} → "
                        f"{folder.status.value}; "
                        f"Order: "
                        f"{previous_order_status.value} → "
                        f"{order.status.value}."
                    ),
                )
            )

    # ============================================================
    # CREATE PRODUCTION FOLDER + INITIAL TASK
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        data: ProductionCreate,
        user_id: str,
    ) -> ProductionFolder:
        # --------------------------------------------------------
        # VERIFY ORDER EXISTS
        # --------------------------------------------------------

        order_exists = await self.order_repo.exists(
            db,
            data.order_id,
        )

        if not order_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        # --------------------------------------------------------
        # MAKE SURE ORDER DOES NOT ALREADY HAVE A FOLDER
        # --------------------------------------------------------

        existing = await self.repo.get_by_order_id(
            db,
            data.order_id,
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Production folder already exists for this order"),
            )

        try:
            # ====================================================
            # CREATE PRODUCTION FOLDER
            # ====================================================

            folder = ProductionFolder(
                order_id=data.order_id,
                title=data.title,
                requirements=data.requirements,
            )

            db.add(folder)

            # ----------------------------------------------------
            # FLUSH FOLDER
            # ----------------------------------------------------
            #
            # This gives us:
            #
            # folder.id
            # folder.production_number
            # folder.created_at
            # folder.folder_number
            #
            # before creating the task/activity.
            # ----------------------------------------------------

            await db.flush()

            # ====================================================
            # CREATE INITIAL DESIGN TASK
            # ====================================================

            task = Task(
                production_folder_id=folder.id,
                assigned_by=user_id,
                assigned_to=None,
                title=data.title,
                description=data.requirements,
                priority=TaskPriority.MEDIUM,
                status=TaskStatus.UNASSIGNED,
            )

            db.add(task)

            # ----------------------------------------------------
            # FLUSH TASK
            # ----------------------------------------------------
            #
            # Important:
            #
            # The synchronization query must be able to see the
            # newly created task in the current transaction.
            # ----------------------------------------------------

            await db.flush()

            # ====================================================
            # RECORD FOLDER CREATION ACTIVITY
            # ====================================================

            db.add(
                ProductionActivity(
                    production_folder_id=folder.id,
                    user_id=user_id,
                    action="FOLDER_CREATED",
                    description=(
                        f"Production folder "
                        f"{folder.folder_number} "
                        f"was created with an initial "
                        f"design task."
                    ),
                )
            )

            # ====================================================
            # SYNCHRONIZE WORKFLOW
            # ====================================================
            #
            # Initial task:
            #
            # UNASSIGNED
            #
            # Therefore:
            #
            # Production Folder:
            # READY_FOR_DESIGN
            #
            # Order:
            # READY_FOR_PRODUCTION
            #
            # Everything remains inside the same transaction.
            # ====================================================

            await self._sync_workflow_status(
                db,
                folder,
                user_id,
            )

            # ====================================================
            # COMMIT EVERYTHING TOGETHER
            # ====================================================

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        # ========================================================
        # RETURN COMPLETE PRODUCTION FOLDER
        # ========================================================

        created_folder = await self.repo.get_by_id(
            db,
            str(folder.id),
        )

        if not created_folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=("Production folder could not be loaded after creation"),
            )

        return created_folder

    # ============================================================
    # UPDATE PRODUCTION FOLDER
    # ============================================================

    async def update(
        self,
        db: AsyncSession,
        folder_id: str,
        data: ProductionUpdate,
        user_id: str,
    ) -> ProductionFolder:
        folder = await self.repo.get_by_id(
            db,
            folder_id,
        )

        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Production folder not found",
            )

        changes: list[str] = []

        old_folder_status = folder.status

        # --------------------------------------------------------
        # UPDATE TITLE
        # --------------------------------------------------------

        if data.title is not None and data.title != folder.title:
            changes.append(f"title changed from '{folder.title}' to '{data.title}'")

            folder.title = data.title

        # --------------------------------------------------------
        # UPDATE REQUIREMENTS
        # --------------------------------------------------------

        if data.requirements is not None and data.requirements != folder.requirements:
            changes.append("customer requirements updated")

            folder.requirements = data.requirements

        # --------------------------------------------------------
        # UPDATE STATUS
        # --------------------------------------------------------

        status_changed = data.status is not None and data.status != folder.status

        if status_changed:
            changes.append(
                f"status changed from {folder.status.value} to {data.status.value}"
            )

            folder.status = data.status

        # --------------------------------------------------------
        # NOTHING CHANGED
        # --------------------------------------------------------

        if not changes:
            return folder

        try:
            # ----------------------------------------------------
            # RECORD PRODUCTION ACTIVITY
            # ----------------------------------------------------

            db.add(
                ProductionActivity(
                    production_folder_id=folder.id,
                    user_id=user_id,
                    action="FOLDER_UPDATED",
                    description="; ".join(changes),
                )
            )

            # ----------------------------------------------------
            # SYNCHRONIZE ORDER STATUS
            # ----------------------------------------------------

            if status_changed:
                await self._sync_order_status(
                    db,
                    folder,
                )

                order_status = self.PRODUCTION_TO_ORDER_STATUS.get(folder.status)

                if order_status is not None:
                    db.add(
                        ProductionActivity(
                            production_folder_id=folder.id,
                            user_id=user_id,
                            action="ORDER_STATUS_SYNCED",
                            description=(
                                f"Order status synchronized "
                                f"to {order_status.value} "
                                f"because production folder "
                                f"status changed from "
                                f"{old_folder_status.value} "
                                f"to {folder.status.value}."
                            ),
                        )
                    )

            # ----------------------------------------------------
            # COMMIT EVERYTHING TOGETHER
            # ----------------------------------------------------

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        # --------------------------------------------------------
        # RELOAD COMPLETE PRODUCTION FOLDER
        # --------------------------------------------------------

        updated_folder = await self.repo.get_by_id(
            db,
            folder_id,
        )

        if not updated_folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Production folder not found",
            )

        return updated_folder

    # ============================================================
    # GET ALL PRODUCTION FOLDERS
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        pagination,
        search,
        status,
    ):
        items, total = await self.repo.get_all(
            db,
            page=pagination.page,
            limit=pagination.limit,
            search=search,
            status=status,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    # ============================================================
    # GET SINGLE PRODUCTION FOLDER
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        folder_id: str,
    ) -> ProductionFolder:
        folder = await self.repo.get_by_id(
            db,
            folder_id,
        )

        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Production folder not found",
            )

        return folder

    # ============================================================
    # UPLOAD PRODUCTION FILE
    # ============================================================

    async def upload_file(
        self,
        db: AsyncSession,
        folder_id: str,
        file: UploadFile,
        user_id: str,
    ):
        # --------------------------------------------------------
        # LOAD FOLDER
        # --------------------------------------------------------

        folder = await self.repo.get_basic_by_id(
            db,
            folder_id,
        )

        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Production folder not found",
            )

        uploaded = None

        try:
            # ----------------------------------------------------
            # UPLOAD TO CLOUDINARY
            # ----------------------------------------------------

            uploaded = await upload_service.upload(
                file,
                f"printflow/production/{folder.folder_number}",
            )

            # ----------------------------------------------------
            # SAVE FILE METADATA
            # ----------------------------------------------------

            production_file = ProductionFile(
                production_folder_id=folder.id,
                file_name=uploaded["file_name"],
                file_url=uploaded["url"],
                public_id=uploaded["public_id"],
                file_type=uploaded["file_type"],
                resource_type=uploaded["resource_type"],
                uploaded_by=user_id,
            )

            await self.repo.add_file(
                db,
                production_file,
            )

            # ----------------------------------------------------
            # RECORD ACTIVITY
            # ----------------------------------------------------

            activity = ProductionActivity(
                production_folder_id=folder.id,
                user_id=user_id,
                action="FILE_UPLOADED",
                description=(
                    f"{uploaded['file_name']} was uploaded "
                    f"to production folder "
                    f"{folder.folder_number}."
                ),
            )

            await self.repo.add_activity(
                db,
                activity,
            )

            # ----------------------------------------------------
            # COMMIT FILE + ACTIVITY TOGETHER
            # ----------------------------------------------------

            await db.commit()

            # ----------------------------------------------------
            # RETURN FILE
            # ----------------------------------------------------

            return production_file

        except Exception:
            await db.rollback()

            # ----------------------------------------------------
            # CLEAN UP CLOUDINARY IF DB OPERATION FAILED
            # ----------------------------------------------------

            if uploaded and uploaded.get("public_id"):
                try:
                    await upload_service.delete(
                        uploaded["public_id"],
                        uploaded.get("resource_type"),
                    )
                except Exception:
                    pass

            raise

    # ============================================================
    # DELETE PRODUCTION FILE
    # ============================================================

    async def delete_file(
        self,
        db: AsyncSession,
        file_id: str,
        user_id: str,
    ):
        # --------------------------------------------------------
        # FIND PRODUCTION FILE
        # --------------------------------------------------------

        production_file = await self.repo.get_file(
            db,
            file_id,
        )

        if not production_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Production file not found",
            )

        # --------------------------------------------------------
        # STORE VALUES BEFORE DELETE
        # --------------------------------------------------------

        file_name = production_file.file_name
        public_id = production_file.public_id
        resource_type = production_file.resource_type
        folder_id = production_file.production_folder_id

        # --------------------------------------------------------
        # LOAD FOLDER
        # --------------------------------------------------------

        folder = await self.repo.get_basic_by_id(
            db,
            folder_id,
        )

        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Production folder not found",
            )

        try:
            # ----------------------------------------------------
            # DELETE FROM CLOUDINARY
            # ----------------------------------------------------

            if public_id:
                await upload_service.delete(
                    public_id,
                    resource_type,
                )

            # ----------------------------------------------------
            # DELETE DATABASE RECORD
            # ----------------------------------------------------

            await self.repo.delete_file(
                db,
                production_file,
            )

            # ----------------------------------------------------
            # RECORD ACTIVITY
            # ----------------------------------------------------

            activity = ProductionActivity(
                production_folder_id=folder.id,
                user_id=user_id,
                action="FILE_DELETED",
                description=(
                    f"{file_name} was deleted "
                    f"from production folder "
                    f"{folder.folder_number}."
                ),
            )

            await self.repo.add_activity(
                db,
                activity,
            )

            # ----------------------------------------------------
            # COMMIT DELETE + ACTIVITY
            # ----------------------------------------------------

            await db.commit()
            return {"message": ("Production file deleted successfully")}

        except Exception:
            await db.rollback()
            raise

    # ============================================================
    # SYNCHRONIZE ORDER STATUS
    # ============================================================

    async def _sync_order_status(
        self,
        db: AsyncSession,
        folder: ProductionFolder,
    ) -> None:
        # --------------------------------------------------------
        # LOAD ORDER
        # --------------------------------------------------------

        order = await db.get(
            Order,
            folder.order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=("Order not found for production folder"),
            )

        # --------------------------------------------------------
        # DETERMINE ORDER STATUS
        # --------------------------------------------------------

        new_order_status = self.PRODUCTION_TO_ORDER_STATUS.get(folder.status)

        if new_order_status is not None:
            order.status = new_order_status
