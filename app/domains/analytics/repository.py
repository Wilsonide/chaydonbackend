from calendar import month_name
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models import MovementType, StockMovement
from app.domains.orders.models import Order, OrderStatus, OrderType
from app.domains.production.models import ProductionFolder
from app.domains.tasks.models import Task, TaskStatus
from app.domains.users.models import User


class AnalyticsRepository:
    async def get_yearly_analytics(
        self,
        db: AsyncSession,
        year: int,
    ) -> list[dict]:
        """
        Build monthly analytics based on completed orders.

        Revenue:
            Order.total_amount

        Material cost:
            Linked STOCK_OUT movements for each completed order.

        Designer cost:
            Charges recorded on approved design tasks belonging to
            completed design orders.

        Profit:
            Revenue - material cost - designer cost

        Inventory consumption and designer charges are attributed
        to the month in which the related order was completed.
        """

        # =========================================================
        # 1. Revenue from completed orders
        # =========================================================

        revenue_query = (
            select(
                extract("month", Order.completed_at).label("month"),
                func.count(Order.id).label("orders"),
                func.coalesce(
                    func.sum(Order.total_amount),
                    0,
                ).label("revenue"),
            )
            .where(
                Order.status == OrderStatus.COMPLETED,
                Order.completed_at.is_not(None),
                extract("year", Order.completed_at) == year,
            )
            .group_by(
                extract("month", Order.completed_at),
            )
        )

        revenue_result = await db.execute(revenue_query)

        revenue_rows = {
            int(row.month): {
                "orders": int(row.orders),
                "revenue": Decimal(str(row.revenue or 0)),
            }
            for row in revenue_result
        }

        # =========================================================
        # 2. Material cost for completed orders
        # =========================================================

        inventory_query = (
            select(
                extract("month", Order.completed_at).label("month"),
                func.coalesce(
                    func.sum(StockMovement.quantity),
                    0,
                ).label("units_used"),
                func.coalesce(
                    func.sum(StockMovement.quantity * StockMovement.unit_selling_price),
                    0,
                ).label("inventory_value"),
            )
            .join(
                Order,
                Order.id == StockMovement.order_id,
            )
            .where(
                Order.status == OrderStatus.COMPLETED,
                Order.completed_at.is_not(None),
                StockMovement.movement_type == MovementType.STOCK_OUT,
                extract("year", Order.completed_at) == year,
            )
            .group_by(
                extract("month", Order.completed_at),
            )
        )

        inventory_result = await db.execute(inventory_query)

        inventory_rows = {
            int(row.month): {
                "units_used": int(row.units_used or 0),
                "inventory_value": Decimal(str(row.inventory_value or 0)),
            }
            for row in inventory_result
        }

        # =========================================================
        # 3. Designer cost for completed design orders
        # =========================================================
        #
        # Task
        #   -> ProductionFolder
        #   -> Order
        #
        # Only APPROVED tasks are included.
        #
        # The charge is attributed to Order.completed_at.
        #
        # =========================================================

        designer_cost_query = (
            select(
                extract(
                    "month",
                    Order.completed_at,
                ).label("month"),
                func.coalesce(
                    func.sum(Task.designer_charge),
                    0,
                ).label("designer_cost"),
            )
            .join(
                ProductionFolder,
                ProductionFolder.id == Task.production_folder_id,
            )
            .join(
                Order,
                Order.id == ProductionFolder.order_id,
            )
            .where(
                Task.status == TaskStatus.APPROVED,
                Task.designer_charge > 0,
                Order.status == OrderStatus.COMPLETED,
                Order.order_type == OrderType.DESIGN,
                Order.completed_at.is_not(None),
                extract("year", Order.completed_at) == year,
            )
            .group_by(
                extract("month", Order.completed_at),
            )
        )

        designer_cost_result = await db.execute(designer_cost_query)

        designer_cost_rows = {
            int(row.month): Decimal(str(row.designer_cost or 0))
            for row in designer_cost_result
        }

        # =========================================================
        # 4. Per-designer earnings
        # =========================================================
        #
        # Each approved task contributes its designer_charge to the
        # designer who was assigned to that task.
        #
        # assigned_to is used because approved tasks cannot be
        # reassigned in the current workflow.
        #
        # =========================================================

        designer_query = (
            select(
                Task.assigned_to.label("designer_id"),
                func.concat(
                    User.first_name,
                    " ",
                    User.last_name,
                ).label("designer_name"),
                func.coalesce(
                    func.sum(Task.designer_charge),
                    0,
                ).label("total_charge"),
                func.count(Task.id).label("completed_tasks"),
            )
            .join(
                ProductionFolder,
                ProductionFolder.id == Task.production_folder_id,
            )
            .join(
                Order,
                Order.id == ProductionFolder.order_id,
            )
            .join(
                User,
                User.id == Task.assigned_to,
            )
            .where(
                Task.status == TaskStatus.APPROVED,
                Task.assigned_to.is_not(None),
                Task.designer_charge > 0,
                Order.status == OrderStatus.COMPLETED,
                Order.order_type == OrderType.DESIGN,
                Order.completed_at.is_not(None),
                extract("year", Order.completed_at) == year,
            )
            .group_by(
                Task.assigned_to,
                User.first_name,
                User.last_name,
            )
            .order_by(
                func.sum(Task.designer_charge).desc(),
            )
        )

        designer_result = await db.execute(designer_query)

        designer_rows = [
            {
                "designer_id": row.designer_id,
                "designer_name": row.designer_name,
                "completed_tasks": int(row.completed_tasks or 0),
                "total_charge": Decimal(str(row.total_charge or 0)),
            }
            for row in designer_result
        ]

        # =========================================================
        # 5. Build all 12 months
        # =========================================================

        monthly = []

        for month in range(1, 13):
            revenue_data = revenue_rows.get(
                month,
                {
                    "orders": 0,
                    "revenue": Decimal("0.00"),
                },
            )

            inventory_data = inventory_rows.get(
                month,
                {
                    "units_used": 0,
                    "inventory_value": Decimal("0.00"),
                },
            )

            revenue = revenue_data["revenue"]

            material_cost = inventory_data["inventory_value"]

            designer_cost = designer_cost_rows.get(
                month,
                Decimal("0.00"),
            )

            profit = revenue - material_cost - designer_cost

            monthly.append(
                {
                    "month": month,
                    "month_name": month_name[month],
                    "orders": revenue_data["orders"],
                    "revenue": revenue,
                    "material_cost": material_cost,
                    "designer_cost": designer_cost,
                    "profit": profit,
                    "inventory_units_used": inventory_data["units_used"],
                    "inventory_value_used": material_cost,
                }
            )

        return {
            "monthly": monthly,
            "designers": designer_rows,
        }
