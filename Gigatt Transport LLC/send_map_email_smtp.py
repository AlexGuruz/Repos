"""Send Tom NY permit map links to gigatttransport3@gmail.com via Gmail SMTP."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

SECRETS = Path(r"E:\secrets\gigatt imap.txt")
EMAIL_BODY = Path(__file__).resolve().parent / "EMAIL-TO-GIGATTTRANSPORTLLC3.txt"

TO = "gigatttransport3@gmail.com"

def main():
    lines = SECRETS.read_text().strip().splitlines()
    password_line = lines[0].strip()
    from_email = lines[1].strip() if len(lines) > 1 else ""
    # App passwords often stored with spaces; remove for login
    password = password_line.replace(" ", "")

    body_path = EMAIL_BODY
    raw = body_path.read_text()
    # Use content after the "COPY EVERYTHING BELOW" line as body
    if "---" in raw:
        parts = raw.split("---", 2)
        body = (parts[2] if len(parts) > 2 else parts[-1]).strip()
    else:
        body = raw
    # Subject: second line starting with SUBJECT:
    subject = "Tom NY Permit 3841749 – GPS route links (Great Bend PA → 1070 Erie Ave North Tonawanda)"
    for line in raw.splitlines():
        if line.upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
            break

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(from_email, password)
        s.sendmail(from_email, [TO], msg.as_string())
    print(f"Sent to {TO}")

if __name__ == "__main__":
    main()
