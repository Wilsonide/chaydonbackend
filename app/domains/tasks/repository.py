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
    @staticmethod
    def _task_load_options():
        return (
            selectinload(Task.production_folder),
            selectinload(Task.assigned_designer),
        )

    @staticmethod
    def _comment_load_options():
        return (selectinload(TaskComment.user),)

    @staticmethod
    def _build_task_filters(
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ):
        filters = []

        if search:
            search_filter = ilike_search(
                search,
                Task.title,
                Task.description,
            )

            if search_filter is not None:
                filters.append(search_filter)

        if status:
            filters.append(Task.status == status)

        if priority:
            filters.append(Task.priority == priority)

        return filters

    @staticmethod
    def _apply_task_filters(
        query,
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ):
        filters = TaskRepository._build_task_filters(
            search=search,
            status=status,
            priority=priority,
        )

        if filters:
            query = query.where(*filters)

        return query

    async def create(
        self,
        db: AsyncSession,
        task: Task,
    ) -> Task:
        """
        Existing create behavior preserved for callers that expect
        the repository to commit immediately.
        """
        db.add(task)
        await db.commit()

        return await self.get_by_id(
            db,
            str(task.id),
        )

    async def create_pending(
        self,
        db: AsyncSession,
        task: Task,
    ) -> Task:
        """
        Adds the task and flushes it without committing.

        Used when the service needs to save related records
        in the same transaction.
        """
        db.add(task)
        await db.flush()

        return task

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
            .where(Task.id == task_id)
        )

        row = result.one_or_none()

        if not row:
            return None

        task, designer = row

        task.assigned_designer = designer

        return task

    async def get_basic_by_id(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> Task | None:
        """
        Loads only the Task itself.

        Used by service operations that don't need
        production folder or assigned designer relationships.
        """
        result = await db.execute(select(Task).where(Task.id == task_id))

        return result.scalar_one_or_none()

    async def exists(
        self,
        db: AsyncSession,
        task_id: str,
    ) -> bool:
        result = await db.execute(select(Task.id).where(Task.id == task_id))

        return result.scalar_one_or_none() is not None

    async def get_all(
        self,
        db: AsyncSession,
        *,
        page: int,
        limit: int,
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ):
        filters = self._build_task_filters(
            search=search,
            status=status,
            priority=priority,
        )

        count_query = select(func.count(Task.id))

        if filters:
            count_query = count_query.where(*filters)

        total = await db.scalar(count_query)

        query = select(Task).options(*self._task_load_options())

        if filters:
            query = query.where(*filters)

        query = (
            query.order_by(Task.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        result = await db.execute(query)

        tasks = list(result.scalars().all())

        return tasks, total or 0

    async def get_folder_tasks(
        self,
        db: AsyncSession,
        *,
        folder_id: str,
        page: int,
        limit: int,
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ):
        filters = [
            Task.production_folder_id == folder_id,
            *self._build_task_filters(
                search=search,
                status=status,
                priority=priority,
            ),
        ]

        count_query = select(func.count(Task.id)).where(*filters)

        total = await db.scalar(count_query)

        query = (
            select(Task)
            .options(*self._task_load_options())
            .where(*filters)
            .order_by(Task.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        result = await db.execute(query)

        tasks = list(result.scalars().all())

        return tasks, total or 0

    async def get_designer_tasks(
        self,
        db: AsyncSession,
        *,
        designer_id: str,
        page: int,
        limit: int,
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
    ):
        filters = [
            Task.assigned_to == designer_id,
            *self._build_task_filters(
                search=search,
                status=status,
                priority=priority,
            ),
        ]

        count_query = select(func.count(Task.id)).where(*filters)

        total = await db.scalar(count_query)

        query = (
            select(Task)
            .options(*self._task_load_options())
            .where(*filters)
            .order_by(Task.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        result = await db.execute(query)

        tasks = list(result.scalars().all())

        return tasks, total or 0

    async def get_folder_task_statuses(
        self,
        db: AsyncSession,
        folder_id: str,
    ):
        """
        Returns only task statuses for a production folder.

        This avoids loading complete Task objects when reviewing
        whether all tasks have been approved.
        """
        result = await db.execute(
            select(Task.status).where(Task.production_folder_id == folder_id)
        )

        return list(result.scalars().all())

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

    async def delete(
        self,
        db: AsyncSession,
        task: Task,
    ):
        await db.delete(task)
        await db.commit()

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
            .where(TaskComment.id == comment.id)
        )

        row = result.one_or_none()

        if not row:
            return comment

        saved_comment, user = row

        saved_comment.user = user

        return saved_comment

    async def get_comments(
        self,
        db: AsyncSession,
        task_id: str,
    ):
        result = await db.execute(
            select(TaskComment)
            .options(*self._comment_load_options())
            .where(TaskComment.task_id == task_id)
            .order_by(TaskComment.created_at.asc())
        )

        return list(result.scalars().all())

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
            .where(TaskComment.id == comment_id)
        )

        row = result.one_or_none()

        if not row:
            return None

        comment, user = row

        comment.user = user

        return comment

    async def get_attachment_comments(
        self,
        db: AsyncSession,
        task_id: str,
    ):
        """
        Loads only comments that actually have attachments.

        No User relationship is loaded because delete_task()
        only needs the Cloudinary attachment information.
        """
        result = await db.execute(
            select(TaskComment).where(
                TaskComment.task_id == task_id,
                TaskComment.attachment_public_id.is_not(None),
            )
        )

        return list(result.scalars().all())

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

        if not saved_comment:
            raise RuntimeError("Comment could not be loaded after saving")

        return saved_comment

    async def delete_comment(
        self,
        db: AsyncSession,
        comment: TaskComment,
    ):
        await db.delete(comment)
        await db.commit()
