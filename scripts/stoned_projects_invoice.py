"""
Generate an invoice PDF for Stoned Projects LLC and (optionally) send it via
Google Drive permission notification (sends a link to the recipient email).

Designed for the "stashbox" service account JSON present in:
  E:/secrets/gcp/sa.json

Note: Drive permission notification emails include a link; they are not classic
email attachments.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def money(value: float) -> str:
    return f"${value:,.2f}"


def generate_invoice_pdf(out_path: str) -> str:
    # Local import so the script can show a clearer error if reportlab is missing.
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    # Data (from user request)
    vendor_name = "Stoned Projects LLC"
    vendor_email = "Alexstonedz@stonedprojects.com"
    vendor_phone = "(580)-768-0879"

    invoice_date = "10/15/2024"
    invoice_number = "SP-2024-1015"

    bill_to = "Leigha M. Saavedra"
    description = "Custom PC Build"
    line_amount = 2500.0
    total_amount = 2500.0

    # Long-form note. We'll word-wrap during rendering to avoid any boundary overlap.
    note_text = (
        "This invoice supports the purchase of a custom customer office PC build "
        "for business use. Please retain this document for tax deductions and CPA "
        "record-keeping."
    )

    # --- Layout ---
    page_w, page_h = letter  # 612 x 792 points
    c = canvas.Canvas(out_path, pagesize=letter)

    # Colors (simple but "official" looking)
    header_blue = (20 / 255, 54 / 255, 105 / 255)  # deep blue
    black = (0, 0, 0)

    def wrap_text(
        text: str,
        *,
        max_width: float,
        font_name: str,
        font_size: int,
    ) -> list[str]:
        """Simple word-wrap for reportlab canvas text."""
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for w in words:
            probe = " ".join(current + [w])
            if c.stringWidth(probe, font_name, font_size) <= max_width:
                current.append(w)
                continue
            if current:
                lines.append(" ".join(current))
            current = [w]
        if current:
            lines.append(" ".join(current))
        return lines

    # Header block
    margin_x = 44
    c.setStrokeColor(header_blue)
    c.setLineWidth(0.7)
    c.roundRect(
        margin_x,
        # Move the header container down so its bottom border doesn't visually
        # intersect the vendor contact text (phone/email).
        page_h - 160,
        page_w - margin_x * 2,
        92,
        10,
        stroke=1,
        fill=0,
    )

    # Logo (simple lettermark: SP in a circle)
    logo_x = margin_x + 28
    logo_y = page_h - 92
    logo_r = 22
    c.setFillColor(header_blue)
    c.circle(logo_x, logo_y, logo_r, stroke=0, fill=1)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(logo_x, logo_y - 4, "SP")

    # Vendor name + contact
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin_x + 78, page_h - 98, vendor_name)
    c.setFont("Helvetica", 10)
    # Nudge up so the header border stroke never touches digits.
    c.drawString(margin_x + 78, page_h - 112, f"Email: {vendor_email}")
    c.drawString(margin_x + 78, page_h - 123, f"Phone: {vendor_phone}")

    # Invoice meta (right side)
    # Right-align values so they never run past the border/page edge.
    meta_right_x = page_w - margin_x - 12
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(meta_right_x, page_h - 78, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(meta_right_x - 115, page_h - 98, "Invoice #")
    c.drawRightString(meta_right_x, page_h - 98, invoice_number)
    c.drawString(meta_right_x - 115, page_h - 113, "Invoice Date")
    c.drawRightString(meta_right_x, page_h - 113, invoice_date)
    c.drawString(meta_right_x - 115, page_h - 128, "Amount Due")
    c.drawRightString(meta_right_x, page_h - 128, money(total_amount))

    # Billing section
    c.setFont("Helvetica-Bold", 12)
    # Extra whitespace above so no rules intersect this heading.
    c.drawString(margin_x, page_h - 186, "Bill To:")
    c.setFont("Helvetica", 12)
    c.drawString(margin_x + 60, page_h - 186, bill_to)

    # Table header
    table_top = page_h - 230
    table_left = margin_x
    table_right = page_w - margin_x
    c.setStrokeColor((0.15, 0.15, 0.15))
    c.setLineWidth(1)
    c.rect(table_left, table_top - 40, table_right - table_left, 40, stroke=1, fill=0)

    c.setFont("Helvetica-Bold", 10)
    # Nudge text down to avoid the header border "cutting through" glyph descenders.
    header_text_y = table_top - 31
    c.drawString(table_left + 10, header_text_y, "Description")
    c.drawCentredString(table_left + 240, header_text_y, "Qty")
    c.drawRightString(table_right - 10, header_text_y, "Amount")

    # Row
    c.setFont("Helvetica", 10)
    row_height = 42
    row_y = table_top - 40 - row_height
    c.rect(table_left, row_y, table_right - table_left, row_height, stroke=1, fill=0)

    # Nudge row text down slightly for consistent padding.
    row_text_y = row_y + 16
    c.drawString(table_left + 10, row_text_y, description)
    c.drawCentredString(table_left + 240, row_text_y, "1")
    c.drawRightString(table_right - 10, row_text_y, money(line_amount))

    # Totals
    # Use explicit Y positions relative to the table row to avoid any overlap
    # with horizontal rules/box borders.
    subtotal_y = row_y - 18
    total_y = row_y - 32
    total_amount_y = row_y - 47

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(table_right - 10, subtotal_y, "Subtotal")
    c.drawRightString(table_right - 10, total_y, "Total")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(table_right - 10, total_amount_y, money(total_amount))

    # Note section
    note_top = total_amount_y - 18
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin_x, note_top, "Tax/CPA Record Note")
    c.setFont("Helvetica", 10)
    # Wrap note so it doesn't run past the right edge.
    note_max_width = page_w - margin_x * 2
    wrapped_note = wrap_text(
        note_text,
        max_width=note_max_width,
        font_name="Helvetica",
        font_size=10,
    )
    y = note_top - 16
    line_step = 13
    for line in wrapped_note:
        c.drawString(margin_x, y, line)
        y -= line_step

    # Footer
    footer_y = 50
    c.setStrokeColor(header_blue)
    c.setLineWidth(1)
    c.line(margin_x, footer_y + 18, page_w - margin_x, footer_y + 18)
    c.setFont("Helvetica", 9)
    c.setFillColor(header_blue)
    c.drawString(margin_x, footer_y, f"{vendor_name} | {vendor_email} | {vendor_phone}")

    c.showPage()
    c.save()
    return out_path


def upload_to_drive_and_notify(
    pdf_path: str,
    recipient_email: str,
    folder_id: str,
    service_account_path: str,
) -> dict:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    scopes = ["https://www.googleapis.com/auth/drive.file"]
    creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
    drive = build("drive", "v3", credentials=creds)

    pdf_name = os.path.basename(pdf_path)
    file_metadata = {"name": pdf_name, "parents": [folder_id]}
    media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)

    created = (
        drive.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )
    file_id = created["id"]

    # Grant recipient read access and send notification email (link).
    permission = {"type": "user", "role": "reader", "emailAddress": recipient_email}
    drive.permissions().create(
        fileId=file_id,
        body=permission,
        sendNotificationEmail=True,
    ).execute()

    return {"file_id": file_id, "web_view_link": created.get("webViewLink")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="E:/Repos/scripts/invoices/stoned_projects_invoice_2024-10-15.pdf",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Upload to Google Drive and notify recipient by email (Drive link, not attachment).",
    )
    parser.add_argument("--recipient", default="stoneddollz@stonedprojects.com")
    parser.add_argument(
        "--drive-folder-id",
        default="1HeWcSmtgM4c7NO32j8Fs11_awk7Xz7It",
        help="Drive folder where the stashbox service account has upload access.",
    )
    parser.add_argument(
        "--service-account-json",
        default="E:/secrets/gcp/sa.json",
        help="Service account JSON used for Drive upload/permission.",
    )
    args = parser.parse_args()

    out_path = str(Path(args.out))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    generate_invoice_pdf(out_path)
    print("Generated:", out_path)

    if args.send:
        result = upload_to_drive_and_notify(
            pdf_path=out_path,
            recipient_email=args.recipient,
            folder_id=args.drive_folder_id,
            service_account_path=args.service_account_json,
        )
        print("Upload+notify result:", result)


if __name__ == "__main__":
    main()

