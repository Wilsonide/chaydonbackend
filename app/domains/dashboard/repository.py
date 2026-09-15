from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
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

NIGERIA_TZ = ZoneInfo("Africa/Lagos")


def now_ng() -> datetime:
    return datetime.now(NIGERIA_TZ)


def nigeria_day_boundaries():
    now = now_ng()

    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    tomorrow_start = today_start + timedelta(days=1)

    return today_start, tomorrow_start


def nigeria_month_boundaries():
    now = now_ng()

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
        today_start, tomorrow_start = nigeria_day_boundaries()
        month_start, next_month = nigeria_month_boundaries()
        today = now_ng().date()
        now = now_ng()

        # --------------------------------------------------------
        # BUSINESS TOTALS
        # --------------------------------------------------------

        customers = await db.scalar(select(func.count(Customer.id))) or 0

        orders = await db.scalar(select(func.count(Order.id))) or 0

        # --------------------------------------------------------
        # TODAY
        # --------------------------------------------------------

        new_orders_today = (
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.created_at >= today_start,
                    Order.created_at < tomorrow_start,
                )
            )
            or 0
        )

        payments_today = (
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(Payment.amount),
                        0,
                    )
                ).where(
                    Payment.created_at >= today_start,
                    Payment.created_at < tomorrow_start,
                )
            )
            or 0
        )

        new_customers_today = (
            await db.scalar(
                select(func.count(Customer.id)).where(
                    Customer.created_at >= today_start,
                    Customer.created_at < tomorrow_start,
                )
            )
            or 0
        )

        # --------------------------------------------------------
        # REVENUE
        # --------------------------------------------------------

        revenue_this_month = (
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(Payment.amount),
                        0,
                    )
                ).where(
                    Payment.created_at >= month_start,
                    Payment.created_at < next_month,
                )
            )
            or 0
        )

        # --------------------------------------------------------
        # FINANCIAL TOTALS
        # --------------------------------------------------------

        invoice_total = (
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(Invoice.total_amount),
                        0,
                    )
                )
            )
            or 0
        )

        payments_total = (
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(Payment.amount),
                        0,
                    )
                )
            )
            or 0
        )

        outstanding = invoice_total - payments_total

        # --------------------------------------------------------
        # ORDER PIPELINE
        # --------------------------------------------------------

        order_counts_result = await db.execute(
            select(
                Order.status,
                func.count(Order.id),
            ).group_by(Order.status)
        )

        order_counts = {
            order_status: count for order_status, count in order_counts_result.all()
        }

        # --------------------------------------------------------
        # ORDER DUE / OVERDUE
        # --------------------------------------------------------

        overdue_orders = (
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.due_date < today,
                    Order.due_date.is_not(None),
                    Order.status.notin_(
                        [
                            OrderStatus.COMPLETED,
                            OrderStatus.CANCELLED,
                        ]
                    ),
                )
            )
            or 0
        )

        due_today = (
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.due_date == today,
                    Order.status.notin_(
                        [
                            OrderStatus.COMPLETED,
                            OrderStatus.CANCELLED,
                        ]
                    ),
                )
            )
            or 0
        )

        # --------------------------------------------------------
        # PRODUCTION PIPELINE
        # --------------------------------------------------------

        production_counts_result = await db.execute(
            select(
                ProductionFolder.status,
                func.count(ProductionFolder.id),
            ).group_by(ProductionFolder.status)
        )

        production_counts = {
            production_status: count
            for production_status, count in production_counts_result.all()
        }

        # --------------------------------------------------------
        # TASK PIPELINE
        # --------------------------------------------------------

        task_counts_result = await db.execute(
            select(
                Task.status,
                func.count(Task.id),
            ).group_by(Task.status)
        )

        task_counts = {
            task_status: count for task_status, count in task_counts_result.all()
        }

        overdue_tasks = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.deadline < now,
                    Task.status != TaskStatus.APPROVED,
                )
            )
            or 0
        )

        # --------------------------------------------------------
        # INVOICE PIPELINE
        # --------------------------------------------------------

        invoice_counts_result = await db.execute(
            select(
                Invoice.status,
                func.count(Invoice.id),
            ).group_by(Invoice.status)
        )

        invoice_counts = {
            invoice_status: count
            for invoice_status, count in invoice_counts_result.all()
        }

        # --------------------------------------------------------
        # RETURN
        # --------------------------------------------------------

        return {
            # Business
            "customers": customers,
            "orders": orders,
            "revenue": revenue_this_month,
            "outstanding": outstanding,
            # Today
            "new_orders_today": new_orders_today,
            "payments_today": payments_today,
            "new_customers_today": new_customers_today,
            # Order pipeline
            "received_orders": order_counts.get(
                OrderStatus.RECEIVED,
                0,
            ),
            "reviewing_orders": order_counts.get(
                OrderStatus.REVIEWING,
                0,
            ),
            "ready_for_production": order_counts.get(
                OrderStatus.READY_FOR_PRODUCTION,
                0,
            ),
            "in_production": order_counts.get(
                OrderStatus.IN_PRODUCTION,
                0,
            ),
            "completed_orders": order_counts.get(
                OrderStatus.COMPLETED,
                0,
            ),
            "cancelled_orders": order_counts.get(
                OrderStatus.CANCELLED,
                0,
            ),
            "overdue_orders": overdue_orders,
            "due_today": due_today,
            # Production pipeline
            "created": production_counts.get(
                ProductionStatus.CREATED,
                0,
            ),
            "waiting": production_counts.get(
                ProductionStatus.WAITING_FOR_REQUIREMENTS,
                0,
            ),
            "ready_for_design": production_counts.get(
                ProductionStatus.READY_FOR_DESIGN,
                0,
            ),
            "in_design": production_counts.get(
                ProductionStatus.IN_DESIGN,
                0,
            ),
            "design_review": production_counts.get(
                ProductionStatus.DESIGN_REVIEW,
                0,
            ),
            "approved_for_print": production_counts.get(
                ProductionStatus.APPROVED_FOR_PRINT,
                0,
            ),
            "printing": production_counts.get(
                ProductionStatus.PRINTING,
                0,
            ),
            "completed": production_counts.get(
                ProductionStatus.COMPLETED,
                0,
            ),
            "production_cancelled": production_counts.get(
                ProductionStatus.CANCELLED,
                0,
            ),
            # Task pipeline
            "assigned": task_counts.get(
                TaskStatus.ASSIGNED,
                0,
            ),
            "in_progress": task_counts.get(
                TaskStatus.IN_PROGRESS,
                0,
            ),
            "pending_review": task_counts.get(
                TaskStatus.SUBMITTED,
                0,
            ),
            "revision": task_counts.get(
                TaskStatus.REVISION_REQUIRED,
                0,
            ),
            "approved": task_counts.get(
                TaskStatus.APPROVED,
                0,
            ),
            "overdue": overdue_tasks,
            # Financial pipeline
            "invoice_total": invoice_total,
            "payments_total": payments_total,
            "unpaid": invoice_counts.get(
                InvoiceStatus.UNPAID,
                0,
            ),
            "partially_paid": invoice_counts.get(
                InvoiceStatus.PARTIALLY_PAID,
                0,
            ),
            "paid": invoice_counts.get(
                InvoiceStatus.PAID,
                0,
            ),
            "void": invoice_counts.get(
                InvoiceStatus.VOID,
                0,
            ),
        }

    # ============================================================
    # FRONT DESK
    # ============================================================

    async def front_desk_summary(
        self,
        db: AsyncSession,
    ):
        today_start, tomorrow_start = nigeria_day_boundaries()
        today = now_ng().date()

        # --------------------------------------------------------
        # TODAY
        # --------------------------------------------------------

        today_orders = (
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.created_at >= today_start,
                    Order.created_at < tomorrow_start,
                )
            )
            or 0
        )

        today_payments = (
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(Payment.amount),
                        0,
                    )
                ).where(
                    Payment.created_at >= today_start,
                    Payment.created_at < tomorrow_start,
                )
            )
            or 0
        )

        new_customers = (
            await db.scalar(
                select(func.count(Customer.id)).where(
                    Customer.created_at >= today_start,
                    Customer.created_at < tomorrow_start,
                )
            )
            or 0
        )

        # --------------------------------------------------------
        # OUTSTANDING
        # --------------------------------------------------------

        invoice_total = (
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(Invoice.total_amount),
                        0,
                    )
                )
            )
            or 0
        )

        payments_total = (
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(Payment.amount),
                        0,
                    )
                )
            )
            or 0
        )

        outstanding = invoice_total - payments_total

        # --------------------------------------------------------
        # ORDER PIPELINE
        # --------------------------------------------------------

        order_counts_result = await db.execute(
            select(
                Order.status,
                func.count(Order.id),
            ).group_by(Order.status)
        )

        order_counts = {
            order_status: count for order_status, count in order_counts_result.all()
        }

        # --------------------------------------------------------
        # DUE ORDERS
        # --------------------------------------------------------

        overdue_orders = (
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.due_date < today,
                    Order.due_date.is_not(None),
                    Order.status.notin_(
                        [
                            OrderStatus.COMPLETED,
                            OrderStatus.CANCELLED,
                        ]
                    ),
                )
            )
            or 0
        )

        due_today = (
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.due_date == today,
                    Order.status.notin_(
                        [
                            OrderStatus.COMPLETED,
                            OrderStatus.CANCELLED,
                        ]
                    ),
                )
            )
            or 0
        )

        # --------------------------------------------------------
        # INVOICE PIPELINE
        # --------------------------------------------------------

        invoice_counts_result = await db.execute(
            select(
                Invoice.status,
                func.count(Invoice.id),
            ).group_by(Invoice.status)
        )

        invoice_counts = {
            invoice_status: count
            for invoice_status, count in invoice_counts_result.all()
        }

        return {
            "today_orders": today_orders,
            "today_payments": today_payments,
            "outstanding": outstanding,
            "new_customers": new_customers,
            "received_orders": order_counts.get(
                OrderStatus.RECEIVED,
                0,
            ),
            "reviewing_orders": order_counts.get(
                OrderStatus.REVIEWING,
                0,
            ),
            "ready_for_production": order_counts.get(
                OrderStatus.READY_FOR_PRODUCTION,
                0,
            ),
            "in_production": order_counts.get(
                OrderStatus.IN_PRODUCTION,
                0,
            ),
            "overdue_orders": overdue_orders,
            "due_today": due_today,
            "unpaid_invoices": invoice_counts.get(
                InvoiceStatus.UNPAID,
                0,
            ),
            "partially_paid_invoices": invoice_counts.get(
                InvoiceStatus.PARTIALLY_PAID,
                0,
            ),
            "paid_invoices": invoice_counts.get(
                InvoiceStatus.PAID,
                0,
            ),
        }

    # ============================================================
    # GRAPHIC LEAD
    # ============================================================

    async def graphic_lead_summary(
        self,
        db: AsyncSession,
    ):
        # --------------------------------------------------------
        # TASK PIPELINE
        # --------------------------------------------------------

        task_counts_result = await db.execute(
            select(
                Task.status,
                func.count(Task.id),
            ).group_by(Task.status)
        )

        task_counts = {
            task_status: count for task_status, count in task_counts_result.all()
        }

        design_queue = task_counts.get(TaskStatus.ASSIGNED, 0) + task_counts.get(
            TaskStatus.IN_PROGRESS, 0
        )

        pending_reviews = task_counts.get(
            TaskStatus.SUBMITTED,
            0,
        )

        overdue = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.deadline < now_ng(),
                    Task.status != TaskStatus.APPROVED,
                )
            )
            or 0
        )

        # --------------------------------------------------------
        # PRODUCTION PIPELINE
        # --------------------------------------------------------

        production_counts_result = await db.execute(
            select(
                ProductionFolder.status,
                func.count(ProductionFolder.id),
            ).group_by(ProductionFolder.status)
        )

        production_counts = {
            production_status: count
            for production_status, count in production_counts_result.all()
        }

        return {
            "design_queue": design_queue,
            "pending_reviews": pending_reviews,
            "overdue": overdue,
            "assigned_tasks": task_counts.get(
                TaskStatus.ASSIGNED,
                0,
            ),
            "in_progress_tasks": task_counts.get(
                TaskStatus.IN_PROGRESS,
                0,
            ),
            "submitted_tasks": task_counts.get(
                TaskStatus.SUBMITTED,
                0,
            ),
            "revision_required_tasks": task_counts.get(
                TaskStatus.REVISION_REQUIRED,
                0,
            ),
            "approved_tasks": task_counts.get(
                TaskStatus.APPROVED,
                0,
            ),
            "created": production_counts.get(
                ProductionStatus.CREATED,
                0,
            ),
            "waiting_for_requirements": production_counts.get(
                ProductionStatus.WAITING_FOR_REQUIREMENTS,
                0,
            ),
            "ready_for_design": production_counts.get(
                ProductionStatus.READY_FOR_DESIGN,
                0,
            ),
            "in_design": production_counts.get(
                ProductionStatus.IN_DESIGN,
                0,
            ),
            "design_review": production_counts.get(
                ProductionStatus.DESIGN_REVIEW,
                0,
            ),
            "approved_for_print": production_counts.get(
                ProductionStatus.APPROVED_FOR_PRINT,
                0,
            ),
            "printing": production_counts.get(
                ProductionStatus.PRINTING,
                0,
            ),
            "completed": production_counts.get(
                ProductionStatus.COMPLETED,
                0,
            ),
        }

    # ============================================================
    # GRAPHIC DESIGNER
    # ============================================================

    async def graphic_designer_summary(
        self,
        db: AsyncSession,
        user_id: str,
    ):
        # --------------------------------------------------------
        # TASK COUNTS
        # --------------------------------------------------------

        assigned = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.assigned_to == user_id,
                    Task.status == TaskStatus.ASSIGNED,
                )
            )
            or 0
        )

        in_progress = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.assigned_to == user_id,
                    Task.status == TaskStatus.IN_PROGRESS,
                )
            )
            or 0
        )

        submitted = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.assigned_to == user_id,
                    Task.status == TaskStatus.SUBMITTED,
                )
            )
            or 0
        )

        revision = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.assigned_to == user_id,
                    Task.status == TaskStatus.REVISION_REQUIRED,
                )
            )
            or 0
        )

        approved = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.assigned_to == user_id,
                    Task.status == TaskStatus.APPROVED,
                )
            )
            or 0
        )

        overdue = (
            await db.scalar(
                select(func.count(Task.id)).where(
                    Task.assigned_to == user_id,
                    Task.deadline < now_ng(),
                    Task.status != TaskStatus.APPROVED,
                )
            )
            or 0
        )

        return {
            "assigned": assigned,
            "in_progress": in_progress,
            "submitted": submitted,
            "revision": revision,
            "approved": approved,
            "overdue": overdue,
        }
