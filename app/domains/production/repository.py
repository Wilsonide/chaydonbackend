from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.production.models import (
    ProductionActivity,
    ProductionFile,
    ProductionFolder,
)
from app.shared.search import ilike_search


class ProductionRepository:
    # ============================================================
    # CREATE PRODUCTION FOLDER
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        folder: ProductionFolder,
    ) -> ProductionFolder:
        db.add(folder)
        await db.flush()

        return folder

    # ============================================================
    # GET SINGLE PRODUCTION FOLDER
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        folder_id: str,
    ) -> ProductionFolder | None:
        result = await db.execute(
            select(ProductionFolder)
            .options(
                selectinload(ProductionFolder.files),
                selectinload(ProductionFolder.activities),
                selectinload(ProductionFolder.tasks),
            )
            .where(ProductionFolder.id == folder_id)
        )

        return result.scalar_one_or_none()

    # ============================================================
    # GET PRODUCTION FOLDER METADATA
    # ============================================================

    async def get_basic_by_id(
        self,
        db: AsyncSession,
        folder_id: str,
    ) -> ProductionFolder | None:
        result = await db.execute(
            select(ProductionFolder).where(ProductionFolder.id == folder_id)
        )

        return result.scalar_one_or_none()

    # ============================================================
    # GET PRODUCTION FOLDER BY ORDER
    # ============================================================

    async def get_by_order_id(
        self,
        db: AsyncSession,
        order_id: str,
    ) -> ProductionFolder | None:
        result = await db.execute(
            select(ProductionFolder).where(ProductionFolder.order_id == order_id)
        )

        return result.scalar_one_or_none()

    # ============================================================
    # GET ALL PRODUCTION FOLDERS
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        status=None,
    ):
        # --------------------------------------------------------
        # FILTERS
        # --------------------------------------------------------

        filters = []

        if search:
            search_filter = ilike_search(
                search,
                ProductionFolder.title,
                cast(
                    ProductionFolder.production_number,
                    String,
                ),
            )

            if search_filter is not None:
                filters.append(search_filter)

        if status:
            filters.append(ProductionFolder.status == status)

        # --------------------------------------------------------
        # TOTAL COUNT
        # --------------------------------------------------------

        count_query = select(func.count(ProductionFolder.id))

        if filters:
            count_query = count_query.where(*filters)

        total = await db.scalar(count_query)

        # --------------------------------------------------------
        # PAGINATED DATA
        # --------------------------------------------------------

        query = select(ProductionFolder).options(
            selectinload(ProductionFolder.files),
            selectinload(ProductionFolder.activities),
            selectinload(ProductionFolder.tasks),
        )

        if filters:
            query = query.where(*filters)

        query = (
            query.order_by(ProductionFolder.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        result = await db.execute(query)

        folders = list(result.scalars().all())

        return folders, total or 0

    # ============================================================
    # ADD ACTIVITY
    # ============================================================

    async def add_activity(
        self,
        db: AsyncSession,
        activity: ProductionActivity,
    ) -> ProductionActivity:
        db.add(activity)
        await db.flush()

        return activity

    # ============================================================
    # ADD PRODUCTION FILE
    # ============================================================

    async def add_file(
        self,
        db: AsyncSession,
        file: ProductionFile,
    ) -> ProductionFile:
        db.add(file)
        await db.flush()

        return file

    # ============================================================
    # GET PRODUCTION FILE
    # ============================================================

    async def get_file(
        self,
        db: AsyncSession,
        file_id: str,
    ) -> ProductionFile | None:
        result = await db.execute(
            select(ProductionFile).where(ProductionFile.id == file_id)
        )

        return result.scalar_one_or_none()

    # ============================================================
    # DELETE PRODUCTION FILE
    # ============================================================

    async def delete_file(
        self,
        db: AsyncSession,
        production_file: ProductionFile,
    ) -> None:
        await db.delete(production_file)
        await db.flush()
