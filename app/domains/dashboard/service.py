from app.domains.dashboard.repository import DashboardRepository
from app.domains.dashboard.schemas import (
    FrontDeskDashboard,
    GraphicDesignerDashboard,
    GraphicLeadDashboard,
    SuperAdminBusiness,
    SuperAdminDashboard,
    SuperAdminFinancial,
    SuperAdminOrders,
    SuperAdminProduction,
    SuperAdminTasks,
)
from app.domains.users.models import UserRole


class DashboardService:
    def __init__(self):
        self.repo = DashboardRepository()

    async def get_summary(
        self,
        db,
        current_user,
    ):
        role = current_user.role

        # ========================================================
        # SUPER ADMIN
        # ========================================================

        if role == UserRole.SUPER_ADMIN:
            data = await self.repo.super_admin_summary(db)

            return SuperAdminDashboard(
                business=SuperAdminBusiness(
                    customers=data["customers"],
                    orders=data["orders"],
                    revenue_this_month=data["revenue"],
                    outstanding_balance=data["outstanding"],
                    new_orders_today=data["new_orders_today"],
                    payments_today=data["payments_today"],
                    new_customers_today=data["new_customers_today"],
                    overdue_orders=data["overdue_orders"],
                    due_today=data["due_today"],
                ),
                orders=SuperAdminOrders(
                    received=data["received_orders"],
                    reviewing=data["reviewing_orders"],
                    ready_for_production=data["ready_for_production"],
                    in_production=data["in_production"],
                    completed=data["completed_orders"],
                    cancelled=data["cancelled_orders"],
                    overdue=data["overdue_orders"],
                    due_today=data["due_today"],
                ),
                production=SuperAdminProduction(
                    created=data["created"],
                    waiting=data["waiting"],
                    ready_for_design=data["ready_for_design"],
                    in_design=data["in_design"],
                    design_review=data["design_review"],
                    approved_for_print=data["approved_for_print"],
                    printing=data["printing"],
                    completed=data["completed"],
                    cancelled=data["production_cancelled"],
                ),
                tasks=SuperAdminTasks(
                    assigned=data["assigned"],
                    in_progress=data["in_progress"],
                    submitted=data["pending_review"],
                    revision=data["revision"],
                    approved=data["approved"],
                    overdue=data["overdue"],
                ),
                financial=SuperAdminFinancial(
                    invoice_total=data["invoice_total"],
                    payments_total=data["payments_total"],
                    outstanding_balance=data["outstanding"],
                    unpaid=data["unpaid"],
                    partially_paid=data["partially_paid"],
                    paid=data["paid"],
                    void=data["void"],
                ),
            )

        # ========================================================
        # FRONT DESK
        # ========================================================

        if role == UserRole.FRONT_DESK:
            data = await self.repo.front_desk_summary(db)

            return FrontDeskDashboard(
                today_orders=data["today_orders"],
                today_payments=data["today_payments"],
                outstanding_balance=data["outstanding"],
                new_customers=data["new_customers"],
                received_orders=data["received_orders"],
                reviewing_orders=data["reviewing_orders"],
                ready_for_production=data["ready_for_production"],
                in_production=data["in_production"],
                overdue_orders=data["overdue_orders"],
                due_today=data["due_today"],
                unpaid_invoices=data["unpaid_invoices"],
                partially_paid_invoices=data["partially_paid_invoices"],
                paid_invoices=data["paid_invoices"],
            )

        # ========================================================
        # GRAPHIC LEAD
        # ========================================================

        if role == UserRole.GRAPHIC_LEAD:
            data = await self.repo.graphic_lead_summary(db)

            return GraphicLeadDashboard(
                design_queue=data["design_queue"],
                pending_reviews=data["pending_reviews"],
                overdue_tasks=data["overdue"],
                assigned_tasks=data["assigned_tasks"],
                in_progress_tasks=data["in_progress_tasks"],
                submitted_tasks=data["submitted_tasks"],
                revision_required_tasks=data["revision_required_tasks"],
                approved_tasks=data["approved_tasks"],
                created=data["created"],
                waiting_for_requirements=data["waiting_for_requirements"],
                ready_for_design=data["ready_for_design"],
                in_design=data["in_design"],
                design_review=data["design_review"],
                approved_for_print=data["approved_for_print"],
                printing=data["printing"],
                completed=data["completed"],
            )

        # ========================================================
        # GRAPHIC DESIGNER
        # ========================================================

        if role == UserRole.GRAPHIC_DESIGNER:
            data = await self.repo.graphic_designer_summary(
                db,
                str(current_user.id),
            )

            return GraphicDesignerDashboard(
                assigned=data["assigned"],
                in_progress=data["in_progress"],
                submitted=data["submitted"],
                revision_required=data["revision"],
                approved=data["approved"],
                overdue=data["overdue"],
            )

        raise PermissionError("Unsupported role")
