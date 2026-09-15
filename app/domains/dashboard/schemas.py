from decimal import Decimal

from pydantic import BaseModel

# ============================================================
# SUPER ADMIN
# ============================================================


class SuperAdminBusiness(BaseModel):
    customers: int
    orders: int

    revenue_this_month: Decimal
    outstanding_balance: Decimal

    new_orders_today: int
    payments_today: Decimal
    new_customers_today: int

    overdue_orders: int
    due_today: int


class SuperAdminOrders(BaseModel):
    received: int
    reviewing: int
    ready_for_production: int
    in_production: int
    completed: int
    cancelled: int

    overdue: int
    due_today: int


class SuperAdminProduction(BaseModel):
    created: int
    waiting: int
    ready_for_design: int
    in_design: int
    design_review: int
    approved_for_print: int
    printing: int
    completed: int
    cancelled: int


class SuperAdminTasks(BaseModel):
    assigned: int
    in_progress: int
    submitted: int
    revision: int
    approved: int
    overdue: int


class SuperAdminFinancial(BaseModel):
    invoice_total: Decimal
    payments_total: Decimal
    outstanding_balance: Decimal

    unpaid: int
    partially_paid: int
    paid: int
    void: int


class SuperAdminDashboard(BaseModel):
    role: str = "SUPER_ADMIN"

    business: SuperAdminBusiness
    orders: SuperAdminOrders
    production: SuperAdminProduction
    tasks: SuperAdminTasks
    financial: SuperAdminFinancial


# ============================================================
# FRONT DESK
# ============================================================


class FrontDeskDashboard(BaseModel):
    role: str = "FRONT_DESK"

    today_orders: int
    today_payments: Decimal
    outstanding_balance: Decimal
    new_customers: int

    received_orders: int
    reviewing_orders: int
    ready_for_production: int
    in_production: int

    overdue_orders: int
    due_today: int

    unpaid_invoices: int
    partially_paid_invoices: int
    paid_invoices: int


# ============================================================
# GRAPHIC LEAD
# ============================================================


class GraphicLeadDashboard(BaseModel):
    role: str = "GRAPHIC_LEAD"

    design_queue: int
    pending_reviews: int
    overdue_tasks: int

    assigned_tasks: int
    in_progress_tasks: int
    submitted_tasks: int
    revision_required_tasks: int
    approved_tasks: int

    created: int
    waiting_for_requirements: int
    ready_for_design: int
    in_design: int
    design_review: int
    approved_for_print: int
    printing: int
    completed: int


# ============================================================
# GRAPHIC DESIGNER
# ============================================================


class GraphicDesignerDashboard(BaseModel):
    role: str = "GRAPHIC_DESIGNER"

    assigned: int
    in_progress: int
    submitted: int
    revision_required: int
    approved: int
    overdue: int
