from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class InvoicePDF:
    def generate(
        self,
        invoice,
        order,
        customer,
    ):
        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=(210 * mm, 297 * mm),
            topMargin=15 * mm,
            bottomMargin=15 * mm,
        )

        styles = getSampleStyleSheet()

        story = []

        title_style = styles["Heading1"]
        title_style.textColor = HexColor("#0F172A")

        story.append(
            Paragraph(
                "CHAYDON PRINT INVOICE",
                title_style,
            )
        )

        story.append(Spacer(1, 8))

        story.append(
            Paragraph(
                f"<b>Invoice ID:</b> {invoice.id}",
                styles["Normal"],
            )
        )

        story.append(
            Paragraph(
                f"<b>Customer:</b> {customer.name}",
                styles["Normal"],
            )
        )

        story.append(
            Paragraph(
                f"<b>Phone:</b> {customer.phone or '-'}",
                styles["Normal"],
            )
        )

        story.append(
            Paragraph(
                f"<b>Order:</b> {order.title}",
                styles["Normal"],
            )
        )

        story.append(Spacer(1, 12))

        table = Table(
            [
                [
                    "Description",
                    "Amount (₦)",
                ],
                [
                    order.title,
                    f"{invoice.total_amount:,.2f}",
                ],
            ],
            colWidths=[
                120 * mm,
                50 * mm,
            ],
        )

        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        HexColor("#0F172A"),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        HexColor("#FFFFFF"),
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        HexColor("#CBD5E1"),
                    ),
                    (
                        "BACKGROUND",
                        (0, 1),
                        (-1, -1),
                        HexColor("#F8FAFC"),
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, 0),
                        10,
                    ),
                ]
            )
        )

        story.append(table)

        story.append(Spacer(1, 12))

        summary = Table(
            [
                [
                    "Subtotal",
                    f"₦{invoice.subtotal:,.2f}",
                ],
                [
                    "Discount",
                    f"₦{invoice.discount:,.2f}",
                ],
                [
                    "Tax",
                    f"₦{invoice.tax:,.2f}",
                ],
                [
                    "Total",
                    f"₦{invoice.total_amount:,.2f}",
                ],
                [
                    "Paid",
                    f"₦{invoice.amount_paid:,.2f}",
                ],
                [
                    "Balance",
                    f"₦{invoice.balance_due:,.2f}",
                ],
                [
                    "Status",
                    invoice.status.value,
                ],
            ],
            colWidths=[
                120 * mm,
                50 * mm,
            ],
        )

        summary.setStyle(
            TableStyle(
                [
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        HexColor("#CBD5E1"),
                    ),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, -1),
                        HexColor("#F1F5F9"),
                    ),
                ]
            )
        )

        story.append(summary)

        story.append(Spacer(1, 20))

        story.append(
            Paragraph(
                "Thank you for choosing PrintFlow.",
                styles["Italic"],
            )
        )

        doc.build(story)

        buffer.seek(0)

        return buffer
