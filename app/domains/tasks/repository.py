from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.tasks.models import (
    Task,
    TaskComment,
    TaskPriority,
    TaskStatus,
)
from app.domains.users.models import User
from app.shared.search import ilike_search


class TaskRepository:
    # ============================================================
    # TASK LOAD OPTIONS
    # ============================================================

    @staticmethod
    def _task_load_options():
        return (selectinload(Task.production_folder),)

    # ============================================================
    # COMMENT LOAD OPTIONS
    # ============================================================

    @staticmethod
    def _comment_load_options():
        return (selectinload(TaskComment.user),)

    # ============================================================
    # TASK FILTERS
    # ============================================================

    @staticmethod
    def _apply_task_filters(
        query,
        search: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ):
        if search:
            search_filter = ilike_search(
                search,
                Task.title,
                Task.description,
            )

            if search_filter is not None:
                query = query.where(search_filter)

        if status is not None:
            query = query.where(Task.status == status)

        if priority is not None:
            query = query.where(Task.priority == priority)

        return query

    # ============================================================
    # CREATE TASK
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        task: Task,
    ) -> Task:
        db.add(task)

        await db.commit()

        return await self.get_by_id(
            db,
            str(task.id),
        )

    # ============================================================
    # GET SINGLE TASK
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> Task | None:
        result = await db.execute(
            select(Task, User)
            .outerjoin(
                User,
                Task.assigned_to == User.id,
            )
            .options(
                selectinload(Task.production_folder),
            )
            .where(
                Task.id == task_id,
            )
        )

        row = result.one_or_none()

        if row is None:
            return None

        task, designer = row

        # Explicitly attach the assigned designer.
        task.assigned_designer = designer

        return task

    # ============================================================
    # GET ALL TASKS
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ):
        query = select(Task)

        query = self._apply_task_filters(
            query,
            search=search,
            status=status,
            priority=priority,
        )

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.options(
                *self._task_load_options(),
                selectinload(Task.assigned_designer),
            )
            .order_by(Task.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        tasks = list(result.scalars().all())

        return tasks, total or 0

    # ============================================================
    # GET TASKS FOR PRODUCTION FOLDER
    # ============================================================

    async def get_folder_tasks(
        self,
        db: AsyncSession,
        folder_id: str,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
    ):
        query = select(Task).where(Task.production_folder_id == folder_id)

        if search:
            search_filter = ilike_search(
                search,
                Task.title,
                Task.description,
            )

            if search_filter is not None:
                query = query.where(search_filter)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.options(
                *self._task_load_options(),
                selectinload(Task.assigned_designer),
            )
            .order_by(Task.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        tasks = list(result.scalars().all())

        return tasks, total or 0

    # ============================================================
    # GET TASKS FOR DESIGNER
    # ============================================================

    async def get_designer_tasks(
        self,
        db: AsyncSession,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
    ):
        query = select(Task).where(Task.assigned_to == user_id)

        if search:
            search_filter = ilike_search(
                search,
                Task.title,
                Task.description,
            )

            if search_filter is not None:
                query = query.where(search_filter)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.options(
                *self._task_load_options(),
                selectinload(Task.assigned_designer),
            )
            .order_by(Task.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        tasks = list(result.scalars().all())

        return tasks, total or 0

    # ============================================================
    # SAVE TASK
    # ============================================================

    async def save(
        self,
        db: AsyncSession,
        task: Task,
    ) -> Task:
        await db.commit()

        return await self.get_by_id(
            db,
            str(task.id),
        )

    # ============================================================
    # DELETE TASK
    # ============================================================

    async def delete(
        self,
        db: AsyncSession,
        task: Task,
    ):
        await db.delete(task)

        await db.commit()

    # ============================================================
    # ADD COMMENT
    # ============================================================

    async def add_comment(
        self,
        db: AsyncSession,
        comment: TaskComment,
    ) -> TaskComment:
        db.add(comment)

        await db.commit()

        result = await db.execute(
            select(TaskComment, User)
            .join(
                User,
                TaskComment.user_id == User.id,
            )
            .where(
                TaskComment.id == comment.id,
            )
        )

        row = result.one_or_none()

        if row is None:
            raise RuntimeError("Comment was created but its user could not be found.")

        saved_comment, user = row

        saved_comment.user = user

        return saved_comment

    # ============================================================
    # GET COMMENTS
    # ============================================================

    async def get_comments(
        self,
        db: AsyncSession,
        task_id: str,
    ):
        result = await db.execute(
            select(TaskComment)
            .options(
                *self._comment_load_options(),
            )
            .where(
                TaskComment.task_id == task_id,
            )
            .order_by(TaskComment.created_at.asc())
        )

        return list(result.scalars().all())

    # ============================================================
    # GET COMMENT BY ID
    # ============================================================

    async def get_comment_by_id(
        self,
        db: AsyncSession,
        comment_id: str,
    ) -> TaskComment | None:
        result = await db.execute(
            select(TaskComment, User)
            .outerjoin(
                User,
                TaskComment.user_id == User.id,
            )
            .where(
                TaskComment.id == comment_id,
            )
        )

        row = result.one_or_none()

        if row is None:
            return None

        comment, user = row

        if user is not None:
            comment.user = user

        return comment

    # ============================================================
    # SAVE COMMENT
    # ============================================================

    async def save_comment(
        self,
        db: AsyncSession,
        comment: TaskComment,
    ) -> TaskComment:
        await db.commit()

        saved_comment = await self.get_comment_by_id(
            db,
            str(comment.id),
        )

        if saved_comment is None:
            raise RuntimeError("Comment could not be reloaded after saving.")

        return saved_comment

    # ============================================================
    # DELETE COMMENT
    # ============================================================

    async def delete_comment(
        self,
        db: AsyncSession,
        comment: TaskComment,
    ):
        await db.delete(comment)

        await db.commit()
