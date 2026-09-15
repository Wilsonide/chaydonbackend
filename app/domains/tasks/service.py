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

    # ============================================================
    # CREATE TASK
    # ============================================================

    async def create(
        self,
        db,
        data,
        assigned_by,
    ):
        # --------------------------------------------------------
        # Verify production folder exists
        # --------------------------------------------------------

        folder = await self.production_repo.get_by_id(
            db,
            data.production_folder_id,
        )

        if not folder:
            raise HTTPException(
                404,
                "Production folder not found",
            )

        # --------------------------------------------------------
        # Create task
        # --------------------------------------------------------

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

        task = await self.repo.create(
            db,
            task,
        )

        # --------------------------------------------------------
        # Record production activity
        # --------------------------------------------------------

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=assigned_by,
            action="TASK_CREATED",
            description=(
                f"Task '{task.title}' was created "
                f"for production folder "
                f"{folder.folder_number}."
            ),
        )

        db.add(activity)
        await db.commit()

        # --------------------------------------------------------
        # Return fully loaded task
        # --------------------------------------------------------

        return await self.repo.get_by_id(
            db,
            str(task.id),
        )

    # ============================================================
    # GET ALL TASKS
    # ============================================================

    async def get_all(
        self,
        db,
        page: int,
        limit: int,
        search: str | None,
        status,
        priority,
    ):
        tasks, total = await self.repo.get_all(
            db=db,
            page=page,
            limit=limit,
            search=search,
            status=status,
            priority=priority,
        )

        return build_page(
            items=tasks,
            total=total,
            page=page,
            limit=limit,
        )

    # ============================================================
    # GET SINGLE TASK
    # ============================================================

    async def get_by_id(
        self,
        db,
        task_id: str,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        return task

    # ============================================================
    # UPDATE TASK
    # ============================================================

    async def update(
        self,
        db,
        task_id: str,
        data,
        user_id: str,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        changes: list[str] = []

        update_data = data.model_dump(
            exclude_unset=True,
        )

        # --------------------------------------------------------
        # Title
        # --------------------------------------------------------

        if "title" in update_data:
            new_title = update_data["title"]

            if new_title is not None and new_title != task.title:
                changes.append(f"title changed from '{task.title}' to '{new_title}'")

                task.title = new_title

        # --------------------------------------------------------
        # Description
        # --------------------------------------------------------

        if "description" in update_data:
            new_description = update_data["description"]

            if new_description != task.description:
                changes.append("description updated")

                task.description = new_description

        # --------------------------------------------------------
        # Priority
        # --------------------------------------------------------

        if "priority" in update_data:
            new_priority = update_data["priority"]

            if new_priority is not None and new_priority != task.priority:
                changes.append(
                    f"priority changed from "
                    f"{task.priority.value} to "
                    f"{new_priority.value}"
                )

                task.priority = new_priority

        # --------------------------------------------------------
        # Deadline
        # --------------------------------------------------------

        if "deadline" in update_data:
            new_deadline = update_data["deadline"]

            if new_deadline != task.deadline:
                changes.append("deadline updated")

                task.deadline = new_deadline

        # --------------------------------------------------------
        # Nothing changed
        # --------------------------------------------------------

        if not changes:
            return task

        # --------------------------------------------------------
        # Save
        # --------------------------------------------------------

        await self.repo.save(
            db,
            task,
        )

        # --------------------------------------------------------
        # Activity
        # --------------------------------------------------------

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=user_id,
            action="TASK_UPDATED",
            description="; ".join(changes),
        )

        db.add(activity)

        await db.commit()

        # --------------------------------------------------------
        # Return fully loaded task
        # --------------------------------------------------------

        return await self.repo.get_by_id(
            db,
            str(task.id),
        )

    # ============================================================
    # ASSIGN / REASSIGN TASK
    # ============================================================

    async def assign_task(
        self,
        db,
        task_id: str,
        designer_id: str,
        assigned_by: str,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        # --------------------------------------------------------
        # Find designer
        # --------------------------------------------------------

        designer = await self.user_repo.get_by_id(
            db,
            designer_id,
        )

        if not designer:
            raise HTTPException(
                404,
                "Designer not found",
            )

        # --------------------------------------------------------
        # Verify role
        # --------------------------------------------------------

        if designer.role != UserRole.GRAPHIC_DESIGNER:
            raise HTTPException(
                400,
                "Task can only be assigned to a graphic designer.",
            )

        # --------------------------------------------------------
        # Verify active account
        # --------------------------------------------------------

        if not designer.is_active:
            raise HTTPException(
                400,
                "This graphic designer account is inactive.",
            )

        # --------------------------------------------------------
        # Prevent unnecessary reassignment
        # --------------------------------------------------------

        if task.assigned_to is not None and str(task.assigned_to) == str(designer.id):
            raise HTTPException(
                400,
                "This task is already assigned to this designer.",
            )

        # --------------------------------------------------------
        # Prevent reassignment of approved tasks
        # --------------------------------------------------------

        if task.status == TaskStatus.APPROVED:
            raise HTTPException(
                400,
                "Approved tasks cannot be reassigned.",
            )

        # --------------------------------------------------------
        # Store previous assignment
        # --------------------------------------------------------

        previous_designer = task.assigned_designer

        # --------------------------------------------------------
        # Assign designer
        # --------------------------------------------------------

        task.assigned_to = designer.id

        # A new assignment starts the assignment workflow again.
        if task.status == TaskStatus.UNASSIGNED:
            task.status = TaskStatus.ASSIGNED

        elif task.status in (
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.SUBMITTED,
            TaskStatus.REVISION_REQUIRED,
        ):
            task.status = TaskStatus.ASSIGNED

        # --------------------------------------------------------
        # Activity description
        # --------------------------------------------------------

        if previous_designer:
            description = (
                f"Task '{task.title}' reassigned from "
                f"{previous_designer.username} to "
                f"{designer.username}."
            )

            action = "TASK_REASSIGNED"

        else:
            description = (
                f"Task '{task.title}' assigned to designer {designer.username}."
            )

            action = "TASK_ASSIGNED"

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=assigned_by,
            action=action,
            description=description,
        )

        db.add(activity)

        # --------------------------------------------------------
        # Save and return
        # --------------------------------------------------------

        await db.commit()

        return await self.repo.get_by_id(
            db,
            str(task.id),
        )

    # ============================================================
    # DELETE TASK
    # ============================================================

    async def delete(
        self,
        db,
        task_id: str,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        # --------------------------------------------------------
        # Find comments/attachments
        # --------------------------------------------------------

        comments = await self.repo.get_comments(
            db,
            task_id,
        )

        attachments = [comment for comment in comments if comment.attachment_public_id]

        # --------------------------------------------------------
        # Delete Cloudinary attachments
        # --------------------------------------------------------

        for comment in attachments:
            try:
                await upload_service.delete(
                    comment.attachment_public_id,
                    resource_type=comment.attachment_type,
                )

            except Exception as exc:
                raise HTTPException(
                    500,
                    "Failed to delete task attachment from storage.",
                ) from exc

        # --------------------------------------------------------
        # Delete task
        # --------------------------------------------------------

        await self.repo.delete(
            db,
            task,
        )

        return {
            "message": "Task deleted successfully.",
            "task_id": str(task_id),
        }

    # ============================================================
    # GET TASKS FOR PRODUCTION FOLDER
    # ============================================================

    async def get_folder_tasks(
        self,
        db,
        folder_id,
        page: int,
        limit: int,
        search: str | None,
    ):
        tasks, total = await self.repo.get_folder_tasks(
            db,
            folder_id,
            page,
            limit,
            search,
        )

        return build_page(
            items=tasks,
            total=total,
            page=page,
            limit=limit,
        )

    # ============================================================
    # GET DESIGNER TASKS
    # ============================================================

    async def get_designer_tasks(
        self,
        db,
        user_id,
        page: int,
        limit: int,
        search: str | None,
    ):
        tasks, total = await self.repo.get_designer_tasks(
            db,
            user_id,
            page,
            limit,
            search,
        )

        return build_page(
            items=tasks,
            total=total,
            page=page,
            limit=limit,
        )

    # ============================================================
    # DESIGNER UPDATE STATUS
    # ============================================================

    async def designer_update_status(
        self,
        db,
        task_id: str,
        user_id: str,
        new_status: TaskStatus,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        # --------------------------------------------------------
        # Must have an assignee
        # --------------------------------------------------------

        if task.assigned_to is None:
            raise HTTPException(
                400,
                "This task has not been assigned to a designer.",
            )

        # --------------------------------------------------------
        # Must belong to current designer
        # --------------------------------------------------------

        if str(task.assigned_to) != str(user_id):
            raise HTTPException(
                403,
                "This task is not assigned to you.",
            )

        # --------------------------------------------------------
        # Allowed workflow
        # --------------------------------------------------------

        allowed = {
            TaskStatus.UNASSIGNED: [],
            TaskStatus.ASSIGNED: [
                TaskStatus.IN_PROGRESS,
            ],
            TaskStatus.IN_PROGRESS: [
                TaskStatus.SUBMITTED,
            ],
            TaskStatus.SUBMITTED: [],
            TaskStatus.REVISION_REQUIRED: [
                TaskStatus.IN_PROGRESS,
            ],
            TaskStatus.APPROVED: [],
        }

        allowed_transitions = allowed.get(
            task.status,
            [],
        )

        if new_status not in allowed_transitions:
            raise HTTPException(
                400,
                (f"Cannot move from {task.status.value} to {new_status.value}"),
            )

        # --------------------------------------------------------
        # Update
        # --------------------------------------------------------

        old_status = task.status

        task.status = new_status

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=user_id,
            action="TASK_STATUS_UPDATED",
            description=(
                f"Task '{task.title}' changed "
                f"from {old_status.value} "
                f"to {new_status.value}"
            ),
        )

        db.add(activity)

        await db.commit()

        return await self.repo.get_by_id(
            db,
            str(task.id),
        )

    # ============================================================
    # ADD COMMENT
    # ============================================================

    async def add_comment(
        self,
        db,
        task_id,
        user_id,
        message,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        cleaned_message = message.strip() if message else None

        if not cleaned_message:
            raise HTTPException(
                400,
                "Comment message is required.",
            )

        comment = TaskComment(
            task_id=task_id,
            user_id=user_id,
            message=cleaned_message,
        )

        return await self.repo.add_comment(
            db,
            comment,
        )

    # ============================================================
    # ADD COMMENT WITH ATTACHMENT
    # ============================================================

    async def add_comment_with_attachment(
        self,
        db,
        task_id: str,
        user_id: str,
        message: str | None,
        file,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        cleaned_message = message.strip() if message else None

        if not cleaned_message and not file:
            raise HTTPException(
                400,
                "A comment or attachment is required.",
            )

        attachment_url = None
        attachment_name = None
        attachment_type = None
        attachment_public_id = None

        # --------------------------------------------------------
        # Upload attachment
        # --------------------------------------------------------

        if file:
            uploaded = await upload_service.upload(
                file,
                f"printflow/tasks/{task.id}",
            )

            attachment_url = uploaded["url"]
            attachment_name = uploaded["file_name"]
            attachment_type = uploaded["resource_type"]
            attachment_public_id = uploaded["public_id"]

        # --------------------------------------------------------
        # Create comment
        # --------------------------------------------------------

        comment = TaskComment(
            task_id=task.id,
            user_id=user_id,
            message=cleaned_message,
            attachment_url=attachment_url,
            attachment_name=attachment_name,
            attachment_type=attachment_type,
            attachment_public_id=attachment_public_id,
        )

        try:
            return await self.repo.add_comment(
                db,
                comment,
            )

        except Exception:
            if attachment_public_id:
                try:
                    await upload_service.delete(
                        attachment_public_id,
                        resource_type=attachment_type,
                    )

                except Exception:
                    pass

            raise

    # ============================================================
    # GET COMMENTS
    # ============================================================

    async def get_comments(
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
                404,
                "Task not found",
            )

        return await self.repo.get_comments(
            db,
            task_id,
        )

    # ============================================================
    # REVIEW TASK
    # ============================================================

    async def review_task(
        self,
        db,
        task_id: str,
        reviewer_id: str,
        approve: bool,
        message: str | None,
    ):
        task = await self.repo.get_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                404,
                "Task not found",
            )

        # --------------------------------------------------------
        # Only submitted tasks can be reviewed
        # --------------------------------------------------------

        if task.status != TaskStatus.SUBMITTED:
            raise HTTPException(
                400,
                "Only submitted tasks can be reviewed.",
            )

        # --------------------------------------------------------
        # Clean review message
        # --------------------------------------------------------

        cleaned_message = message.strip() if message else None

        # --------------------------------------------------------
        # Approval
        # --------------------------------------------------------

        if approve:
            task.status = TaskStatus.APPROVED

            comment = TaskComment(
                task_id=task.id,
                user_id=reviewer_id,
                message=cleaned_message or "Task approved.",
                is_approval=True,
            )

            activity = ProductionActivity(
                production_folder_id=task.production_folder_id,
                user_id=reviewer_id,
                action="TASK_APPROVED",
                description=(f"{task.title} was approved."),
            )

        # --------------------------------------------------------
        # Revision requested
        # --------------------------------------------------------

        else:
            if not cleaned_message:
                raise HTTPException(
                    400,
                    "A revision message is required when rejecting a task.",
                )

            task.status = TaskStatus.REVISION_REQUIRED

            comment = TaskComment(
                task_id=task.id,
                user_id=reviewer_id,
                message=cleaned_message,
                is_revision_request=True,
            )

            activity = ProductionActivity(
                production_folder_id=task.production_folder_id,
                user_id=reviewer_id,
                action="TASK_REVISION_REQUESTED",
                description=(f"Revision requested for {task.title}."),
            )

        # --------------------------------------------------------
        # Add review comment/activity
        # --------------------------------------------------------

        db.add(comment)
        db.add(activity)

        # --------------------------------------------------------
        # Check production folder status
        # --------------------------------------------------------

        folder = await self.production_repo.get_by_id(
            db,
            task.production_folder_id,
        )

        if folder:
            # Only mark the production folder as approved
            # when there is at least one task and every task
            # is approved.

            tasks = folder.tasks

            if tasks and all(
                production_task.status == TaskStatus.APPROVED
                for production_task in tasks
            ):
                folder.status = ProductionStatus.APPROVED_FOR_PRINT

            elif task.status == TaskStatus.REVISION_REQUIRED:
                # If a task goes back for revision, the
                # production folder should no longer remain
                # approved for print.

                if folder.status == ProductionStatus.APPROVED_FOR_PRINT:
                    folder.status = ProductionStatus.DESIGN_REVIEW

        # --------------------------------------------------------
        # Save everything
        # --------------------------------------------------------

        await db.commit()

        # --------------------------------------------------------
        # Return fully loaded task
        # --------------------------------------------------------

        return await self.repo.get_by_id(
            db,
            str(task.id),
        )

    # ============================================================
    # DELETE TASK ATTACHMENT
    # ============================================================

    async def delete_attachment(
        self,
        db,
        comment_id: str,
        user_id: str,
    ):
        comment = await self.repo.get_comment_by_id(
            db,
            comment_id,
        )

        if not comment:
            raise HTTPException(
                404,
                "Attachment not found",
            )

        if not comment.attachment_public_id:
            raise HTTPException(
                400,
                "This comment does not contain an attachment.",
            )

        # --------------------------------------------------------
        # Only attachment owner can delete it
        # --------------------------------------------------------

        if str(comment.user_id) != str(user_id):
            raise HTTPException(
                403,
                "You can only delete your own attachments.",
            )

        # --------------------------------------------------------
        # Delete from Cloudinary
        # --------------------------------------------------------

        try:
            await upload_service.delete(
                comment.attachment_public_id,
                resource_type=comment.attachment_type,
            )

        except Exception as exc:
            raise HTTPException(
                500,
                "Failed to delete attachment from storage.",
            ) from exc

        # --------------------------------------------------------
        # Remove attachment information from comment
        #
        # IMPORTANT:
        # We do NOT delete the entire comment.
        # --------------------------------------------------------

        comment.attachment_url = None
        comment.attachment_name = None
        comment.attachment_type = None
        comment.attachment_public_id = None

        # --------------------------------------------------------
        # If the comment has no message either, remove the
        # now-empty comment.
        # --------------------------------------------------------

        if not comment.message:
            await self.repo.delete_comment(
                db,
                comment,
            )

        else:
            await self.repo.save_comment(
                db,
                comment,
            )

        return {
            "message": "Attachment deleted successfully.",
            "comment_id": str(comment_id),
        }
