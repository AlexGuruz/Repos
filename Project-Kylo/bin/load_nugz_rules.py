from __future__ import annotations

import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service


def load_nugz_rules():
    """Load NUGZ rules from Google Sheets into database"""
    spreadsheet_id = "1hXG_doc4R2ODSDpjElsNgSel54kP1q2qb2RmNBOMeco"
    company_id = "NUGZ"
    service_account = os.path.join("secrets", "service_account.json")
    
    if service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    service = _get_service()
    
    # Get rules from Google Sheets Pending tab
    pending_title = f"Pending Rules – {company_id}"
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{pending_title}!A2:G50"
        ).execute()
        
        values = result.get('values', [])
        print(f"Found {len(values)} rows in {pending_title}")
        
        # Generate SQL insert statements
        sql_statements = []
        for row in values:
            if len(row) >= 7:  # Date, Source, Company, Amount, Target_Sheet, Target_Header, Approved
                source = row[1] if len(row) > 1 else ""
                target_sheet = row[4] if len(row) > 4 else ""
                target_header = row[5] if len(row) > 5 else ""
                approved = row[6] if len(row) > 6 else "FALSE"
                
                if source and target_sheet and target_header:
                    # Create content hash
                    content = f"{source}|{target_sheet}|{target_header}"
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    
                    # Convert approved to boolean
                    is_approved = approved.upper() == "TRUE"
                    
                    sql = f"""INSERT INTO rules_pending_nugz (source, target_sheet, target_header, approved, content_hash) 
                             VALUES ('{source}', '{target_sheet}', '{target_header}', {is_approved}, '{content_hash}')
                             ON CONFLICT (source, content_hash) DO NOTHING;"""
                    sql_statements.append(sql)
        
        # Write SQL to file
        with open("nugz_rules.sql", "w") as f:
            f.write("-- NUGZ Rules from Google Sheets\n")
            f.write("TRUNCATE rules_pending_nugz;\n\n")
            for sql in sql_statements:
                f.write(sql + "\n")
        
        print(f"Generated {len(sql_statements)} SQL statements in nugz_rules.sql")
        print("Run: docker exec -i kylo-pg psql -U postgres -d kylo_nugz -f /tmp/nugz_rules.sql")
        
    except Exception as e:
        print(f"Error reading Google Sheets: {e}")


if __name__ == "__main__":
    load_nugz_rules()
