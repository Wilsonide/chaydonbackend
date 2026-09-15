from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.orders.repository import OrderRepository
from app.domains.production.models import (
    ProductionActivity,
    ProductionFile,
    ProductionFolder,
)
from app.domains.production.repository import ProductionRepository
from app.domains.production.schemas import (
    ProductionCreate,
    ProductionUpdate,
)
from app.domains.tasks.models import Task, TaskPriority, TaskStatus
from app.services.cloudinary_service import CloudinaryService
from app.shared.responses import build_page

upload_service = CloudinaryService()


class ProductionService:
    def __init__(self):
        self.repo = ProductionRepository()
        self.order_repo = OrderRepository()

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
        # Verify order exists
        # --------------------------------------------------------

        order = await self.order_repo.get_by_id(
            db,
            data.order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        # --------------------------------------------------------
        # Make sure order does not already have a production folder
        # --------------------------------------------------------

        existing = await self.repo.get_by_order_id(
            db,
            data.order_id,
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Production folder already exists for this order",
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

            # Flush so the folder identity and generated values
            # are available before creating related records.
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

            # ====================================================
            # RECORD PRODUCTION ACTIVITY
            # ====================================================

            activity = ProductionActivity(
                production_folder_id=folder.id,
                user_id=user_id,
                action="FOLDER_CREATED",
                description=(
                    f"Production folder {folder.folder_number} "
                    f"was created with an initial design task."
                ),
            )

            db.add(activity)

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
                detail="Production folder could not be loaded after creation",
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

        # --------------------------------------------------------
        # Update title
        # --------------------------------------------------------

        if data.title is not None and data.title != folder.title:
            changes.append(f"title changed from '{folder.title}' to '{data.title}'")

            folder.title = data.title

        # --------------------------------------------------------
        # Update requirements
        # --------------------------------------------------------

        if data.requirements is not None and data.requirements != folder.requirements:
            changes.append("customer requirements updated")

            folder.requirements = data.requirements

        # --------------------------------------------------------
        # Update status
        # --------------------------------------------------------

        if data.status is not None and data.status != folder.status:
            changes.append(
                f"status changed from {folder.status.value} to {data.status.value}"
            )

            folder.status = data.status

        # --------------------------------------------------------
        # Nothing changed
        # --------------------------------------------------------

        if not changes:
            return folder

        # --------------------------------------------------------
        # Save folder changes
        # --------------------------------------------------------

        await db.commit()
        await db.refresh(folder)

        # --------------------------------------------------------
        # Record activity
        # --------------------------------------------------------

        activity = ProductionActivity(
            production_folder_id=folder.id,
            user_id=user_id,
            action="FOLDER_UPDATED",
            description="; ".join(changes),
        )

        await self.repo.add_activity(
            db,
            activity,
        )

        # --------------------------------------------------------
        # Reload complete folder
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
        # Find production folder
        # --------------------------------------------------------

        folder = await self.repo.get_by_id(
            db,
            folder_id,
        )

        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Production folder not found",
            )

        # --------------------------------------------------------
        # Upload to Cloudinary
        # --------------------------------------------------------

        uploaded = await upload_service.upload(
            file,
            f"printflow/production/{folder.folder_number}",
        )

        # --------------------------------------------------------
        # Save file metadata
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Record activity
        # --------------------------------------------------------

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

        return production_file

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
        # Find production file
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
        # Store values before deleting DB object
        # --------------------------------------------------------

        file_name = production_file.file_name
        public_id = production_file.public_id
        resource_type = production_file.resource_type
        folder_id = production_file.production_folder_id

        # --------------------------------------------------------
        # Find production folder
        # --------------------------------------------------------

        folder = await self.repo.get_by_id(
            db,
            folder_id,
        )

        # --------------------------------------------------------
        # Delete from Cloudinary
        # --------------------------------------------------------

        if public_id:
            await upload_service.delete(
                public_id,
                resource_type,
            )

        # --------------------------------------------------------
        # Delete database record
        # --------------------------------------------------------

        await self.repo.delete_file(
            db,
            production_file,
        )

        # --------------------------------------------------------
        # Record activity
        # --------------------------------------------------------

        if folder:
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

        return {"message": "Production file deleted successfully"}
