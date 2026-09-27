from calendar import month_name
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.inventory.models import MovementType, StockMovement
from app.domains.orders.models import Order, OrderStatus


class AnalyticsRepository:
    async def get_yearly_analytics(
        self,
        db: AsyncSession,
        year: int,
    ) -> dict:
        """
        Build yearly analytics with monthly and daily drill-down.

        Revenue:
            Order.total_amount

        Material cost:
            Linked STOCK_OUT movements for completed orders.

        Profit:
            Revenue - material cost

        Inventory consumption is attributed to the
        completion date of the related order.
        """

        # =========================================================
        # 1. Monthly revenue
        # =========================================================

        monthly_revenue_query = (
            select(
                extract(
                    "month",
                    Order.completed_at,
                ).label("month"),
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
                extract(
                    "month",
                    Order.completed_at,
                ),
            )
        )

        monthly_revenue_result = await db.execute(monthly_revenue_query)

        monthly_revenue_rows = {
            int(row.month): {
                "orders": int(row.orders),
                "revenue": Decimal(str(row.revenue or 0)),
            }
            for row in monthly_revenue_result
        }

        # =========================================================
        # 2. Monthly inventory/material cost
        # =========================================================

        monthly_inventory_query = (
            select(
                extract(
                    "month",
                    Order.completed_at,
                ).label("month"),
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
                extract(
                    "year",
                    Order.completed_at,
                )
                == year,
            )
            .group_by(
                extract(
                    "month",
                    Order.completed_at,
                ),
            )
        )

        monthly_inventory_result = await db.execute(monthly_inventory_query)

        monthly_inventory_rows = {
            int(row.month): {
                "units_used": int(row.units_used or 0),
                "inventory_value": Decimal(str(row.inventory_value or 0)),
            }
            for row in monthly_inventory_result
        }

        # =========================================================
        # 3. Daily revenue
        # =========================================================

        daily_revenue_query = (
            select(
                extract(
                    "month",
                    Order.completed_at,
                ).label("month"),
                extract(
                    "day",
                    Order.completed_at,
                ).label("day"),
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
                extract(
                    "month",
                    Order.completed_at,
                ),
                extract(
                    "day",
                    Order.completed_at,
                ),
            )
        )

        daily_revenue_result = await db.execute(daily_revenue_query)

        daily_revenue_rows = {
            (
                int(row.month),
                int(row.day),
            ): {
                "orders": int(row.orders),
                "revenue": Decimal(str(row.revenue or 0)),
            }
            for row in daily_revenue_result
        }

        # =========================================================
        # 4. Daily inventory/material cost
        # =========================================================

        daily_inventory_query = (
            select(
                extract(
                    "month",
                    Order.completed_at,
                ).label("month"),
                extract(
                    "day",
                    Order.completed_at,
                ).label("day"),
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
                extract(
                    "year",
                    Order.completed_at,
                )
                == year,
            )
            .group_by(
                extract(
                    "month",
                    Order.completed_at,
                ),
                extract(
                    "day",
                    Order.completed_at,
                ),
            )
        )

        daily_inventory_result = await db.execute(daily_inventory_query)

        daily_inventory_rows = {
            (
                int(row.month),
                int(row.day),
            ): {
                "units_used": int(row.units_used or 0),
                "inventory_value": Decimal(str(row.inventory_value or 0)),
            }
            for row in daily_inventory_result
        }

        # =========================================================
        # 5. Build monthly + daily structure
        # =========================================================

        monthly = []

        for month in range(1, 13):
            monthly_revenue = monthly_revenue_rows.get(
                month,
                {
                    "orders": 0,
                    "revenue": Decimal("0.00"),
                },
            )

            monthly_inventory = monthly_inventory_rows.get(
                month,
                {
                    "units_used": 0,
                    "inventory_value": Decimal("0.00"),
                },
            )

            revenue = monthly_revenue["revenue"]
            material_cost = monthly_inventory["inventory_value"]

            monthly_profit = revenue - material_cost

            # -----------------------------------------------------
            # Determine number of days in the month
            # -----------------------------------------------------

            if month == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month + 1, 1)

            current_month = date(
                year,
                month,
                1,
            )

            days_in_month = (next_month - current_month).days

            # -----------------------------------------------------
            # Build daily analytics
            # -----------------------------------------------------

            daily = []

            for day in range(
                1,
                days_in_month + 1,
            ):
                revenue_data = daily_revenue_rows.get(
                    (month, day),
                    {
                        "orders": 0,
                        "revenue": Decimal("0.00"),
                    },
                )

                inventory_data = daily_inventory_rows.get(
                    (month, day),
                    {
                        "units_used": 0,
                        "inventory_value": Decimal("0.00"),
                    },
                )

                daily_revenue = revenue_data["revenue"]

                daily_material_cost = inventory_data["inventory_value"]

                daily_profit = daily_revenue - daily_material_cost

                daily.append(
                    {
                        "day": day,
                        "date": date(
                            year,
                            month,
                            day,
                        ).isoformat(),
                        "orders": revenue_data["orders"],
                        "revenue": daily_revenue,
                        "material_cost": (daily_material_cost),
                        "profit": daily_profit,
                        "inventory_units_used": (inventory_data["units_used"]),
                        "inventory_value_used": (daily_material_cost),
                    }
                )

            monthly.append(
                {
                    "month": month,
                    "month_name": month_name[month],
                    "orders": monthly_revenue["orders"],
                    "revenue": revenue,
                    "material_cost": material_cost,
                    "profit": monthly_profit,
                    "inventory_units_used": (monthly_inventory["units_used"]),
                    "inventory_value_used": (material_cost),
                    "daily": daily,
                }
            )

        return {
            "monthly": monthly,
        }
