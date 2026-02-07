from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def update_jgd_main_active():
    """Update JGD's active tab in the main workbook with promoted rules"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    company_id = "JGD"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    # Get rules from database via container - ORDER BY SOURCE FOR ALPHABETICAL ORDER
    import subprocess
    result = subprocess.run([
        "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", "kylo_jgd", 
        "-c", "SELECT rule_json FROM app.rules_active ORDER BY rule_json->>'source';", "-t"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error getting rules from database: {result.stderr}")
        return
    
    # Parse the rules
    rules = []
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            import json
            try:
                rule = json.loads(line.strip())
                rules.append(rule)
            except json.JSONDecodeError:
                continue
    
    print(f"Found {len(rules)} active rules in database")
    
    # Prepare data for active tab - PRESERVE ORIGINAL FORMAT
    # Format: [source, target_sheet, target_header, approved]
    rows = []
    for rule in rules:
        # Keep the original format from database (should be ALL CAPS now)
        rows.append([
            rule.get("source", ""),  # PRESERVE FORMAT
            rule.get("target_sheet", ""),
            rule.get("target_header", ""),
            "TRUE"  # All active rules are approved
        ])
    
    # Clear existing data (keep header)
    active_title = f"{company_id} Active"
    clear_range = f"{active_title}!A2:D1000"
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=clear_range
    ).execute()
    
    # Write new data
    if rows:
        body = {
            "values": rows
        }
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{active_title}!A2",
            valueInputOption="RAW",
            body=body
        ).execute()
    
    print(f"Updated {active_title} with {len(rows)} rules (PRESERVING FORMAT & ORDER)")


if __name__ == "__main__":
    update_jgd_main_active()
