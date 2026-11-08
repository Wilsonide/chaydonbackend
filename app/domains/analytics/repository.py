from calendar import month_name
from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.analytics.schemas import (
    DailyAnalytics,
    MonthlyAnalytics,
)
from app.domains.invoices.models import Invoice, InvoiceStatus
from app.domains.orders.models import Order, OrderStatus


ZERO = Decimal("0.00")


def to_decimal(value) -> Decimal:
    return Decimal(str(value or ZERO)).quantize(Decimal("0.01"))


class AnalyticsRepository:

    async def get_yearly_analytics(
        self,
        db: AsyncSession,
        year: int,
    ) -> dict:
        """
        Build yearly business revenue analytics.

        Order value:
            Invoice.total_amount grouped by order creation date.

        Revenue received:
            Same as order value. Every valid print order contributes
            its full invoice value to revenue received.

        Outstanding balance:
            Invoice.balance_due grouped by order creation date.

        Cancelled orders and void invoices are excluded from
        order value, revenue received, and outstanding balance.
        """

        # =====================================================
        # 1. Order value and outstanding balance
        # =====================================================

        order_month = extract("month", Order.created_at)
        order_day = extract("day", Order.created_at)

        valid_invoice = or_(
            Invoice.id.is_(None),
            Invoice.status != InvoiceStatus.VOID,
        )

        order_analytics_query = (
            select(
                order_month.label("month"),
                order_day.label("day"),
                func.count(Order.id).label("orders"),
                func.coalesce(
                    func.sum(Invoice.total_amount),
                    ZERO,
                ).label("order_value"),
                func.coalesce(
                    func.sum(Invoice.balance_due),
                    ZERO,
                ).label("outstanding_balance"),
            )
            .outerjoin(
                Invoice,
                Invoice.order_id == Order.id,
            )
            .where(
                Order.status != OrderStatus.CANCELLED,
                extract("year", Order.created_at) == year,
                valid_invoice,
            )
            .group_by(
                order_month,
                order_day,
            )
        )

        order_result = await db.execute(order_analytics_query)

        order_rows = {
            (int(row.month), int(row.day)): {
                "orders": int(row.orders or 0),
                "order_value": to_decimal(row.order_value),
                "outstanding_balance": to_decimal(
                    row.outstanding_balance
                ),
            }
            for row in order_result
        }

        # =====================================================
        # 2. Build monthly and daily analytics
        # =====================================================

        monthly = []

        total_orders = 0
        total_order_value = ZERO
        total_revenue_received = ZERO
        total_outstanding_balance = ZERO

        for month in range(1, 13):

            if month == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month + 1, 1)

            current_month = date(year, month, 1)

            days_in_month = (
                next_month - current_month
            ).days

            monthly_orders = 0
            monthly_order_value = ZERO
            monthly_revenue_received = ZERO
            monthly_outstanding_balance = ZERO

            daily = []

            for day in range(1, days_in_month + 1):

                key = (month, day)

                order_data = order_rows.get(
                    key,
                    {
                        "orders": 0,
                        "order_value": ZERO,
                        "outstanding_balance": ZERO,
                    },
                )

                order_value = order_data["order_value"]

                # Revenue received is defined as the full value
                # of print orders, not actual payment collections.
                revenue_received = order_value

                outstanding_balance = order_data[
                    "outstanding_balance"
                ]

                daily.append(
                    DailyAnalytics(
                        day=day,
                        date=date(
                            year,
                            month,
                            day,
                        ).isoformat(),
                        orders=order_data["orders"],
                        order_value=order_value,
                        revenue_received=revenue_received,
                        outstanding_balance=outstanding_balance,
                    )
                )

                monthly_orders += order_data["orders"]

                monthly_order_value += order_value

                monthly_revenue_received += revenue_received

                monthly_outstanding_balance += outstanding_balance

            monthly.append(
                MonthlyAnalytics(
                    month=month,
                    month_name=month_name[month],
                    orders=monthly_orders,
                    order_value=monthly_order_value,
                    revenue_received=monthly_revenue_received,
                    outstanding_balance=monthly_outstanding_balance,
                    daily=daily,
                )
            )

            total_orders += monthly_orders
            total_order_value += monthly_order_value
            total_revenue_received += monthly_revenue_received
            total_outstanding_balance += monthly_outstanding_balance

        # =====================================================
        # 3. Return yearly analytics
        # =====================================================

        return {
            "total_orders": total_orders,
            "total_order_value": total_order_value,
            "total_revenue_received": total_revenue_received,
            "total_outstanding_balance": total_outstanding_balance,
            "monthly": monthly,
        }