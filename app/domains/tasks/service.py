from datetime import UTC, datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.orders.models import Order, OrderStatus
from app.domains.production.models import (
    ProductionActivity,
    ProductionStatus,
)
from app.domains.production.repository import ProductionRepository
from app.domains.tasks.models import (
    Task,
    TaskComment,
    TaskStatus,
)
from app.domains.tasks.repository import TaskRepository
from app.domains.users.models import UserRole
from app.domains.users.repository import UserRepository
from app.services.cloudinary_service import CloudinaryService
from app.shared.responses import build_page

upload_service = CloudinaryService()


class TaskService:
    def __init__(self):
        self.repo = TaskRepository()
        self.production_repo = ProductionRepository()
        self.user_repo = UserRepository()

    # ============================================================

    # SYNCHRONIZE TASK → PRODUCTION → ORDER
    # ============================================================

    async def _sync_workflow_status(
        self,
        db: AsyncSession,
        task: Task,
    ) -> None:
        """
        Synchronize.

            Tasks
                ↓
            Production Folder
                ↓
            Order

        Workflow:

            All tasks approved
                → ProductionFolder.COMPLETED
                → Order.COMPLETED
                → Order.completed_at set

            Submitted / revision required
                → ProductionFolder.DESIGN_REVIEW
                → Order.IN_PRODUCTION

            Assigned / in progress
                → ProductionFolder.IN_DESIGN
                → Order.IN_PRODUCTION

            No active work
                → ProductionFolder.READY_FOR_DESIGN
                → Order.READY_FOR_PRODUCTION

        This method does NOT commit.
        The caller is responsible for committing.
        """
        folder = await self.production_repo.get_basic_by_id(
            db,
            str(task.production_folder_id),
        )

        if not folder:
            raise HTTPException(
                status_code=404,
                detail="Production folder not found",
            )

        order = await db.get(
            Order,
            folder.order_id,
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        task_statuses = await self.repo.get_folder_task_statuses(
            db,
            folder.id,
        )

        # ------------------------------------------------------------
        # TASK STATUS SUMMARY
        # ------------------------------------------------------------

        all_approved = bool(task_statuses) and all(
            status == TaskStatus.APPROVED for status in task_statuses
        )

        any_review = any(
            status
            in {
                TaskStatus.SUBMITTED,
                TaskStatus.REVISION_REQUIRED,
            }
            for status in task_statuses
        )

        any_active = any(
            status
            in {
                TaskStatus.ASSIGNED,
                TaskStatus.IN_PROGRESS,
            }
            for status in task_statuses
        )

        previous_folder_status = folder.status
        previous_order_status = order.status

        # ------------------------------------------------------------
        # TASK → PRODUCTION FOLDER
        # ------------------------------------------------------------

        if all_approved:
            # All tasks belonging to this production folder
            # have now been approved.
            folder.status = ProductionStatus.COMPLETED

        elif any_review:
            folder.status = ProductionStatus.DESIGN_REVIEW

        elif any_active:
            folder.status = ProductionStatus.IN_DESIGN

        else:
            folder.status = ProductionStatus.READY_FOR_DESIGN

        # ------------------------------------------------------------
        # PRODUCTION FOLDER → ORDER
        # ------------------------------------------------------------

        if folder.status == ProductionStatus.READY_FOR_DESIGN:
            order.status = OrderStatus.READY_FOR_PRODUCTION

        elif folder.status in {
            ProductionStatus.IN_DESIGN,
            ProductionStatus.DESIGN_REVIEW,
            ProductionStatus.APPROVED_FOR_PRINT,
            ProductionStatus.PRINTING,
        }:
            order.status = OrderStatus.IN_PRODUCTION

        elif folder.status == ProductionStatus.COMPLETED:
            order.status = OrderStatus.COMPLETED

            # --------------------------------------------------------
            # RECORD ORDER COMPLETION TIME
            # --------------------------------------------------------
            #
            # Only set completed_at when the order is transitioning
            # into COMPLETED for the first time.
            #
            if previous_order_status != OrderStatus.COMPLETED:
                order.completed_at = datetime.now(UTC)

        elif folder.status == ProductionStatus.CANCELLED:
            order.status = OrderStatus.CANCELLED

        # ------------------------------------------------------------
        # ACTIVITY HISTORY
        # ------------------------------------------------------------

        if (
            previous_folder_status != folder.status
            or previous_order_status != order.status
        ):
            db.add(
                ProductionActivity(
                    production_folder_id=folder.id,
                    user_id=task.assigned_to or task.assigned_by,
                    action="WORKFLOW_SYNCED",
                    description=(
                        f"Workflow synchronized. "
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
    # CREATE TASK
    # ============================================================

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
            task = await self.repo.create_pending(
                db,
                task,
            )

            activity = ProductionActivity(
                production_folder_id=production_folder.id,
                user_id=assigned_by,
                action="TASK_CREATED",
                description=(
                    f"Task '{task.title}' was created for "
                    f"production folder "
                    f"{production_folder.folder_number}."
                ),
            )

            db.add(activity)

            await self._sync_workflow_status(
                db,
                task,
            )

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

    # ============================================================
    # GET ALL TASKS
    # ============================================================

    async def get_all(
        self,
        db,
        page,
        limit,
        search=None,
        status=None,
        priority=None,
        order_type=None,
    ):
        items, total = await self.repo.get_all(
            db,
            page=page,
            limit=limit,
            search=search,
            status=status,
            priority=priority,
            order_type=order_type,
        )

        return build_page(
            items=items,
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

    # ============================================================
    # UPDATE TASK
    # ============================================================

    async def update(
        self,
        db,
        task_id,
        data,
        user_id,
    ):
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        changes: list[str] = []

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
                f"{task.priority.value} to "
                f"{update_data['priority'].value}"
            )
            task.priority = update_data["priority"]

        if "deadline" in update_data and update_data["deadline"] != task.deadline:
            changes.append("deadline updated")
            task.deadline = update_data["deadline"]

        if not changes:
            return await self.repo.get_by_id(
                db,
                task_id,
            )

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=user_id,
            action="TASK_UPDATED",
            description="; ".join(changes),
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
                detail="Task not found after update",
            )

        return updated_task

    # ============================================================
    # ASSIGN TASK
    # ============================================================

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
                detail="Selected user is not a graphic designer",
            )

        if not designer.is_active:
            raise HTTPException(
                status_code=400,
                detail="Selected designer is inactive",
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
            description = (
                f"Task '{task.title}' was reassigned from "
                f"{previous_designer.first_name} "
                f"{previous_designer.last_name} to "
                f"{designer.first_name} "
                f"{designer.last_name}."
            )

            action = "TASK_REASSIGNED"

        else:
            description = (
                f"Task '{task.title}' was assigned to "
                f"{designer.first_name} "
                f"{designer.last_name}."
            )

            action = "TASK_ASSIGNED"

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=assigned_by,
            action=action,
            description=description,
        )

        db.add(activity)

        await self._sync_workflow_status(
            db,
            task,
        )

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
                detail="Task not found after assignment",
            )

        return updated_task

    # ============================================================
    # DELETE TASK
    # ============================================================

    async def delete(
        self,
        db,
        task_id,
    ):
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        attachment_comments = await self.repo.get_attachment_comments(
            db,
            task_id,
        )

        for comment in attachment_comments:
            if comment.attachment_public_id:
                try:
                    await upload_service.delete(
                        comment.attachment_public_id,
                        comment.attachment_resource_type,
                    )
                except Exception:
                    pass

        await self.repo.delete(
            db,
            task,
        )

        return {"message": "Task deleted successfully"}

    # ============================================================
    # GET FOLDER TASKS
    # ============================================================

    async def get_folder_tasks(
        self,
        db,
        folder_id,
        page,
        limit,
        search=None,
    ):
        items, total = await self.repo.get_folder_tasks(
            db=db,
            folder_id=folder_id,
            page=page,
            limit=limit,
            search=search,
        )

        return build_page(
            items=items,
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
        page,
        limit,
        search=None,
    ):
        items, total = await self.repo.get_designer_tasks(
            db=db,
            designer_id=user_id,
            page=page,
            limit=limit,
            search=search,
        )

        return build_page(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    # ============================================================
    # DESIGNER STATUS UPDATE
    # ============================================================

    async def designer_update_status(
        self,
        db,
        task_id,
        user_id,
        new_status,
    ):
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
                detail="Task is not assigned to a designer",
            )

        if str(task.assigned_to) != str(user_id):
            raise HTTPException(
                status_code=403,
                detail="You can only update your own assigned tasks",
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
                    f"Cannot change task status from "
                    f"{task.status.value} to "
                    f"{new_status.value}"
                ),
            )

        previous_status = task.status
        task.status = new_status

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=user_id,
            action="TASK_STATUS_UPDATED",
            description=(
                f"Task '{task.title}' status changed from "
                f"{previous_status.value} to "
                f"{new_status.value}."
            ),
        )

        db.add(activity)

        await self._sync_workflow_status(
            db,
            task,
        )

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
                detail="Task not found after status update",
            )

        return updated_task

    # ============================================================
    # REVIEW TASK
    # ============================================================

    async def review_task(
        self,
        db,
        task_id,
        reviewer_id,
        approve,
        message,
        designer_charge,
    ):
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

        # ------------------------------------------------------------
        # APPROVAL
        # ------------------------------------------------------------

        if approve:
            if designer_charge is None:
                raise HTTPException(
                    status_code=400,
                    detail="Designer charge is required when approving a task",
                )

            if designer_charge < 0:
                raise HTTPException(
                    status_code=400,
                    detail="Designer charge cannot be negative",
                )

            task.status = TaskStatus.APPROVED

            # --------------------------------------------------------
            # SAVE DESIGNER CHARGE
            # --------------------------------------------------------

            task.designer_charge = designer_charge

            action = "TASK_APPROVED"

            description = (
                f"Task '{task.title}' was approved. "
                f"Designer charge: {designer_charge:.2f}."
            )

            comment_message = (
                message.strip()
                if message and message.strip()
                else "Task approved by graphic lead."
            )

        # ------------------------------------------------------------
        # REVISION
        # ------------------------------------------------------------

        else:
            task.status = TaskStatus.REVISION_REQUIRED

            action = "TASK_REVISION_REQUESTED"

            description = f"Revision was requested for task '{task.title}'."

            comment_message = (
                message.strip()
                if message and message.strip()
                else "Revision requested by graphic lead."
            )

        # ------------------------------------------------------------
        # COMMENT
        # ------------------------------------------------------------

        comment = TaskComment(
            task_id=task.id,
            user_id=reviewer_id,
            message=comment_message,
        )

        # ------------------------------------------------------------
        # ACTIVITY
        # ------------------------------------------------------------

        activity = ProductionActivity(
            production_folder_id=task.production_folder_id,
            user_id=reviewer_id,
            action=action,
            description=description,
        )

        db.add(comment)
        db.add(activity)

        # ------------------------------------------------------------
        # SYNCHRONIZE TASK → PRODUCTION → ORDER
        # ------------------------------------------------------------

        await self._sync_workflow_status(
            db,
            task,
        )

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
                detail="Task not found after review",
            )

        return updated_task

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
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        if not message or not message.strip():
            raise HTTPException(
                status_code=400,
                detail="Comment message cannot be empty",
            )

        comment = TaskComment(
            task_id=task.id,
            user_id=user_id,
            message=message.strip(),
        )

        return await self.repo.add_comment(
            db,
            comment,
        )

    # ============================================================
    # COMMENT WITH ATTACHMENT
    # ============================================================

    async def add_comment_with_attachment(
        self,
        db,
        task_id,
        user_id,
        message,
        file,
    ):
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        clean_message = message.strip() if message else None

        if not clean_message and not file:
            raise HTTPException(
                status_code=400,
                detail="Message or attachment is required",
            )

        uploaded = None

        try:
            # ----------------------------------------------------
            # UPLOAD ATTACHMENT
            # ----------------------------------------------------

            if file:
                uploaded = await upload_service.upload(
                    file,
                    f"printflow/tasks/{task.id}/comments",
                )

            # ----------------------------------------------------
            # CREATE COMMENT
            # ----------------------------------------------------

            comment = TaskComment(
                task_id=task.id,
                user_id=user_id,
                message=clean_message,
                attachment_url=(uploaded["url"] if uploaded else None),
                attachment_public_id=(uploaded["public_id"] if uploaded else None),
                attachment_resource_type=(
                    uploaded["resource_type"] if uploaded else None
                ),
                attachment_file_name=(uploaded["file_name"] if uploaded else None),
            )

            return await self.repo.add_comment(
                db,
                comment,
            )

        except Exception:
            await db.rollback()

            # ----------------------------------------------------
            # CLEAN UP CLOUDINARY UPLOAD IF DATABASE SAVE FAILS
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
    # GET COMMENTS
    # ============================================================

    async def get_comments(
        self,
        db,
        task_id,
    ):
        task = await self.repo.get_basic_by_id(
            db,
            task_id,
        )

        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return await self.repo.get_comments(
            db,
            task_id,
        )

    # ============================================================
    # DELETE ATTACHMENT
    # ============================================================

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

        # --------------------------------------------------------
        # ONLY COMMENT OWNER CAN DELETE ATTACHMENT
        # --------------------------------------------------------

        if str(comment.user_id) != str(user_id):
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own attachment",
            )

        if not comment.attachment_public_id:
            raise HTTPException(
                status_code=404,
                detail="Attachment not found",
            )

        public_id = comment.attachment_public_id
        resource_type = comment.attachment_resource_type

        # --------------------------------------------------------
        # DELETE FROM CLOUDINARY
        # --------------------------------------------------------

        await upload_service.delete(
            public_id,
            resource_type,
        )

        # --------------------------------------------------------
        # REMOVE ATTACHMENT DATA
        # --------------------------------------------------------

        comment.attachment_url = None
        comment.attachment_public_id = None
        comment.attachment_resource_type = None
        comment.attachment_file_name = None

        # --------------------------------------------------------
        # DELETE EMPTY COMMENT
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

        return {"message": "Attachment deleted successfully"}
