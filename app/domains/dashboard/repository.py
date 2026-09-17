from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customers.models import Customer
from app.domains.invoices.models import Invoice, InvoiceStatus
from app.domains.orders.models import Order, OrderStatus
from app.domains.payments.models import Payment
from app.domains.production.models import (
    ProductionFolder,
    ProductionStatus,
)
from app.domains.tasks.models import Task, TaskStatus
from app.domains.users.models import User, UserRole

NIGERIA_TZ = ZoneInfo("Africa/Lagos")


def now_ng() -> datetime:
    return datetime.now(NIGERIA_TZ)


def nigeria_day_boundaries(now: datetime):
    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    tomorrow_start = today_start + timedelta(days=1)

    return today_start, tomorrow_start


def nigeria_month_boundaries(now: datetime):
    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    if now.month == 12:
        next_month = month_start.replace(
            year=now.year + 1,
            month=1,
        )
    else:
        next_month = month_start.replace(
            month=now.month + 1,
        )

    return month_start, next_month


class DashboardRepository:
    # ============================================================
    # SUPER ADMIN
    # ============================================================

    async def super_admin_summary(
        self,
        db: AsyncSession,
    ):
        now = now_ng()
        today = now.date()

        today_start, tomorrow_start = nigeria_day_boundaries(now)
        month_start, next_month = nigeria_month_boundaries(now)

        active_order_statuses = [
            OrderStatus.RECEIVED,
            OrderStatus.REVIEWING,
            OrderStatus.READY_FOR_PRODUCTION,
            OrderStatus.IN_PRODUCTION,
        ]

        completed_or_cancelled = [
            OrderStatus.COMPLETED,
            OrderStatus.CANCELLED,
        ]

        # ========================================================
        # BUSINESS
        #
        # Everything is collected in ONE database round trip.
        # ========================================================

        business_query = select(
            # ----------------------------------------------------
            # BUSINESS TOTALS
            # ----------------------------------------------------
            select(func.count(Customer.id)).scalar_subquery().label("customers"),
            select(func.count(Order.id)).scalar_subquery().label("orders"),
            select(
                func.coalesce(
                    func.sum(Payment.amount),
                    0,
                )
            )
            .where(
                Payment.created_at >= month_start,
                Payment.created_at < next_month,
            )
            .scalar_subquery()
            .label("revenue_this_month"),
            select(
                func.coalesce(
                    func.sum(Invoice.balance_due),
                    0,
                )
            )
            .scalar_subquery()
            .label("outstanding_balance"),
            select(func.count(Order.id))
            .where(
                Order.created_at >= today_start,
                Order.created_at < tomorrow_start,
            )
            .scalar_subquery()
            .label("new_orders_today"),
            select(
                func.coalesce(
                    func.sum(Payment.amount),
                    0,
                )
            )
            .where(
                Payment.created_at >= today_start,
                Payment.created_at < tomorrow_start,
            )
            .scalar_subquery()
            .label("payments_today"),
            select(func.count(Customer.id))
            .where(
                Customer.created_at >= today_start,
                Customer.created_at < tomorrow_start,
            )
            .scalar_subquery()
            .label("new_customers_today"),
            select(func.count(Order.id))
            .where(
                Order.due_date < today,
                Order.due_date.is_not(None),
                Order.status.notin_(completed_or_cancelled),
            )
            .scalar_subquery()
            .label("overdue_orders"),
            select(func.count(Order.id))
            .where(
                Order.due_date == today,
                Order.status.notin_(completed_or_cancelled),
            )
            .scalar_subquery()
            .label("due_today"),
            # ----------------------------------------------------
            # ORDER PIPELINE
            # ----------------------------------------------------
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.RECEIVED)
            .scalar_subquery()
            .label("received_orders"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.REVIEWING)
            .scalar_subquery()
            .label("reviewing_orders"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.READY_FOR_PRODUCTION)
            .scalar_subquery()
            .label("ready_for_production"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.IN_PRODUCTION)
            .scalar_subquery()
            .label("in_production"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.COMPLETED)
            .scalar_subquery()
            .label("completed_orders"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.CANCELLED)
            .scalar_subquery()
            .label("cancelled_orders"),
            # ----------------------------------------------------
            # PRODUCTION PIPELINE
            # ----------------------------------------------------
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.CREATED)
            .scalar_subquery()
            .label("production_created"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.WAITING_FOR_REQUIREMENTS)
            .scalar_subquery()
            .label("production_waiting"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.READY_FOR_DESIGN)
            .scalar_subquery()
            .label("production_ready_for_design"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.IN_DESIGN)
            .scalar_subquery()
            .label("production_in_design"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.DESIGN_REVIEW)
            .scalar_subquery()
            .label("production_design_review"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.APPROVED_FOR_PRINT)
            .scalar_subquery()
            .label("production_approved_for_print"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.PRINTING)
            .scalar_subquery()
            .label("production_printing"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.COMPLETED)
            .scalar_subquery()
            .label("production_completed"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.CANCELLED)
            .scalar_subquery()
            .label("production_cancelled"),
            # ----------------------------------------------------
            # TASK PIPELINE
            # ----------------------------------------------------
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.ASSIGNED)
            .scalar_subquery()
            .label("assigned_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.IN_PROGRESS)
            .scalar_subquery()
            .label("in_progress_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.SUBMITTED)
            .scalar_subquery()
            .label("submitted_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.REVISION_REQUIRED)
            .scalar_subquery()
            .label("revision_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.APPROVED)
            .scalar_subquery()
            .label("approved_tasks"),
            select(func.count(Task.id))
            .where(
                Task.deadline < now,
                Task.deadline.is_not(None),
                Task.status != TaskStatus.APPROVED,
            )
            .scalar_subquery()
            .label("overdue_tasks"),
            # ----------------------------------------------------
            # INVOICE PIPELINE
            # ----------------------------------------------------
            select(func.count(Invoice.id))
            .where(Invoice.status == InvoiceStatus.UNPAID)
            .scalar_subquery()
            .label("unpaid_invoices"),
            select(func.count(Invoice.id))
            .where(Invoice.status == InvoiceStatus.PARTIALLY_PAID)
            .scalar_subquery()
            .label("partially_paid_invoices"),
            select(func.count(Invoice.id))
            .where(Invoice.status == InvoiceStatus.PAID)
            .scalar_subquery()
            .label("paid_invoices"),
            select(func.count(Invoice.id))
            .where(Invoice.status == InvoiceStatus.VOID)
            .scalar_subquery()
            .label("void_invoices"),
            # ----------------------------------------------------
            # FINANCIAL TOTALS
            # ----------------------------------------------------
            select(
                func.coalesce(
                    func.sum(Invoice.total_amount),
                    0,
                )
            )
            .scalar_subquery()
            .label("invoice_total"),
            select(
                func.coalesce(
                    func.sum(Payment.amount),
                    0,
                )
            )
            .scalar_subquery()
            .label("payments_total"),
        )

        result = await db.execute(business_query)
        data = result.one()

        # ========================================================
        # RETURN
        # ========================================================

        return {
            # ----------------------------------------------------
            # BUSINESS
            # ----------------------------------------------------
            "customers": data.customers,
            "orders": data.orders,
            "revenue": data.revenue_this_month,
            "outstanding": data.outstanding_balance,
            # ----------------------------------------------------
            # TODAY
            # ----------------------------------------------------
            "new_orders_today": data.new_orders_today,
            "payments_today": data.payments_today,
            "new_customers_today": data.new_customers_today,
            # ----------------------------------------------------
            # ORDERS
            # ----------------------------------------------------
            "received_orders": data.received_orders,
            "reviewing_orders": data.reviewing_orders,
            "ready_for_production": data.ready_for_production,
            "in_production": data.in_production,
            "completed_orders": data.completed_orders,
            "cancelled_orders": data.cancelled_orders,
            "overdue_orders": data.overdue_orders,
            "due_today": data.due_today,
            # ----------------------------------------------------
            # PRODUCTION
            # ----------------------------------------------------
            "created": data.production_created,
            "waiting": data.production_waiting,
            "ready_for_design": data.production_ready_for_design,
            "in_design": data.production_in_design,
            "design_review": data.production_design_review,
            "approved_for_print": data.production_approved_for_print,
            "printing": data.production_printing,
            "completed": data.production_completed,
            "production_cancelled": data.production_cancelled,
            # ----------------------------------------------------
            # TASKS
            # ----------------------------------------------------
            "assigned": data.assigned_tasks,
            "in_progress": data.in_progress_tasks,
            "pending_review": data.submitted_tasks,
            "revision": data.revision_tasks,
            "approved": data.approved_tasks,
            "overdue": data.overdue_tasks,
            # ----------------------------------------------------
            # FINANCIAL
            # ----------------------------------------------------
            "invoice_total": data.invoice_total,
            "payments_total": data.payments_total,
            "unpaid": data.unpaid_invoices,
            "partially_paid": data.partially_paid_invoices,
            "paid": data.paid_invoices,
            "void": data.void_invoices,
        }

    # ============================================================
    # FRONT DESK
    # ============================================================

    async def front_desk_summary(
        self,
        db: AsyncSession,
    ):
        now = now_ng()
        today = now.date()

        today_start, tomorrow_start = nigeria_day_boundaries(now)

        completed_or_cancelled = [
            OrderStatus.COMPLETED,
            OrderStatus.CANCELLED,
        ]

        # ========================================================
        # ONE DATABASE ROUND TRIP
        # ========================================================

        query = select(
            # Today orders
            select(func.count(Order.id))
            .where(
                Order.created_at >= today_start,
                Order.created_at < tomorrow_start,
            )
            .scalar_subquery()
            .label("today_orders"),
            # Today payments
            select(
                func.coalesce(
                    func.sum(Payment.amount),
                    0,
                )
            )
            .where(
                Payment.created_at >= today_start,
                Payment.created_at < tomorrow_start,
            )
            .scalar_subquery()
            .label("today_payments"),
            # Outstanding
            select(
                func.coalesce(
                    func.sum(Invoice.balance_due),
                    0,
                )
            )
            .scalar_subquery()
            .label("outstanding"),
            # New customers
            select(func.count(Customer.id))
            .where(
                Customer.created_at >= today_start,
                Customer.created_at < tomorrow_start,
            )
            .scalar_subquery()
            .label("new_customers"),
            # Overdue orders
            select(func.count(Order.id))
            .where(
                Order.due_date < today,
                Order.due_date.is_not(None),
                Order.status.notin_(completed_or_cancelled),
            )
            .scalar_subquery()
            .label("overdue_orders"),
            # Due today
            select(func.count(Order.id))
            .where(
                Order.due_date == today,
                Order.status.notin_(completed_or_cancelled),
            )
            .scalar_subquery()
            .label("due_today"),
            # Order statuses
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.RECEIVED)
            .scalar_subquery()
            .label("received_orders"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.REVIEWING)
            .scalar_subquery()
            .label("reviewing_orders"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.READY_FOR_PRODUCTION)
            .scalar_subquery()
            .label("ready_for_production"),
            select(func.count(Order.id))
            .where(Order.status == OrderStatus.IN_PRODUCTION)
            .scalar_subquery()
            .label("in_production"),
            # Invoice statuses
            select(func.count(Invoice.id))
            .where(Invoice.status == InvoiceStatus.UNPAID)
            .scalar_subquery()
            .label("unpaid_invoices"),
            select(func.count(Invoice.id))
            .where(Invoice.status == InvoiceStatus.PARTIALLY_PAID)
            .scalar_subquery()
            .label("partially_paid_invoices"),
            select(func.count(Invoice.id))
            .where(Invoice.status == InvoiceStatus.PAID)
            .scalar_subquery()
            .label("paid_invoices"),
        )

        result = await db.execute(query)
        data = result.one()

        return {
            "today_orders": data.today_orders,
            "today_payments": data.today_payments,
            "outstanding": data.outstanding,
            "new_customers": data.new_customers,
            "received_orders": data.received_orders,
            "reviewing_orders": data.reviewing_orders,
            "ready_for_production": data.ready_for_production,
            "in_production": data.in_production,
            "overdue_orders": data.overdue_orders,
            "due_today": data.due_today,
            "unpaid_invoices": data.unpaid_invoices,
            "partially_paid_invoices": data.partially_paid_invoices,
            "paid_invoices": data.paid_invoices,
        }

    # ============================================================
    # GRAPHIC LEAD
    # ============================================================

    async def graphic_lead_summary(
        self,
        db: AsyncSession,
    ):
        now = now_ng()

        # ========================================================
        # ONE DATABASE ROUND TRIP
        # ========================================================

        query = select(
            # ----------------------------------------------------
            # TASK PIPELINE
            # ----------------------------------------------------
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.ASSIGNED)
            .scalar_subquery()
            .label("assigned_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.IN_PROGRESS)
            .scalar_subquery()
            .label("in_progress_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.SUBMITTED)
            .scalar_subquery()
            .label("submitted_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.REVISION_REQUIRED)
            .scalar_subquery()
            .label("revision_required_tasks"),
            select(func.count(Task.id))
            .where(Task.status == TaskStatus.APPROVED)
            .scalar_subquery()
            .label("approved_tasks"),
            select(func.count(Task.id))
            .where(
                Task.deadline < now,
                Task.deadline.is_not(None),
                Task.status != TaskStatus.APPROVED,
            )
            .scalar_subquery()
            .label("overdue_tasks"),
            # ----------------------------------------------------
            # PRODUCTION PIPELINE
            # ----------------------------------------------------
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.CREATED)
            .scalar_subquery()
            .label("created"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.WAITING_FOR_REQUIREMENTS)
            .scalar_subquery()
            .label("waiting_for_requirements"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.READY_FOR_DESIGN)
            .scalar_subquery()
            .label("ready_for_design"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.IN_DESIGN)
            .scalar_subquery()
            .label("in_design"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.DESIGN_REVIEW)
            .scalar_subquery()
            .label("design_review"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.APPROVED_FOR_PRINT)
            .scalar_subquery()
            .label("approved_for_print"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.PRINTING)
            .scalar_subquery()
            .label("printing"),
            select(func.count(ProductionFolder.id))
            .where(ProductionFolder.status == ProductionStatus.COMPLETED)
            .scalar_subquery()
            .label("completed"),
        )

        result = await db.execute(query)
        data = result.one()

        design_queue = data.assigned_tasks + data.in_progress_tasks

        return {
            "design_queue": design_queue,
            "pending_reviews": data.submitted_tasks,
            "overdue": data.overdue_tasks,
            "assigned_tasks": data.assigned_tasks,
            "in_progress_tasks": data.in_progress_tasks,
            "submitted_tasks": data.submitted_tasks,
            "revision_required_tasks": (data.revision_required_tasks),
            "approved_tasks": data.approved_tasks,
            "created": data.created,
            "waiting_for_requirements": (data.waiting_for_requirements),
            "ready_for_design": data.ready_for_design,
            "in_design": data.in_design,
            "design_review": data.design_review,
            "approved_for_print": data.approved_for_print,
            "printing": data.printing,
            "completed": data.completed,
        }

    # ============================================================
    # GRAPHIC DESIGNER
    # ============================================================

    async def graphic_designer_summary(
        self,
        db: AsyncSession,
        user_id: str,
    ):
        now = now_ng()

        query = select(
            func.count(
                case(
                    (
                        Task.status == TaskStatus.ASSIGNED,
                        1,
                    )
                )
            ).label("assigned"),
            func.count(
                case(
                    (
                        Task.status == TaskStatus.IN_PROGRESS,
                        1,
                    )
                )
            ).label("in_progress"),
            func.count(
                case(
                    (
                        Task.status == TaskStatus.SUBMITTED,
                        1,
                    )
                )
            ).label("submitted"),
            func.count(
                case(
                    (
                        Task.status == TaskStatus.REVISION_REQUIRED,
                        1,
                    )
                )
            ).label("revision"),
            func.count(
                case(
                    (
                        Task.status == TaskStatus.APPROVED,
                        1,
                    )
                )
            ).label("approved"),
            func.count(
                case(
                    (
                        (
                            (Task.deadline < now)
                            & Task.deadline.is_not(None)
                            & (Task.status != TaskStatus.APPROVED)
                        ),
                        1,
                    )
                )
            ).label("overdue"),
        ).where(Task.assigned_to == user_id)

        result = await db.execute(query)
        summary = result.one()

        return {
            "assigned": summary.assigned,
            "in_progress": summary.in_progress,
            "submitted": summary.submitted,
            "revision": summary.revision,
            "approved": summary.approved,
            "overdue": summary.overdue,
        }

    # ============================================================
    # STAFF ACTIVITY
    # ============================================================

    async def staff_activity(
        self,
        db: AsyncSession,
    ):
        now = now_ng()
        online_cutoff = now - timedelta(minutes=5)

        # ========================================================
        # STEP 1
        # Get staff + current task in ONE database round trip.
        #
        # row_number() gives us only the newest active task
        # for each designer.
        # ========================================================

        task_rank = (
            func.row_number()
            .over(
                partition_by=Task.assigned_to,
                order_by=Task.created_at.desc(),
            )
            .label("task_rank")
        )

        current_task_subquery = (
            select(
                Task.assigned_to.label("assigned_to"),
                Task.title.label("task_title"),
                Task.status.label("task_status"),
                task_rank,
            )
            .where(
                Task.status.in_(
                    [
                        TaskStatus.ASSIGNED,
                        TaskStatus.IN_PROGRESS,
                        TaskStatus.REVISION_REQUIRED,
                        TaskStatus.SUBMITTED,
                    ]
                )
            )
            .subquery()
        )

        query = (
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.username,
                User.role,
                User.last_login_at,
                User.last_activity_at,
                current_task_subquery.c.task_title,
                current_task_subquery.c.task_status,
            )
            .outerjoin(
                current_task_subquery,
                (User.id == current_task_subquery.c.assigned_to)
                & (current_task_subquery.c.task_rank == 1),
            )
            .where(
                User.role.in_(
                    [
                        UserRole.FRONT_DESK,
                        UserRole.GRAPHIC_LEAD,
                        UserRole.GRAPHIC_DESIGNER,
                    ]
                )
            )
            .order_by(
                User.role,
                User.first_name,
                User.last_name,
            )
        )

        result = await db.execute(query)
        staff = result.all()

        # ========================================================
        # BUILD RESPONSE
        # ========================================================

        output = []

        for user in staff:
            output.append(
                {
                    "id": str(user.id),
                    "name": (f"{user.first_name} {user.last_name}"),
                    "username": user.username,
                    "role": user.role,
                    "is_online": (
                        user.last_activity_at is not None
                        and user.last_activity_at >= online_cutoff
                    ),
                    "last_login": user.last_login_at,
                    "last_activity": (user.last_activity_at),
                    "current_task": user.task_title,
                    "task_status": user.task_status,
                }
            )

        return output
