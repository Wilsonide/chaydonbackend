from fastapi import HTTPException

from app.domains.production.models import (
    ProductionActivity,
    ProductionStatus,
)
from app.domains.production.repository import (
    ProductionRepository,
)
from app.domains.tasks.models import (
    Task,
    TaskComment,
    TaskStatus,
)
from app.domains.tasks.repository import (
    TaskRepository,
)
from app.domains.users.models import UserRole
from app.domains.users.repository import UserRepository
from app.services.cloudinary_service import (
    CloudinaryService,
)
from app.shared.responses import build_page

upload_service = CloudinaryService()


class TaskService:
    def __init__(self):
        self.repo = TaskRepository()
        self.production_repo = ProductionRepository()
        self.user_repo = UserRepository()

    async def create(
        self,
        db,
        data,
        assigned_by,
    ):
        production_folder = await self.production_repo.get_by_id(
            db,
            data.production_folder_id,
        )

        if not production_folder:
            raise HTTPException(
                status_code=404,
                detail="Production folder not found",
            )

        task = Task(
            production_folder_id=data.production_folder_id,
            assigned_by=assigned_by,
            assigned_to=None,
            title=data.title,
            description=data.description,
            priority=data.priority,
            status=TaskStatus.UNASSIGNED,
            deadline=data.deadline,
        )

        try:
            # Flush instead of committing here so the task,
            # activity, and any other related records use one transaction.
            task = await self.repo.create_pending(
                db,
                task,
            )

            activity = ProductionActivity(
                production_folder_id=production_folder.id,
                user_id=assigned_by,
                action="TASK_CREATED",
                description=(
                    f"Task '{task.title}' was created "
                    f"for production folder "
                    f"{production_folder.folder_number}."
                ),
            )

            db.add(activity)

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        created_task = await self.repo.get_by_id(
            db,
            str(task.id),
        )

        if not created_task:
            raise HTTPException(
                status_code=404,
                detail="Task could not be loaded after creation",
            )

        return created_task

    async def get_all(
        self,
        db,
        page,
        limit,
        search,
        status,
        priority,
    ):
        items, total = await self.repo.get_all(
            db,
            page=page,
            limit=limit,
            search=search,
            status=status,
            priority=priority,
        )

        return build_page(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    async def get_by_id(
        self,
        db,
        task_id,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return task

    async def update(
        self,
        db,
        task_id,
        data,
        user_id,
    ):
        # No related objects are needed for an update.
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        changes = []

        update_data = data.model_dump(
            exclude_unset=True,
        )

        if "title" in update_data and update_data["title"] != task.title:
            changes.append(
                f"title changed from '{task.title}' to '{update_data['title']}'"
            )
            task.title = update_data["title"]

        if (
            "description" in update_data
            and update_data["description"] != task.description
        ):
            changes.append("description updated")
            task.description = update_data["description"]

        if "priority" in update_data and update_data["priority"] != task.priority:
            changes.append(
                f"priority changed from "
                f"{task.priority.value} "
                f"to {update_data['priority'].value}"
            )
            task.priority = update_data["priority"]

        if "deadline" in update_data and update_data["deadline"] != task.deadline:
            changes.append("deadline updated")
            task.deadline = update_data["deadline"]

        if not changes:
            return task

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=user_id,
            action="TASK_UPDATED",
            description="; ".join(changes),
        )

        db.add(activity)

        try:
            # One commit for both task changes and activity.
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        updated_task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not updated_task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return updated_task

    async def assign_task(
        self,
        db,
        task_id,
        designer_id,
        assigned_by,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        designer = await self.user_repo.get_by_id(
            db,
            designer_id,
        )

        if not designer:
            raise HTTPException(
                status_code=404,
                detail="Designer not found",
            )

        if designer.role != UserRole.GRAPHIC_DESIGNER:
            raise HTTPException(
                status_code=400,
                detail="Task can only be assigned to a graphic designer",
            )

        if not designer.is_active:
            raise HTTPException(
                status_code=400,
                detail="Designer account is inactive",
            )

        if task.assigned_to == designer.id:
            raise HTTPException(
                status_code=400,
                detail="Task is already assigned to this designer",
            )

        if task.status == TaskStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="Approved task cannot be reassigned",
            )

        previous_designer = task.assigned_designer

        task.assigned_to = designer.id

        if task.status in {
            TaskStatus.UNASSIGNED,
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.SUBMITTED,
            TaskStatus.REVISION_REQUIRED,
        }:
            task.status = TaskStatus.ASSIGNED

        if previous_designer:
            action = "TASK_REASSIGNED"
            description = (
                f"Task '{task.title}' was reassigned "
                f"from {previous_designer.username} "
                f"to {designer.username}."
            )
        else:
            action = "TASK_ASSIGNED"
            description = f"Task '{task.title}' was assigned to {designer.username}."

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=assigned_by,
            action=action,
            description=description,
        )

        db.add(activity)

        try:
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        updated_task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not updated_task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return updated_task

    async def delete(
        self,
        db,
        task_id,
    ):
        # We only need the Task itself here.
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        # Don't load comment users because deletion only needs
        # the attachment information.
        comments = await self.repo.get_attachment_comments(
            db,
            task_id,
        )

        for comment in comments:
            if comment.attachment_public_id:
                await upload_service.delete(
                    comment.attachment_public_id,
                    comment.attachment_type,
                )

        await self.repo.delete(
            db,
            task,
        )

        return {
            "message": "Task deleted successfully",
            "task_id": task_id,
        }

    async def get_folder_tasks(
        self,
        db,
        folder_id,
        pagination,
        search,
        status=None,
        priority=None,
    ):
        items, total = await self.repo.get_folder_tasks(
            db,
            folder_id=folder_id,
            page=pagination.page,
            limit=pagination.limit,
            search=search,
            status=status,
            priority=priority,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def get_designer_tasks(
        self,
        db,
        designer_id,
        pagination,
        search,
        status=None,
        priority=None,
    ):
        items, total = await self.repo.get_designer_tasks(
            db,
            designer_id=designer_id,
            page=pagination.page,
            limit=pagination.limit,
            search=search,
            status=status,
            priority=priority,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def designer_update_status(
        self,
        db,
        task_id,
        user_id,
        new_status,
    ):
        # No production_folder or assigned_designer relationship
        # is required for this operation.
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        if not task.assigned_to:
            raise HTTPException(
                status_code=400,
                detail="Task has not been assigned to a designer",
            )

        if task.assigned_to != user_id:
            raise HTTPException(
                status_code=403,
                detail="You are not assigned to this task",
            )

        allowed_transitions = {
            TaskStatus.ASSIGNED: {
                TaskStatus.IN_PROGRESS,
            },
            TaskStatus.IN_PROGRESS: {
                TaskStatus.SUBMITTED,
            },
            TaskStatus.REVISION_REQUIRED: {
                TaskStatus.IN_PROGRESS,
            },
        }

        allowed = allowed_transitions.get(
            task.status,
            set(),
        )

        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot change task status "
                    f"from {task.status.value} "
                    f"to {new_status.value}"
                ),
            )

        previous_status = task.status

        task.status = new_status

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=user_id,
            action="TASK_STATUS_UPDATED",
            description=(
                f"Task '{task.title}' status changed "
                f"from {previous_status.value} "
                f"to {new_status.value}."
            ),
        )

        db.add(activity)

        try:
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        updated_task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not updated_task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return updated_task

    async def add_comment(
        self,
        db,
        task_id,
        user_id,
        data,
    ):
        task_exists = await self.repo.exists(
            db,
            task_id,
        )

        if not task_exists:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        message = data.message.strip() if data.message else None

        if not message:
            raise HTTPException(
                status_code=400,
                detail="Comment message cannot be empty",
            )

        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            message=message,
            attachment_url=None,
            attachment_name=None,
            attachment_type=None,
            attachment_public_id=None,
            is_revision_request=False,
        )

        return await self.repo.add_comment(
            db,
            comment,
        )

    async def add_comment_with_attachment(
        self,
        db,
        task_id,
        user_id,
        data,
        file,
    ):
        task_exists = await self.repo.exists(
            db,
            task_id,
        )

        if not task_exists:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        message = data.message.strip() if data.message else None

        if not message and not file:
            raise HTTPException(
                status_code=400,
                detail="Comment or attachment is required",
            )

        uploaded = None

        try:
            if file:
                uploaded = await upload_service.upload(
                    file,
                    f"printflow/tasks/{task_id}",
                )

            comment = TaskComment(
                task_id=task_id,
                user_id=user_id,
                message=message,
                attachment_url=(uploaded["url"] if uploaded else None),
                attachment_name=(uploaded["file_name"] if uploaded else None),
                attachment_type=(uploaded["file_type"] if uploaded else None),
                attachment_public_id=(uploaded["public_id"] if uploaded else None),
                is_revision_request=False,
            )

            return await self.repo.add_comment(
                db,
                comment,
            )

        except Exception:
            if uploaded and uploaded.get("public_id"):
                try:
                    await upload_service.delete(
                        uploaded["public_id"],
                        uploaded.get(
                            "resource_type",
                            "image",
                        ),
                    )
                except Exception:
                    pass

            raise

    async def get_comments(
        self,
        db,
        task_id,
    ):
        task_exists = await self.repo.exists(
            db,
            task_id,
        )

        if not task_exists:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return await self.repo.get_comments(
            db,
            task_id,
        )

    async def review_task(
        self,
        db,
        task_id,
        reviewer_id,
        data,
    ):
        # Review only needs the task's own fields.
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        if task.status != TaskStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only submitted tasks can be reviewed",
            )

        if data.approve:
            task.status = TaskStatus.APPROVED

            action = "TASK_APPROVED"

            description = f"Task '{task.title}' was approved."

            if data.message:
                comment_message = data.message.strip()
            else:
                comment_message = "Task approved by graphic lead."

            is_revision_request = False

        else:
            task.status = TaskStatus.REVISION_REQUIRED

            action = "TASK_REVISION_REQUESTED"

            description = f"Revision requested for task '{task.title}'."

            if data.message:
                comment_message = data.message.strip()
            else:
                comment_message = "Revision requested by graphic lead."

            is_revision_request = True

        comment = TaskComment(
            task_id=task.id,
            user_id=reviewer_id,
            message=comment_message,
            attachment_url=None,
            attachment_name=None,
            attachment_type=None,
            attachment_public_id=None,
            is_revision_request=is_revision_request,
        )

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=reviewer_id,
            action=action,
            description=description,
        )

        db.add(comment)
        db.add(activity)

        # Only load the production folder itself.
        # We don't need files, activities, or full Task objects.
        folder = await self.production_repo.get_basic_by_id(
            db,
            task.production_folder_id,
        )

        if not folder:
            raise HTTPException(
                status_code=404,
                detail="Production folder not found",
            )

        # Fetch only task statuses rather than loading the
        # entire folder.tasks relationship.
        task_statuses = await self.repo.get_folder_task_statuses(
            db,
            task.production_folder_id,
        )

        if task_statuses and all(
            task_status == TaskStatus.APPROVED for task_status in task_statuses
        ):
            folder.status = ProductionStatus.APPROVED_FOR_PRINT

        elif (
            task.status == TaskStatus.REVISION_REQUIRED
            and folder.status == ProductionStatus.APPROVED_FOR_PRINT
        ):
            folder.status = ProductionStatus.DESIGN_REVIEW

        try:
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        updated_task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not updated_task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return updated_task

    async def delete_attachment(
        self,
        db,
        comment_id,
        user_id,
    ):
        comment = await self.repo.get_comment_by_id(
            db,
            comment_id,
        )

        if not comment:
            raise HTTPException(
                status_code=404,
                detail="Comment not found",
            )

        if comment.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own attachment",
            )

        if not comment.attachment_public_id:
            raise HTTPException(
                status_code=400,
                detail="Comment has no attachment",
            )

        public_id = comment.attachment_public_id
        resource_type = comment.attachment_type

        await upload_service.delete(
            public_id,
            resource_type,
        )

        comment.attachment_url = None
        comment.attachment_name = None
        comment.attachment_type = None
        comment.attachment_public_id = None

        if not comment.message:
            await self.repo.delete_comment(
                db,
                comment,
            )

            return {
                "message": "Attachment deleted successfully",
            }

        return await self.repo.save_comment(
            db,
            comment,
        )
