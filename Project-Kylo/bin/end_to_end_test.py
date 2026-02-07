from __future__ import annotations

import os
import sys
import json
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.sheets.poster import _get_service, _extract_spreadsheet_id
from scaffold.tools.sheets_cli import load_companies_config
from services.rules_promoter.service import _sheets_writeback


def end_to_end_test():
    """Run a comprehensive end-to-end test of the banner row workflow"""
    
    print("=== END-TO-END BANNER ROW WORKFLOW TEST ===\n")
    
    # Step 1: Check current state
    print("🔍 STEP 1: Checking current state...")
    check_current_state()
    
    # Step 2: Check pending rules
    print("\n🔍 STEP 2: Checking pending rules...")
    check_pending_rules()
    
    # Step 3: Test banner row creation
    print("\n🔍 STEP 3: Testing banner row creation...")
    test_banner_creation()
    
    # Step 4: Verify final state
    print("\n🔍 STEP 4: Verifying final state...")
    verify_final_state()
    
    print("\n✅ END-TO-END TEST COMPLETE!")


def check_current_state():
    """Check the current state of all companies"""
    
    cfg = load_companies_config()
    service = _get_service()
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        # Use the rules management workbook, not the company transaction workbook
        # This script is for testing rule management
        spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
        pending_title = f"{company_id} Pending"
        
        try:
            # Check current banner rows
            data_result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{pending_title}!A1:A10"
            ).execute()
            
            data_rows = data_result.get('values', [])
            banner_count = 0
            
            for i, row in enumerate(data_rows, start=1):
                if row and "Promoted" in str(row[0]):
                    banner_count += 1
            
            print(f"   📋 {company_id}: {banner_count} banner rows in first 10 rows")
            
        except Exception as e:
            print(f"   ❌ {company_id}: Error - {e}")


def check_pending_rules():
    """Check pending rules in database"""
    
    cfg = load_companies_config()
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        
        try:
            # Check if Docker container is running
            result = subprocess.run([
                "docker", "ps", "--filter", "name=kylo-pg", "--format", "{{.Names}}"
            ], capture_output=True, text=True)
            
            if "kylo-pg" not in result.stdout:
                print(f"   ❌ {company_id}: Docker container not running")
                continue
            
            # Check pending rules
            db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
            result = subprocess.run([
                "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                "-c", f"SELECT COUNT(*) FROM rules_pending_{company_id.lower().replace(' ', '_')} WHERE approved = true;", "-t"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                approved_count = result.stdout.strip()
                print(f"   📊 {company_id}: {approved_count} approved pending rules")
            else:
                print(f"   ❌ {company_id}: Error checking pending rules")
                
        except Exception as e:
            print(f"   ❌ {company_id}: Error - {e}")


def test_banner_creation():
    """Test banner row creation for each company"""
    
    cfg = load_companies_config()
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        
        try:
            # Get active rules count
            db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
            result = subprocess.run([
                "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                "-c", "SELECT COUNT(*) FROM app.rules_active;", "-t"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                active_count = int(result.stdout.strip())
                print(f"   🎯 {company_id}: Testing banner creation with {active_count} active rules")
                
                # Test banner creation
                result = _sheets_writeback(company_id, active_count)
                if result == "ok":
                    print(f"   ✅ {company_id}: Banner creation successful")
                else:
                    print(f"   ❌ {company_id}: Banner creation failed - {result}")
            else:
                print(f"   ❌ {company_id}: Error getting active rules count")
                
        except Exception as e:
            print(f"   ❌ {company_id}: Error - {e}")


def verify_final_state():
    """Verify the final state after banner creation"""
    
    cfg = load_companies_config()
    service = _get_service()
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        # Use the rules management workbook, not the company transaction workbook
        # This script is for testing rule management
        spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
        pending_title = f"{company_id} Pending"
        
        try:
            # Check banner rows in first 10 rows
            data_result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{pending_title}!A1:A10"
            ).execute()
            
            data_rows = data_result.get('values', [])
            banner_rows = []
            
            for i, row in enumerate(data_rows, start=1):
                if row and "Promoted" in str(row[0]):
                    banner_rows.append((i, str(row[0])))
            
            if banner_rows:
                print(f"   ✅ {company_id}: {len(banner_rows)} banner rows found in first 10 rows")
                for row_num, content in banner_rows:
                    print(f"      Row {row_num}: {content[:60]}...")
            else:
                print(f"   ⚠️  {company_id}: No banner rows found in first 10 rows")
            
            # Check total banner rows
            full_result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{pending_title}!A:A"
            ).execute()
            
            full_rows = full_result.get('values', [])
            total_banners = sum(1 for row in full_rows if row and "Promoted" in str(row[0]))
            print(f"   📊 {company_id}: {total_banners} total banner rows in sheet")
            
        except Exception as e:
            print(f"   ❌ {company_id}: Error - {e}")


def load_companies_config():
    """Load companies configuration"""
    cfg_path = os.environ.get("KYLO_COMPANIES_CONFIG", os.path.join("config", "companies.json"))
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Companies config not found at {cfg_path}")
    
    with open(cfg_path, 'r') as f:
        return json.load(f)


def _get_service():
    """Get Google Sheets service"""
    service_account = os.path.join("secrets", "service_account.json")
    
    if not os.path.exists(service_account):
        raise FileNotFoundError(f"Service account not found at {service_account}")
    
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
    
    from services.sheets.poster import _get_service
    return _get_service()


if __name__ == "__main__":
    end_to_end_test()
