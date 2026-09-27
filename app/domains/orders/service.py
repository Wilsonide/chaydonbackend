import re
from datetime import UTC, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.customers.repository import CustomerRepository
from app.domains.inventory.models import (
    InventoryItem,
    MovementType,
    OrderMaterialRequirement,
    StockMovement,
)
from app.domains.inventory.repository import InventoryRepository
from app.domains.invoices.models import (
    Invoice,
    InvoiceStatus,
)
from app.domains.invoices.repository import InvoiceRepository
from app.domains.orders.models import (
    Order,
    OrderFile,
    OrderStatus,
    OrderType,
)
from app.domains.orders.repository import OrderRepository
from app.domains.orders.schemas import (
    OrderCreate,
    OrderInventoryItemCreate,
    OrderUpdate,
)
from app.domains.production.repository import ProductionRepository
from app.domains.users.models import (
    User,
    UserRole,
)
from app.services.cloudinary_service import CloudinaryService
from app.shared.responses import build_page


class OrderService:
    def __init__(self):
        self.repo = OrderRepository()
        self.customer_repo = CustomerRepository()
        self.invoice_repo = InvoiceRepository()
        self.production_repo = ProductionRepository()
        self.cloudinary = CloudinaryService()
        self.inventory_repo = InventoryRepository()

    _DIMENSION_PATTERN = re.compile(
        r"^\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*(?:\*|x|X|×)\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*$"
    )

    def _calculate_inventory_quantity(
        self,
        *,
        unit: str,
        input_quantity: str,
    ) -> int:
        """
        Convert staff inventory input into the actual quantity to deduct.

        Dimension expressions are only allowed for inventory measured in feet.

        Supported:

            "12"
            "3*4"
            "3 x 4"
            "3x4"

        Current InventoryItem.quantity is an INTEGER, so the
        final calculated quantity must be a whole number.
        """
        raw = input_quantity.strip()

        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inventory quantity cannot be empty.",
            )

        # ========================================================
        # PLAIN INTEGER
        # ========================================================

        if raw.isdigit():
            calculated_quantity = int(raw)

            if calculated_quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=("Inventory quantity must be greater than zero."),
                )

            return calculated_quantity

        # ========================================================
        # DIMENSION EXPRESSION
        # ========================================================

        match = self._DIMENSION_PATTERN.match(raw)

        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid inventory quantity '{input_quantity}'. "
                    "Enter a number such as '12' or a dimension "
                    "such as '3*4'."
                ),
            )

        # ========================================================
        # DIMENSIONS ONLY MAKE SENSE FOR FEET
        # ========================================================

        normalized_unit = unit.strip().lower()

        if normalized_unit not in {
            "feet",
            "foot",
            "ft",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Dimension input '{input_quantity}' is not "
                    f"valid for inventory measured in '{unit}'. "
                    "Dimension calculations are currently "
                    "supported only for feet."
                ),
            )

        # ========================================================
        # CONVERT DIMENSIONS
        # ========================================================

        first_dimension = Decimal(
            match.group(1),
        )

        second_dimension = Decimal(
            match.group(2),
        )

        calculated = first_dimension * second_dimension

        # ========================================================
        # CURRENT DATABASE USES INTEGER QUANTITIES
        # ========================================================

        if calculated != calculated.to_integral_value():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"'{input_quantity}' calculates to "
                    f"{calculated}. "
                    "Inventory quantities must currently "
                    "be whole numbers."
                ),
            )

        calculated_quantity = int(calculated)

        if calculated_quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("Calculated inventory quantity must be greater than zero."),
            )

        return calculated_quantity

    # ============================================================
    # CREATE ORDER
    # ============================================================

    async def create(
        self,
        db: AsyncSession,
        data: OrderCreate,
        current_user: User,
    ) -> Order:
        """
        Create an order and immediately consume all selected inventory materials.

        Everything is handled inside one database transaction:

            Order
            + Invoice
            + Inventory deductions
            + Stock movements
            + Material requirements

        If anything fails, the entire transaction is rolled back.

        Inventory quantity input supports:

            "12"

        and, for feet-based inventory:

            "3*4"
            "3 x 4"
            "3x4"

        Example:
            Fabric = 50 feet

            Staff enters:

                3*4

            Backend calculates:

                3 x 4 = 12 feet

            Inventory becomes:

                50 - 12 = 38 feet

        """
        # ========================================================
        # VERIFY CUSTOMER
        # ========================================================

        customer = await self.customer_repo.get_by_id(
            db,
            str(data.customer_id),
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found",
            )

        try:
            # ====================================================
            # DETERMINE INITIAL ORDER STATUS
            # ====================================================

            initial_status = (
                OrderStatus.COMPLETED
                if data.order_type == OrderType.PRINT
                else OrderStatus.RECEIVED
            )

            # ====================================================
            # CREATE ORDER
            # ====================================================

            order = Order(
                customer_id=data.customer_id,
                order_type=data.order_type,
                title=data.title,
                description=data.description,
                status=initial_status,
                total_amount=data.total_amount,
                due_date=data.due_date,
            )

            if data.order_type == OrderType.PRINT:
                order.completed_at = datetime.now(UTC)

            db.add(order)

            # We need the generated order ID for:
            #
            # - StockMovement
            # - OrderMaterialRequirement
            # - Invoice
            #
            await db.flush()

            # ====================================================
            # CREATE INVOICE
            # ====================================================

            invoice = Invoice(
                order_id=order.id,
                subtotal=data.total_amount,
                discount=0,
                tax=0,
                total_amount=data.total_amount,
                amount_paid=0,
                balance_due=data.total_amount,
                status=(
                    InvoiceStatus.PAID
                    if data.total_amount == 0
                    else InvoiceStatus.UNPAID
                ),
            )

            db.add(invoice)

            # ====================================================
            # NO INVENTORY SELECTED
            # ====================================================

            if not data.inventory_items:
                await db.commit()

                created_order = await self.repo.get_by_id(
                    db,
                    str(order.id),
                )

                if not created_order:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Order could not be loaded after creation",
                    )

                return created_order

            # ====================================================
            # GROUP REQUESTS BY INVENTORY ITEM
            # ====================================================
            #
            # We intentionally do not calculate quantities yet.
            #
            # We first need to load each inventory item so that we
            # know its unit.
            #
            # Example:
            #
            # Fabric:
            #   3*4
            #
            # Fabric:
            #   2*5
            #
            # These will eventually become:
            #
            #   12 + 10 = 22 feet
            #
            # ====================================================

            requested_items: dict[str, list[OrderInventoryItemCreate]] = {}

            for material in data.inventory_items:
                item_id = str(material.inventory_item_id)

                requested_items.setdefault(
                    item_id,
                    [],
                ).append(material)

            # ====================================================
            # LOCK ALL INVENTORY ITEMS
            # ====================================================
            #
            # Every requested inventory row is locked before stock
            # is checked or deducted.
            #
            # Sorting IDs gives concurrent orders a consistent
            # locking order and reduces deadlock risk.
            #
            # ====================================================

            locked_items: dict[str, InventoryItem] = {}

            for item_id in sorted(requested_items.keys()):
                result = await db.execute(
                    select(InventoryItem)
                    .where(
                        InventoryItem.id == item_id,
                    )
                    .with_for_update()
                )

                item = result.scalar_one_or_none()

                if not item:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(f"Inventory item {item_id} not found."),
                    )

                locked_items[item_id] = item

            # ====================================================
            # CALCULATE ACTUAL QUANTITIES
            # ====================================================
            #
            # Example:
            #
            # inventory unit = feet
            #
            # input_quantity = "3*4"
            #
            # result = 12
            #
            # ====================================================

            aggregated_items: dict[str, int] = {}

            input_values: dict[str, list[str]] = {}

            for item_id, materials in requested_items.items():
                item = locked_items[item_id]

                for material in materials:
                    calculated_quantity = self._calculate_inventory_quantity(
                        unit=item.unit,
                        input_quantity=material.input_quantity,
                    )

                    aggregated_items[item_id] = (
                        aggregated_items.get(
                            item_id,
                            0,
                        )
                        + calculated_quantity
                    )

                    input_values.setdefault(
                        item_id,
                        [],
                    ).append(
                        material.input_quantity.strip(),
                    )

            # ====================================================
            # CHECK ALL STOCK BEFORE DEDUCTING ANYTHING
            # ====================================================
            #
            # This is important.
            #
            # If one material has insufficient stock, we don't
            # deduct anything from the other materials.
            #
            # ====================================================

            for item_id, required_quantity in aggregated_items.items():
                item = locked_items[item_id]

                if item.quantity < required_quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock for '{item.name}'. "
                            f"Required: {required_quantity} {item.unit}, "
                            f"Available: {item.quantity} {item.unit}."
                        ),
                    )

            # ====================================================
            # DEDUCT INVENTORY
            # ====================================================

            for item_id, required_quantity in aggregated_items.items():
                item = locked_items[item_id]

                # ------------------------------------------------
                # DEDUCT FROM INVENTORY
                # ------------------------------------------------

                item.quantity -= required_quantity

                # ------------------------------------------------
                # ORIGINAL STAFF INPUT
                # ------------------------------------------------

                entered_values = input_values.get(
                    item_id,
                    [],
                )

                if entered_values:
                    input_description = ", ".join(
                        entered_values,
                    )

                    quantity_description = f"{input_description} = {required_quantity}"
                else:
                    quantity_description = str(
                        required_quantity,
                    )

                # ------------------------------------------------
                # MOVEMENT REASON
                # ------------------------------------------------

                movement_reason = (
                    f"Used for order '{order.title}' "
                    f"by {customer.name}. "
                    f"Quantity: "
                    f"{quantity_description} "
                    f"{item.unit}"
                )

                # ------------------------------------------------
                # CREATE STOCK OUT MOVEMENT
                # ------------------------------------------------

                movement = StockMovement(
                    item_id=item.id,
                    quantity=required_quantity,
                    movement_type=MovementType.STOCK_OUT,
                    unit_selling_price=item.unit_selling_price,
                    reason=movement_reason,
                    recorded_by=current_user.id,
                    order_id=order.id,
                )

                db.add(movement)

                # ------------------------------------------------
                # CREATE MATERIAL REQUIREMENT
                # ------------------------------------------------
                #
                # Because this material is consumed immediately:
                #
                # required_quantity == consumed_quantity
                #
                # remaining_quantity == 0
                #
                # ------------------------------------------------

                requirement = OrderMaterialRequirement(
                    order_id=order.id,
                    inventory_item_id=item.id,
                    required_quantity=required_quantity,
                    consumed_quantity=required_quantity,
                    unit_selling_price=item.unit_selling_price,
                )

                db.add(requirement)

            # ====================================================
            # COMMIT EVERYTHING TOGETHER
            # ====================================================
            #
            # Order
            # Invoice
            # Inventory deduction
            # Stock movement
            # Material requirement
            #
            # all become permanent together.
            #
            # ====================================================

            await db.commit()

        # ========================================================
        # EXPECTED BUSINESS ERRORS
        # ========================================================

        except HTTPException:
            await db.rollback()
            raise

        # ========================================================
        # UNEXPECTED ERRORS
        # ========================================================

        except Exception:
            await db.rollback()
            raise

        # ========================================================
        # RELOAD CREATED ORDER
        # ========================================================

        created_order = await self.repo.get_by_id(
            db,
            str(order.id),
        )

        if not created_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order could not be loaded after creation",
            )

        return created_order

    # ============================================================
    # GET ALL ORDERS
    # ============================================================

    async def get_all(
        self,
        db: AsyncSession,
        pagination,
        search,
        status,
        order_type,
    ):
        items, total = await self.repo.get_all(
            db,
            page=pagination.page,
            limit=pagination.limit,
            search=search,
            status=status,
            order_type=order_type,
        )

        return build_page(
            items=items,
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    # ============================================================
    # GET ORDER BY ID
    # ============================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        order = await self.repo.get_by_id(
            db,
            order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return order

    # ============================================================
    # UPDATE ORDER
    # ============================================================

    async def update(
        self,
        db: AsyncSession,
        order_id: str,
        data: OrderUpdate,
        current_user,
    ):
        order = await self.get_by_id(
            db,
            order_id,
        )

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        try:
            # ========================================================
            # ORDER TYPE
            # ========================================================

            if data.order_type is not None:
                if data.order_type != order.order_type:
                    production_folder = await self.production_repo.get_by_order_id(
                        db,
                        str(order.id),
                    )

                    if production_folder:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                "Order type cannot be changed because "
                                "a production folder already exists for this order."
                            ),
                        )

                    if order.status not in {
                        OrderStatus.RECEIVED,
                        OrderStatus.REVIEWING,
                    }:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                "Order type cannot be changed "
                                "after the order has entered production."
                            ),
                        )

                    order.order_type = data.order_type

            # ========================================================
            # TITLE
            # ========================================================

            if data.title is not None:
                order.title = data.title

            # ========================================================
            # DESCRIPTION
            # ========================================================

            if data.description is not None:
                order.description = data.description

            # ========================================================
            # STATUS
            # ========================================================

            if data.status is not None:
                order.status = data.status

            # ========================================================
            # DUE DATE
            # ========================================================

            if data.due_date is not None:
                order.due_date = data.due_date

            # ========================================================
            # UPDATE ORDER TOTAL + INVOICE
            # ========================================================

            if data.total_amount is not None:
                invoice = await self.invoice_repo.get_by_order_id(
                    db,
                    order_id,
                )

                if invoice:
                    if data.total_amount < invoice.amount_paid:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                "Order total cannot be less than "
                                "the amount already paid."
                            ),
                        )

                    order.total_amount = data.total_amount

                    invoice.subtotal = data.total_amount
                    invoice.discount = 0
                    invoice.tax = 0
                    invoice.total_amount = data.total_amount
                    invoice.balance_due = data.total_amount - invoice.amount_paid

                    if data.total_amount in (
                        0,
                        invoice.amount_paid,
                    ):
                        invoice.status = InvoiceStatus.PAID
                    elif invoice.amount_paid > 0:
                        invoice.status = InvoiceStatus.PARTIALLY_PAID
                    else:
                        invoice.status = InvoiceStatus.UNPAID

                else:
                    order.total_amount = data.total_amount

            # ========================================================
            # INVENTORY / MATERIALS
            #
            # data.inventory_items is None:
            #     Do not touch existing inventory.
            #
            # data.inventory_items == []:
            #     Remove all existing materials and return their
            #     consumed quantities to inventory.
            #
            # data.inventory_items contains items:
            #     Make the database match exactly what was supplied.
            # ========================================================

            if data.inventory_items is not None:
                # ----------------------------------------------------
                # Aggregate duplicate requested inventory items
                # ----------------------------------------------------

                requested_materials: dict[str, dict] = {}

                for material in data.inventory_items:
                    item_id = str(material.inventory_item_id)

                    inventory_item = await self.inventory_repo.get_by_id(
                        db,
                        item_id,
                    )

                    if not inventory_item:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=(f"Inventory item {item_id} not found."),
                        )

                    calculated_quantity = self._calculate_inventory_quantity(
                        unit=inventory_item.unit,
                        input_quantity=material.input_quantity,
                    )

                    if item_id in requested_materials:
                        requested_materials[item_id]["quantity"] += calculated_quantity

                        requested_materials[item_id]["input_descriptions"].append(
                            material.input_quantity.strip()
                        )

                    else:
                        requested_materials[item_id] = {
                            "quantity": calculated_quantity,
                            "input_descriptions": [material.input_quantity.strip()],
                        }

                # ----------------------------------------------------
                # Load current material requirements
                # ----------------------------------------------------

                current_result = await db.execute(
                    select(OrderMaterialRequirement)
                    .where(OrderMaterialRequirement.order_id == order.id)
                    .with_for_update()
                )

                current_requirements = current_result.scalars().all()

                current_by_item: dict[
                    str,
                    OrderMaterialRequirement,
                ] = {
                    str(requirement.inventory_item_id): requirement
                    for requirement in current_requirements
                }

                # ----------------------------------------------------
                # Lock every affected inventory item.
                #
                # We lock in sorted ID order to reduce deadlock risk.
                # ----------------------------------------------------

                affected_item_ids = sorted(
                    set(current_by_item.keys()) | set(requested_materials.keys())
                )

                locked_items: dict[str, InventoryItem] = {}

                for item_id in affected_item_ids:
                    inventory_item = await self.inventory_repo.get_by_id_for_update(
                        db,
                        item_id,
                    )

                    if not inventory_item:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=(f"Inventory item {item_id} not found."),
                        )

                    locked_items[item_id] = inventory_item

                # ----------------------------------------------------
                # Calculate every stock change BEFORE modifying stock.
                # This lets us validate all additions first.
                # ----------------------------------------------------

                stock_changes: list[dict] = []

                all_item_ids = set(current_by_item.keys()) | set(
                    requested_materials.keys()
                )

                for item_id in sorted(all_item_ids):
                    inventory_item = locked_items[item_id]

                    current_requirement = current_by_item.get(item_id)

                    current_quantity = (
                        current_requirement.consumed_quantity
                        if current_requirement
                        else 0
                    )

                    requested_data = requested_materials.get(item_id)

                    requested_quantity = (
                        requested_data["quantity"] if requested_data else 0
                    )

                    difference = requested_quantity - current_quantity

                    stock_changes.append(
                        {
                            "item_id": item_id,
                            "inventory_item": inventory_item,
                            "current_requirement": current_requirement,
                            "current_quantity": current_quantity,
                            "requested_quantity": requested_quantity,
                            "difference": difference,
                            "requested_data": requested_data,
                        }
                    )

                # ----------------------------------------------------
                # VALIDATE ALL ADDITIONAL STOCK BEFORE DEDUCTING
                # ----------------------------------------------------

                for change in stock_changes:
                    difference = change["difference"]

                    if difference <= 0:
                        continue

                    inventory_item = change["inventory_item"]

                    if inventory_item.quantity < difference:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Insufficient stock for "
                                f"'{inventory_item.name}'. "
                                f"Available: {inventory_item.quantity} "
                                f"{inventory_item.unit}. "
                                f"Additional required: {difference} "
                                f"{inventory_item.unit}."
                            ),
                        )

                # ----------------------------------------------------
                # APPLY STOCK + REQUIREMENT CHANGES
                # ----------------------------------------------------

                for change in stock_changes:
                    item_id = change["item_id"]
                    inventory_item = change["inventory_item"]
                    current_requirement = change["current_requirement"]
                    current_quantity = change["current_quantity"]
                    requested_quantity = change["requested_quantity"]
                    difference = change["difference"]
                    requested_data = change["requested_data"]

                    # ------------------------------------------------
                    # MATERIAL REMOVED ENTIRELY
                    # ------------------------------------------------

                    if requested_quantity == 0:
                        if current_requirement:
                            returned_quantity = current_quantity

                            if returned_quantity > 0:
                                inventory_item.quantity += returned_quantity

                                db.add(
                                    StockMovement(
                                        item_id=inventory_item.id,
                                        quantity=returned_quantity,
                                        movement_type=MovementType.STOCK_IN,
                                        unit_selling_price=(
                                            inventory_item.unit_selling_price
                                        ),
                                        reason=(
                                            f"Returned from edited order "
                                            f"'{order.title}'. "
                                            f"Material removed from order."
                                        ),
                                        recorded_by=str(current_user.id),
                                        order_id=order.id,
                                    )
                                )

                            await db.delete(current_requirement)

                        continue

                    # ------------------------------------------------
                    # NEW MATERIAL
                    # ------------------------------------------------

                    if current_requirement is None:
                        inventory_item.quantity -= requested_quantity

                        input_descriptions = ", ".join(
                            requested_data["input_descriptions"]
                        )

                        db.add(
                            StockMovement(
                                item_id=inventory_item.id,
                                quantity=requested_quantity,
                                movement_type=MovementType.STOCK_OUT,
                                unit_selling_price=(inventory_item.unit_selling_price),
                                reason=(
                                    f"Used for edited order "
                                    f"'{order.title}'. "
                                    f"Input: {input_descriptions} = "
                                    f"{requested_quantity} "
                                    f"{inventory_item.unit}."
                                ),
                                recorded_by=str(current_user.id),
                                order_id=order.id,
                            )
                        )

                        db.add(
                            OrderMaterialRequirement(
                                order_id=order.id,
                                inventory_item_id=inventory_item.id,
                                required_quantity=requested_quantity,
                                consumed_quantity=requested_quantity,
                                unit_selling_price=(inventory_item.unit_selling_price),
                            )
                        )

                        continue

                    # ------------------------------------------------
                    # EXISTING MATERIAL - NO CHANGE
                    # ------------------------------------------------

                    if difference == 0:
                        current_requirement.required_quantity = requested_quantity
                        current_requirement.consumed_quantity = requested_quantity

                        continue

                    # ------------------------------------------------
                    # EXISTING MATERIAL - MORE REQUIRED
                    # ------------------------------------------------

                    if difference > 0:
                        inventory_item.quantity -= difference

                        input_descriptions = ", ".join(
                            requested_data["input_descriptions"]
                        )

                        db.add(
                            StockMovement(
                                item_id=inventory_item.id,
                                quantity=difference,
                                movement_type=MovementType.STOCK_OUT,
                                unit_selling_price=(inventory_item.unit_selling_price),
                                reason=(
                                    f"Additional material used for "
                                    f"edited order '{order.title}'. "
                                    f"Input: {input_descriptions}. "
                                    f"Previous: {current_quantity} "
                                    f"{inventory_item.unit}; "
                                    f"new total: {requested_quantity} "
                                    f"{inventory_item.unit}."
                                ),
                                recorded_by=str(current_user.id),
                                order_id=order.id,
                            )
                        )

                    # ------------------------------------------------
                    # EXISTING MATERIAL - LESS REQUIRED
                    # ------------------------------------------------

                    else:
                        returned_quantity = abs(difference)

                        inventory_item.quantity += returned_quantity

                        db.add(
                            StockMovement(
                                item_id=inventory_item.id,
                                quantity=returned_quantity,
                                movement_type=MovementType.STOCK_IN,
                                unit_selling_price=(inventory_item.unit_selling_price),
                                reason=(
                                    f"Material returned from edited "
                                    f"order '{order.title}'. "
                                    f"Previous: {current_quantity} "
                                    f"{inventory_item.unit}; "
                                    f"new total: {requested_quantity} "
                                    f"{inventory_item.unit}."
                                ),
                                recorded_by=str(current_user.id),
                                order_id=order.id,
                            )
                        )

                    current_requirement.required_quantity = requested_quantity
                    current_requirement.consumed_quantity = requested_quantity

            # ========================================================
            # SAVE ORDER
            # ========================================================

            await self.repo.update(
                db,
                order,
            )

            await db.flush()

            await db.commit()

        except HTTPException:
            await db.rollback()
            raise

        except Exception:
            await db.rollback()
            raise

        # ============================================================
        # RELOAD
        # ============================================================

        updated_order = await self.repo.get_by_id(
            db,
            order_id,
        )

        if not updated_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return updated_order

    # ============================================================
    # UPLOAD ORDER FILE
    # ============================================================

    async def upload_file(
        self,
        db: AsyncSession,
        order_id: str,
        file: UploadFile,
        current_user: User,
    ):
        order = await self.get_by_id(
            db,
            order_id,
        )

        uploaded = None

        try:
            # ----------------------------------------------------
            # CLOUDINARY
            # ----------------------------------------------------

            uploaded = await self.cloudinary.upload(
                file=file,
                folder=f"printflow/orders/{order.id}",
            )

            # ----------------------------------------------------
            # DATABASE FILE
            # ----------------------------------------------------

            order_file = OrderFile(
                order_id=order.id,
                file_name=uploaded["file_name"],
                file_url=uploaded["url"],
                public_id=uploaded["public_id"],
                resource_type=uploaded["resource_type"],
                file_type=uploaded["file_type"],
                uploaded_by=current_user.id,
            )

            await self.repo.create_file(
                db,
                order_file,
            )

            await db.commit()

            return order_file

        except Exception:
            await db.rollback()

            # ----------------------------------------------------
            # CLEAN UP CLOUDINARY
            # ----------------------------------------------------

            if uploaded and uploaded.get("public_id"):
                try:
                    await self.cloudinary.delete(
                        public_id=uploaded["public_id"],
                        resource_type=uploaded.get("resource_type"),
                    )
                except Exception:
                    pass

            raise

    # ============================================================
    # GET ORDER FILES
    # ============================================================

    async def get_files(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        exists = await self.repo.exists(
            db,
            order_id,
        )

        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return await self.repo.get_files(
            db,
            order_id,
        )

    # ============================================================
    # DELETE ORDER FILE
    # ============================================================

    async def delete_file(
        self,
        db: AsyncSession,
        file_id: str,
        current_user: User,
    ):
        file = await self.repo.get_file(
            db,
            file_id,
        )

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        # --------------------------------------------------------
        # FRONT DESK OWNERSHIP
        # --------------------------------------------------------

        if (
            current_user.role == UserRole.FRONT_DESK
            and file.uploaded_by != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=("You can only delete files you uploaded."),
            )

        try:
            # ----------------------------------------------------
            # CLOUDINARY
            # ----------------------------------------------------

            await self.cloudinary.delete(
                public_id=file.public_id,
                resource_type=file.resource_type,
            )

            # ----------------------------------------------------
            # DATABASE
            # ----------------------------------------------------

            await self.repo.delete_file(
                db,
                file,
            )

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        return {
            "message": "File deleted successfully",
        }

    # ============================================================
    # DELETE ORDER
    # ============================================================

    async def delete(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        # --------------------------------------------------------
        # LOAD ORDER + FILES
        # --------------------------------------------------------

        order = await self.get_by_id(
            db,
            order_id,
        )

        # --------------------------------------------------------
        # DELETE CLOUDINARY FILES
        # --------------------------------------------------------

        try:
            for file in order.files:
                await self.cloudinary.delete(
                    public_id=file.public_id,
                    resource_type=file.resource_type,
                )

            # ----------------------------------------------------
            # DELETE DATABASE ORDER
            # ----------------------------------------------------

            await self.repo.delete(
                db,
                order,
            )

            await db.commit()

        except Exception:
            await db.rollback()
            raise

        return {
            "message": "Order deleted successfully",
        }
