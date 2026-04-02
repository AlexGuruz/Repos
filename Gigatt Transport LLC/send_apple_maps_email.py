"""Send Tom NY permit Apple Maps link to gigatttransport3@gmail.com via Gmail SMTP."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

SECRETS = Path(r"E:\secrets\gigatt imap.txt")
TO = "gigatttransport3@gmail.com"
SUBJECT = "GIGATT MAP ROUTE - Tom NY Permit 3841749 - Apple Maps (search: GIGATT MAP ROUTE)"

# Same origin and destination as Google route. Apple Maps URLs do not support waypoints.
APPLE_MAPS_URL = "https://maps.apple.com/?saddr=41.97686,-75.74225&daddr=43.04834,-78.85371&dirflg=d"

BODY = f"""Tom NY Permit 3841749 - Apple Maps link (same route: Great Bend PA to 1070 Erie Ave North Tonawanda)

Open this link on your iPhone, iPad, or Mac for driving directions in Apple Maps:

{APPLE_MAPS_URL}

Note: Apple Maps does not support multiple waypoints in a single link, so this is origin to destination only. For turn-by-turn that follows every permit stop (23 waypoints), use the Google Maps link from the other email, or load the GPX file (Tom-NY-permit-route-EXACT-TRACK.gpx) into a compatible app.
"""


def main():
    lines = SECRETS.read_text().strip().splitlines()
    password_line = lines[0].strip()
    from_email = lines[1].strip() if len(lines) > 1 else ""
    password = password_line.replace(" ", "")

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = TO
    msg["Subject"] = SUBJECT
    msg.attach(MIMEText(BODY, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(from_email, password)
        s.sendmail(from_email, [TO], msg.as_string())
    print(f"Sent Apple Maps link to {TO}")


if __name__ == "__main__":
    main()
