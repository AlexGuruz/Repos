from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def money(value: float) -> str:
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def generate_invoice(output_path: Path) -> None:
    c = canvas.Canvas(str(output_path), pagesize=LETTER)
    width, height = LETTER

    margin = 0.75 * inch
    y = height - margin

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(margin, y, "INVOICE")
    y -= 0.35 * inch

    c.setFont("Helvetica", 11)
    c.drawString(margin, y, f"Invoice Date: {date.today().isoformat()}")
    y -= 0.20 * inch
    c.drawString(margin, y, "Invoice Number: INV-2026-0314-001")
    y -= 0.35 * inch

    # From / Bill To
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "From")
    c.drawString(width / 2, y, "Bill To")
    y -= 0.20 * inch

    c.setFont("Helvetica", 11)
    c.drawString(margin, y, "Stoned Projects LLC")
    c.drawString(width / 2, y, "Leigha M. Saavedara")
    y -= 0.45 * inch

    # Line item table
    table_x = margin
    table_w = width - (2 * margin)
    row_h = 0.32 * inch
    col_desc = table_w * 0.65
    col_qty = table_w * 0.10
    col_unit = table_w * 0.12
    col_total = table_w * 0.13

    item_description = "Prebuilt PC and Accessories kit"
    qty = 1
    unit_price = -1000.00
    line_total = qty * unit_price

    c.setFillColor(colors.HexColor("#f3f4f6"))
    c.rect(table_x, y - row_h, table_w, row_h, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(table_x + 6, y - 0.22 * inch, "Description")
    c.drawString(table_x + col_desc + 6, y - 0.22 * inch, "Qty")
    c.drawString(table_x + col_desc + col_qty + 6, y - 0.22 * inch, "Unit Price")
    c.drawString(table_x + col_desc + col_qty + col_unit + 6, y - 0.22 * inch, "Amount")

    y -= row_h
    c.rect(table_x, y - row_h, table_w, row_h, stroke=1, fill=0)
    c.setFont("Helvetica", 10)
    c.drawString(table_x + 6, y - 0.22 * inch, item_description)
    c.drawRightString(table_x + col_desc + col_qty - 6, y - 0.22 * inch, str(qty))
    c.drawRightString(table_x + col_desc + col_qty + col_unit - 6, y - 0.22 * inch, money(unit_price))
    c.drawRightString(table_x + table_w - 6, y - 0.22 * inch, money(line_total))

    y -= row_h + 0.30 * inch

    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(table_x + table_w, y, f"Total Due: {money(line_total)}")

    y -= 0.55 * inch
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(margin, y, "Amount shown as requested: negative one thousand dollars.")

    c.showPage()
    c.save()


if __name__ == "__main__":
    invoices_dir = Path(__file__).resolve().parent.parent / "reports" / "invoices"
    invoices_dir.mkdir(parents=True, exist_ok=True)
    output_file = invoices_dir / "invoice_stoned-projects_to_leigha-saavedara.pdf"
    generate_invoice(output_file)
    print(output_file)
