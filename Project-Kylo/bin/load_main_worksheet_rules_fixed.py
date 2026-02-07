from __future__ import annotations

import os
import sys
import hashlib
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def load_main_worksheet_rules(company_id: str):
    """Load rules from the main Google Sheets workbook into database - PRESERVING FORMAT"""
    spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    try:
        # Get pending rules from the main workbook - READ ALL RULES
        pending_title = f"{company_id} Pending"
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{pending_title}!A2:D500"  # Increased range to get ALL rules
        ).execute()
        
        values = result.get('values', [])
        print(f"Found {len(values)} rules in {pending_title}")
        
        # Generate SQL insert statements
        sql_statements = []
        for row in values:
            if len(row) >= 4:  # source, target_sheet, target_header, approved
                source = row[0] if row[0] else ""  # PRESERVE ORIGINAL FORMAT (ALL CAPS)
                target_sheet = row[1] if row[1] else ""
                target_header = row[2] if row[2] else ""
                approved = row[3].upper() == "TRUE" if row[3] else False
                
                if source and target_sheet and target_header:
                    # Create content hash (use original format)
                    content = f"{source}|{target_sheet}|{target_header}"
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    
                    # Convert company_id to lowercase for table name
                    table_name = f"rules_pending_{company_id.lower().replace(' ', '_')}"
                    
                    # Escape single quotes in SQL
                    source_escaped = source.replace("'", "''")
                    target_sheet_escaped = target_sheet.replace("'", "''")
                    target_header_escaped = target_header.replace("'", "''")
                    
                    sql = f"""INSERT INTO {table_name} (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('{source_escaped}', '{target_sheet_escaped}', '{target_header_escaped}', {approved}, '{content_hash}')
                             ON CONFLICT (source, content_hash) DO UPDATE SET 
                             target_sheet = EXCLUDED.target_sheet,
                             target_header = EXCLUDED.target_header,
                             approved = EXCLUDED.approved;"""
                    sql_statements.append(sql)
        
        # Write SQL to file
        sql_file = f"{company_id.lower().replace(' ', '_')}_rules_fixed.sql"
        with open(sql_file, "w") as f:
            f.write(f"-- {company_id} Rules from Main Worksheet (PRESERVING FORMAT)\n")
            f.write(f"TRUNCATE rules_pending_{company_id.lower().replace(' ', '_')};\n\n")
            for sql in sql_statements:
                f.write(sql + "\n")
        
        print(f"Generated {len(sql_statements)} SQL statements in {sql_file}")
        print(f"Run: docker exec -i kylo-pg psql -U postgres -d kylo_{company_id.lower().replace(' ', '_')} -f /tmp/{sql_file}")
        
        # Also copy to /tmp for docker
        import shutil
        shutil.copy(sql_file, f"/tmp/{sql_file}")
        print(f"Copied to /tmp/{sql_file}")
        
    except Exception as e:
        print(f"Error loading {company_id} rules: {e}")


def main():
    companies = ["NUGZ", "710 EMPIRE", "PUFFIN PURE", "JGD"]
    
    for company in companies:
        print(f"\n=== Loading {company} rules (PRESERVING FORMAT) ===")
        load_main_worksheet_rules(company)


if __name__ == "__main__":
    main()
