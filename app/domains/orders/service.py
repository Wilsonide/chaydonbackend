import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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

    MONEY = Decimal("0.01")

    @classmethod
    def _money(cls, value) -> Decimal:
        """Normalize monetary values to two decimal places."""
        return Decimal(str(value or 0)).quantize(
            cls.MONEY,
            rounding=ROUND_HALF_UP,
        )

    # Supports:
    #   3x2
    #   3x2x2
    #   3 x 2 x 2
    #   3×2×2
    #   3*2*2
    #
    # The third value, when present, is the number of copies.
    _DIMENSION_PATTERN = re.compile(
        r"^\s*"
        r"(\d+(?:\.\d+)?)"
        r"\s*(?:\*|x|X|×)\s*"
        r"(\d+(?:\.\d+)?)"
        r"(?:\s*(?:\*|x|X|×)\s*(\d+(?:\.\d+)?))?"
        r"\s*$"
    )

    # ============================================================
    # INPUT HELPERS
    # ============================================================

    @staticmethod
    def _material_input(
        material: OrderInventoryItemCreate,
    ) -> str:
        """Return the exact input to calculate and preserve."""

        raw = material.input_quantity

        if raw is None:
            if material.quantity is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Provide either quantity or input_quantity "
                        "for each inventory item."
                    ),
                )

            raw = str(material.quantity)

        raw = raw.strip()

        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inventory quantity cannot be empty.",
            )

        return raw

    @classmethod
    def _validate_discount(
        cls,
        *,
        item: InventoryItem,
        discount_amount: Decimal,
        required_quantity: int = 1,
    ) -> Decimal:
        """
        Validate one fixed monetary discount against the total.

        cost of the requested inventory quantity.

        The discount is applied once to the entire material total,
        not separately to each inventory unit.
        """
        try:
            discount = cls._money(discount_amount)
            unit_price = cls._money(item.unit_selling_price)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid inventory price or discount.",
            ) from exc

        if not discount.is_finite() or not unit_price.is_finite():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inventory price and discount must be finite values.",
            )

        if unit_price < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{item.name}' has an invalid unit selling price.",
            )

        if discount < Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discount cannot be negative.",
            )

        if required_quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Required inventory quantity must be greater than zero.",
            )

        gross_total = cls._money(unit_price * required_quantity)

        if discount > gross_total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Discount for '{item.name}' cannot exceed "
                    f"the total material cost of ₦{gross_total:,.2f}."
                ),
            )

        return discount

    @staticmethod
    def _dimension_input(
        expressions: list[str],
    ) -> str:
        """Preserve the expressions in the order staff entered them."""
        return ", ".join(expressions)

    def _calculate_inventory_quantity(
        self,
        *,
        unit: str,
        input_quantity: str,
    ) -> int:
        """
        Calculate the actual inventory quantity.

        Plain quantity:
            12 -> 12

        Dimensions:
            3x2 -> 6
            3x2x2 -> 12
            3x2x4 -> 24

        Multiple expressions:
            3x2x2, 4x5x3 -> 12 + 60 = 72

        The first two values are dimensions.
        The optional third value is the number of copies.

        Dimension calculations are supported only for feet-based
        inventory. The final stock quantity must be a positive integer.
        """
        raw = (input_quantity or "").strip()

        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inventory quantity cannot be empty.",
            )

        # Plain numeric quantities retain the existing behavior.
        if raw.isdigit():
            quantity = int(raw)

            if quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Inventory quantity must be greater than zero.",
                )

            return quantity

        # Dimensions are allowed only for feet-based items.
        normalized_unit = unit.strip().lower()

        if normalized_unit not in {"feet", "foot", "ft"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Dimension input '{raw}' is not valid for inventory "
                    f"measured in '{unit}'. Dimension calculations are "
                    "supported only for feet."
                ),
            )

        expressions = [part.strip() for part in raw.split(",")]

        if not expressions or any(not part for part in expressions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid dimension input. Enter complete expressions "
                    "separated by commas, for example '3x2x2, 4x5x3'."
                ),
            )

        total = Decimal("0")

        for expression in expressions:
            match = self._DIMENSION_PATTERN.fullmatch(expression)

            if not match:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid dimension expression '{expression}'. "
                        "Use 'width x height' or "
                        "'width x height x copies'."
                    ),
                )

            try:
                width = Decimal(match.group(1))
                height = Decimal(match.group(2))
                copies = Decimal(match.group(3) or "1")
            except InvalidOperation as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid dimension expression '{expression}'.",
                ) from exc

            if not all(value.is_finite() for value in (width, height, copies)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Dimensions and copies must be finite numbers.",
                )

            if width <= 0 or height <= 0 or copies <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=("Dimensions and copy counts must be greater than zero."),
                )

            if copies != copies.to_integral_value():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The copy count must be a whole number.",
                )

            total += width * height * copies

        if total != total.to_integral_value():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"'{raw}' calculates to {total}. "
                    "Inventory quantities must be whole numbers."
                ),
            )

        quantity = int(total)

        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("Calculated inventory quantity must be greater than zero."),
            )

        return quantity

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
        Create an order, invoice, material requirements and stock movements.

        Selected inventory is deducted immediately, matching the existing
        PrintFlow workflow. All database changes are committed together.
        """
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
            initial_status = (
                OrderStatus.COMPLETED
                if data.order_type == OrderType.PRINT
                else OrderStatus.RECEIVED
            )

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
            await db.flush()

            invoice = Invoice(
    order_id=order.id,
    subtotal=data.total_amount,
    discount=0,
    tax=0,
    total_amount=data.total_amount,
    amount_paid=(
        data.total_amount
        if data.order_type == OrderType.PRINT
        else Decimal("0.00")
    ),
    balance_due=(
        Decimal("0.00")
        if data.order_type == OrderType.PRINT
        else data.total_amount
    ),
    status=(
        InvoiceStatus.PAID
        if data.order_type == OrderType.PRINT
        or data.total_amount == 0
        else InvoiceStatus.UNPAID
    ),
)



            db.add(invoice)

            if data.inventory_items:
                requested_items: dict[
                    str,
                    list[OrderInventoryItemCreate],
                ] = {}

                for material in data.inventory_items:
                    item_id = str(material.inventory_item_id)

                    requested_items.setdefault(
                        item_id,
                        [],
                    ).append(material)

                # Lock inventory rows in a consistent order.
                locked_items: dict[str, InventoryItem] = {}

                for item_id in sorted(requested_items):
                    result = await db.execute(
                        select(InventoryItem)
                        .where(InventoryItem.id == item_id)
                        .with_for_update()
                    )

                    item = result.scalar_one_or_none()

                    if not item:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Inventory item {item_id} not found.",
                        )

                    locked_items[item_id] = item

                aggregated_items: dict[str, int] = {}
                input_values: dict[str, list[str]] = {}
                discount_values: dict[str, Decimal] = {}

                # Calculate quantities and normalize discounts.
                for item_id, materials in requested_items.items():
                    item = locked_items[item_id]

                    for material in materials:
                        raw_input = self._material_input(material)

                        quantity = self._calculate_inventory_quantity(
                            unit=item.unit,
                            input_quantity=raw_input,
                        )

                        try:
                            discount = self._money(material.discount_amount)
                        except (
                            InvalidOperation,
                            ValueError,
                            TypeError,
                        ) as exc:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid inventory price or discount.",
                            ) from exc

                        if not discount.is_finite():
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Discount must be a finite value.",
                            )

                        if discount < Decimal("0.00"):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Discount cannot be negative.",
                            )

                        existing_discount = discount_values.get(item_id)

                        if (
                            existing_discount is not None
                            and existing_discount != discount
                        ):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=(
                                    f"'{item.name}' was submitted with "
                                    "different discounts. Use one discount "
                                    "per inventory item in an order."
                                ),
                            )

                        discount_values[item_id] = discount

                        aggregated_items[item_id] = (
                            aggregated_items.get(item_id, 0) + quantity
                        )

                        input_values.setdefault(
                            item_id,
                            [],
                        ).append(raw_input)

                # Validate each discount against the aggregated material cost.
                for item_id, required_quantity in aggregated_items.items():
                    item = locked_items[item_id]

                    discount_values[item_id] = self._validate_discount(
                        item=item,
                        discount_amount=discount_values[item_id],
                        required_quantity=required_quantity,
                    )

                # Validate all stock before deducting anything.
                for item_id, required_quantity in aggregated_items.items():
                    item = locked_items[item_id]

                    if item.quantity < required_quantity:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Insufficient stock for '{item.name}'. "
                                f"Required: {required_quantity} {item.unit}, "
                                f"available: {item.quantity} {item.unit}."
                            ),
                        )

                # Deduct stock and persist movement/requirement details.
                for item_id, required_quantity in aggregated_items.items():
                    item = locked_items[item_id]
                    item.quantity -= required_quantity

                    dimension_input = self._dimension_input(input_values[item_id])
                    discount = discount_values[item_id]

                    movement_reason = (
                        f"Used for order '{order.title}' by {customer.name}. "
                        f"Input: {dimension_input}. "
                        f"Quantity deducted: {required_quantity} {item.unit}."
                    )

                    db.add(
                        StockMovement(
                            item_id=item.id,
                            quantity=required_quantity,
                            movement_type=MovementType.STOCK_OUT,
                            unit_selling_price=item.unit_selling_price,
                            discount_amount=discount,
                            dimension_input=dimension_input,
                            reason=movement_reason,
                            recorded_by=current_user.id,
                            order_id=order.id,
                        )
                    )

                    db.add(
                        OrderMaterialRequirement(
                            order_id=order.id,
                            inventory_item_id=item.id,
                            required_quantity=required_quantity,
                            consumed_quantity=required_quantity,
                            unit_selling_price=item.unit_selling_price,
                            discount_amount=discount,
                            dimension_input=dimension_input,
                        )
                    )

            await db.commit()

        except HTTPException:
            await db.rollback()
            raise

        except Exception:
            await db.rollback()
            raise

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
        current_user: User,
    ):
        order = await self.get_by_id(db, order_id)

        try:
            # --------------------------------------------------------
            # ORDER TYPE
            # --------------------------------------------------------
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
                                "a production folder already exists."
                            ),
                        )

                    if order.status not in {
                        OrderStatus.RECEIVED,
                        OrderStatus.REVIEWING,
                    }:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                "Order type cannot be changed after "
                                "the order has entered production."
                            ),
                        )

                    order.order_type = data.order_type

            if data.title is not None:
                order.title = data.title

            if data.description is not None:
                order.description = data.description

            if data.status is not None:
                order.status = data.status

            if data.due_date is not None:
                order.due_date = data.due_date

            # --------------------------------------------------------
            # ORDER TOTAL AND INVOICE
            # --------------------------------------------------------
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

                    if data.total_amount == invoice.amount_paid:
                        invoice.status = InvoiceStatus.PAID
                    elif invoice.amount_paid > 0:
                        invoice.status = InvoiceStatus.PARTIALLY_PAID
                    else:
                        invoice.status = InvoiceStatus.UNPAID
                else:
                    order.total_amount = data.total_amount

            # --------------------------------------------------------
            # INVENTORY RECONCILIATION
            # --------------------------------------------------------
            if data.inventory_items is not None:
                requested_materials: dict[str, dict] = {}

                # ----------------------------------------------------
                # RESOLVE MATERIALS AND AGGREGATE QUANTITIES
                # ----------------------------------------------------
                for material in data.inventory_items:
                    item_id = str(material.inventory_item_id)

                    inventory_item = await self.inventory_repo.get_by_id(
                        db,
                        item_id,
                    )

                    if not inventory_item:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Inventory item {item_id} not found.",
                        )

                    raw_input = material.input_quantity.strip()

                    calculated_quantity = self._calculate_inventory_quantity(
                        unit=inventory_item.unit,
                        input_quantity=raw_input,
                    )

                    try:
                        discount = self._money(material.discount_amount)
                    except (InvalidOperation, ValueError, TypeError) as exc:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid inventory price or discount.",
                        ) from exc

                    if not discount.is_finite():
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Discount must be a finite value.",
                        )

                    if discount < Decimal("0.00"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Discount cannot be negative.",
                        )

                    if item_id in requested_materials:
                        existing = requested_materials[item_id]

                        if existing["discount_amount"] != discount:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=(
                                    f"'{inventory_item.name}' has conflicting "
                                    "discounts. Use one discount per item."
                                ),
                            )

                        existing["quantity"] += calculated_quantity
                        existing["input_descriptions"].append(raw_input)

                    else:
                        requested_materials[item_id] = {
                            "quantity": calculated_quantity,
                            "input_descriptions": [raw_input],
                            "discount_amount": discount,
                        }

                # ----------------------------------------------------
                # LOCK EXISTING REQUIREMENTS
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
                # LOCK ALL AFFECTED INVENTORY ITEMS
                # ----------------------------------------------------
                affected_item_ids = sorted(
                    set(current_by_item) | set(requested_materials)
                )

                locked_items: dict[str, InventoryItem] = {}

                for item_id in affected_item_ids:
                    item = await self.inventory_repo.get_by_id_for_update(
                        db,
                        item_id,
                    )

                    if not item:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Inventory item {item_id} not found.",
                        )

                    locked_items[item_id] = item

                # ----------------------------------------------------
                # VALIDATE DISCOUNTS AGAINST UPDATED TOTAL COST
                # ----------------------------------------------------
                for item_id, requested in requested_materials.items():
                    item = locked_items[item_id]

                    requested["discount_amount"] = self._validate_discount(
                        item=item,
                        discount_amount=requested["discount_amount"],
                        required_quantity=requested["quantity"],
                    )

                # ----------------------------------------------------
                # BUILD STOCK CHANGES
                # ----------------------------------------------------
                stock_changes: list[dict] = []

                for item_id in affected_item_ids:
                    requirement = current_by_item.get(item_id)
                    requested = requested_materials.get(item_id)

                    current_quantity = (
                        requirement.consumed_quantity if requirement else 0
                    )

                    requested_quantity = requested["quantity"] if requested else 0

                    stock_changes.append(
                        {
                            "item_id": item_id,
                            "item": locked_items[item_id],
                            "requirement": requirement,
                            "current_quantity": current_quantity,
                            "requested_quantity": requested_quantity,
                            "difference": (requested_quantity - current_quantity),
                            "requested": requested,
                        }
                    )

                # ----------------------------------------------------
                # VALIDATE ALL ADDITIONAL STOCK BEFORE DEDUCTIONS
                # ----------------------------------------------------
                for change in stock_changes:
                    difference = change["difference"]

                    if difference <= 0:
                        continue

                    item = change["item"]

                    if item.quantity < difference:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Insufficient stock for '{item.name}'. "
                                f"Available: {item.quantity} {item.unit}. "
                                f"Additional required: {difference} {item.unit}."
                            ),
                        )

                # ----------------------------------------------------
                # APPLY STOCK ADJUSTMENTS
                # ----------------------------------------------------
                for change in stock_changes:
                    item = change["item"]
                    requirement = change["requirement"]
                    requested = change["requested"]

                    requested_quantity = change["requested_quantity"]
                    current_quantity = change["current_quantity"]
                    difference = change["difference"]

                    # ------------------------------------------------
                    # MATERIAL REMOVED
                    # ------------------------------------------------
                    if requested_quantity == 0:
                        if requirement:
                            if current_quantity > 0:
                                item.quantity += current_quantity

                                db.add(
                                    StockMovement(
                                        item_id=item.id,
                                        quantity=current_quantity,
                                        movement_type=MovementType.STOCK_IN,
                                        unit_selling_price=(
                                            requirement.unit_selling_price
                                        ),
                                        discount_amount=self._money(
                                            requirement.discount_amount
                                        ),
                                        dimension_input=(requirement.dimension_input),
                                        reason=(
                                            f"Returned from edited order "
                                            f"'{order.title}'. Material removed."
                                        ),
                                        recorded_by=current_user.id,
                                        order_id=order.id,
                                    )
                                )

                            await db.delete(requirement)

                        continue

                    input_description = self._dimension_input(
                        requested["input_descriptions"]
                    )

                    new_discount = requested["discount_amount"]

                    # ------------------------------------------------
                    # NEW MATERIAL
                    # ------------------------------------------------
                    if requirement is None:
                        item.quantity -= requested_quantity

                        db.add(
                            StockMovement(
                                item_id=item.id,
                                quantity=requested_quantity,
                                movement_type=MovementType.STOCK_OUT,
                                unit_selling_price=item.unit_selling_price,
                                discount_amount=new_discount,
                                dimension_input=input_description,
                                reason=(
                                    f"Material added to edited order "
                                    f"'{order.title}'. Input: {input_description}. "
                                    f"Quantity deducted: {requested_quantity} "
                                    f"{item.unit}."
                                ),
                                recorded_by=current_user.id,
                                order_id=order.id,
                            )
                        )

                        db.add(
                            OrderMaterialRequirement(
                                order_id=order.id,
                                inventory_item_id=item.id,
                                required_quantity=requested_quantity,
                                consumed_quantity=requested_quantity,
                                unit_selling_price=item.unit_selling_price,
                                discount_amount=new_discount,
                                dimension_input=input_description,
                            )
                        )

                        continue

                    # ------------------------------------------------
                    # EXISTING MATERIAL - MORE REQUIRED
                    # ------------------------------------------------
                    if difference > 0:
                        item.quantity -= difference

                        # The existing discount belongs to the existing
                        # requirement. Do not record it again on the
                        # additional stock movement.
                        db.add(
                            StockMovement(
                                item_id=item.id,
                                quantity=difference,
                                movement_type=MovementType.STOCK_OUT,
                                unit_selling_price=item.unit_selling_price,
                                discount_amount=Decimal("0.00"),
                                dimension_input=input_description,
                                reason=(
                                    f"Additional material used for edited "
                                    f"order '{order.title}'. "
                                    f"Input: {input_description}. "
                                    f"Previous quantity: {current_quantity}; "
                                    f"new total: {requested_quantity} {item.unit}."
                                ),
                                recorded_by=current_user.id,
                                order_id=order.id,
                            )
                        )

                    # ------------------------------------------------
                    # EXISTING MATERIAL - LESS REQUIRED
                    # ------------------------------------------------
                    elif difference < 0:
                        returned_quantity = abs(difference)

                        item.quantity += returned_quantity

                        old_discount = self._money(requirement.discount_amount)

                        # Allocate the returned share of the old discount.
                        # Returning the entire quantity returns the full
                        # discount; partial returns are proportional.
                        if returned_quantity == current_quantity:
                            returned_discount = old_discount
                        elif current_quantity > 0:
                            returned_discount = self._money(
                                old_discount
                                * Decimal(returned_quantity)
                                / Decimal(current_quantity)
                            )
                        else:
                            returned_discount = Decimal("0.00")

                        db.add(
                            StockMovement(
                                item_id=item.id,
                                quantity=returned_quantity,
                                movement_type=MovementType.STOCK_IN,
                                unit_selling_price=(requirement.unit_selling_price),
                                discount_amount=returned_discount,
                                dimension_input=requirement.dimension_input,
                                reason=(
                                    f"Material returned from edited order "
                                    f"'{order.title}'. "
                                    f"Previous quantity: {current_quantity}; "
                                    f"new total: {requested_quantity} {item.unit}."
                                ),
                                recorded_by=current_user.id,
                                order_id=order.id,
                            )
                        )

                    # ------------------------------------------------
                    # UPDATE REQUIREMENT
                    # ------------------------------------------------
                    requirement.required_quantity = requested_quantity
                    requirement.consumed_quantity = requested_quantity
                    requirement.unit_selling_price = item.unit_selling_price

                    # The newly entered discount replaces the previous
                    # discount for the entire updated material quantity.
                    requirement.discount_amount = new_discount

                    requirement.dimension_input = input_description

            # --------------------------------------------------------
            # SAVE
            # --------------------------------------------------------
            await self.repo.update(db, order)
            await db.flush()
            await db.commit()

        except HTTPException:
            await db.rollback()
            raise

        except Exception:
            await db.rollback()
            raise

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
        order = await self.get_by_id(db, order_id)
        uploaded = None

        try:
            uploaded = await self.cloudinary.upload(
                file=file,
                folder=f"printflow/orders/{order.id}",
            )

            order_file = OrderFile(
                order_id=order.id,
                file_name=uploaded["file_name"],
                file_url=uploaded["url"],
                public_id=uploaded["public_id"],
                resource_type=uploaded["resource_type"],
                file_type=uploaded["file_type"],
                uploaded_by=current_user.id,
            )

            await self.repo.create_file(db, order_file)
            await db.commit()

            return order_file

        except Exception:
            await db.rollback()

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
        exists = await self.repo.exists(db, order_id)

        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )

        return await self.repo.get_files(db, order_id)

    # ============================================================
    # DELETE ORDER FILE
    # ============================================================

    async def delete_file(
        self,
        db: AsyncSession,
        file_id: str,
        current_user: User,
    ):
        file = await self.repo.get_file(db, file_id)

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        if (
            current_user.role == UserRole.FRONT_DESK
            and file.uploaded_by != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete files you uploaded.",
            )

        try:
            await self.cloudinary.delete(
                public_id=file.public_id,
                resource_type=file.resource_type,
            )

            await self.repo.delete_file(db, file)
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        return {"message": "File deleted successfully"}

    # ============================================================
    # DELETE ORDER
    # ============================================================

    async def delete(
        self,
        db: AsyncSession,
        order_id: str,
    ):
        order = await self.get_by_id(db, order_id)

        try:
            for file in order.files:
                await self.cloudinary.delete(
                    public_id=file.public_id,
                    resource_type=file.resource_type,
                )

            await self.repo.delete(db, order)
            await db.commit()

        except Exception:
            await db.rollback()
            raise

        return {"message": "Order deleted successfully"}
