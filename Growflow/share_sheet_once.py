"""One-off: share the prepackaged flower spreadsheet with alexstonedz@stonedprojects.com."""
import sys
sys.path.insert(0, ".")
from prepackaged_flower_metrics_to_sheet import share_spreadsheet_with_email

SPREADSHEET_ID = "13Wm3UdCdvzw6lpYUDIs-J2UOiRO42oNxE8wKzVyCqRA"
EMAIL = "alexstonedz@stonedprojects.com"
SA_PATH = "E:/secrets/gcp/sa.json"

if __name__ == "__main__":
    try:
        share_spreadsheet_with_email(SA_PATH, SPREADSHEET_ID, EMAIL)
        print("Shared with", EMAIL, "(writer).")
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)
