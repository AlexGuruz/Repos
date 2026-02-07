from __future__ import annotations

import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scaffold.tools.sheets_cli import load_companies_config


def promote_rules_docker(company_ids: list[str]):
    """Promote rules using Docker container to avoid connection issues"""
    
    print(f"=== Promoting Rules for {', '.join(company_ids)} ===\n")
    
    for company_id in company_ids:
        print(f"🔧 Promoting rules for {company_id}...")
        
        # Convert company ID to database name
        db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
        
        try:
            # Check if pending table exists and has approved rules
            result = subprocess.run([
                "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                "-c", f"SELECT COUNT(*) FROM rules_pending_{company_id.lower().replace(' ', '_')} WHERE approved = true;", "-t"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"  ❌ Error checking pending rules: {result.stderr}")
                continue
            
            approved_count = result.stdout.strip()
            if approved_count == "0":
                print(f"  ⚠️  No approved pending rules to promote")
                continue
            
            print(f"  📊 Found {approved_count} approved pending rules")
            
            # Run the promotion SQL script
            sql_file = "db/ddl/promote_from_pending.sql"
            if not os.path.exists(sql_file):
                print(f"  ❌ SQL file not found: {sql_file}")
                continue
            
            # Read the SQL file
            with open(sql_file, 'r') as f:
                sql_content = f.read()
            
            # Set the table name variable
            table_name = f"rules_pending_{company_id.lower().replace(' ', '_')}"
            
            # Run the promotion
            result = subprocess.run([
                "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                "-v", f"table_name={table_name}",
                "-f", "-"
            ], input=sql_content, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"  ✅ Rules promoted successfully!")
                print(f"  📝 Output: {result.stdout}")
                
                # Check if active rules were created
                result = subprocess.run([
                    "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                    "-c", "SELECT COUNT(*) FROM app.rules_active;", "-t"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    active_count = result.stdout.strip()
                    print(f"  📈 Active rules count: {active_count}")
                    
                    # Now trigger the banner row creation by calling the sheets writeback
                    print(f"  🎯 Triggering banner row creation...")
                    trigger_banner_rows(company_id)
                else:
                    print(f"  ❌ Error checking active rules: {result.stderr}")
            else:
                print(f"  ❌ Error promoting rules: {result.stderr}")
                print(f"  📝 Output: {result.stdout}")
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()  # Empty line between companies


def trigger_banner_rows(company_id: str):
    """Trigger banner row creation by calling the sheets writeback function"""
    try:
        # Import the promotion service
        from services.rules_promoter.service import _sheets_writeback
        
        # Get the count of active rules
        db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
        result = subprocess.run([
            "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
            "-c", "SELECT COUNT(*) FROM app.rules_active;", "-t"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            promoted_count = int(result.stdout.strip())
            
            # Call the sheets writeback function
            result = _sheets_writeback(company_id, promoted_count)
            print(f"    📋 Banner row result: {result}")
        else:
            print(f"    ❌ Error getting active rule count: {result.stderr}")
    
    except Exception as e:
        print(f"    ❌ Error triggering banner rows: {e}")


def main():
    """Main function to promote rules and generate banner rows"""
    
    # Load companies configuration
    cfg_path = os.environ.get("KYLO_COMPANIES_CONFIG", os.path.join("config", "companies.json"))
    if not os.path.exists(cfg_path):
        print(f"Error: Companies config not found at {cfg_path}")
        return
    
    cfg = load_companies_config(cfg_path)
    
    # Show available companies
    companies = [c.get("company_id") for c in cfg.get("companies", [])]
    print("Available companies:")
    for i, company in enumerate(companies, 1):
        print(f"  {i}. {company}")
    
    print("\nEnter company numbers to promote (comma-separated, or 'all' for all):")
    response = input("> ").strip()
    
    if response.lower() == 'all':
        selected_companies = companies
    else:
        try:
            indices = [int(x.strip()) - 1 for x in response.split(',')]
            selected_companies = [companies[i] for i in indices if 0 <= i < len(companies)]
        except (ValueError, IndexError):
            print("Invalid input. Please enter valid company numbers.")
            return
    
    if not selected_companies:
        print("No companies selected.")
        return
    
    print(f"\nSelected companies: {', '.join(selected_companies)}")
    
    # Confirm before proceeding
    confirm = input("\nProceed with promotion? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("Promotion cancelled.")
        return
    
    # Run the promotion
    promote_rules_docker(selected_companies)
    
    print("\n=== Promotion Complete ===")
    print("Check the Google Sheets for banner rows in the Pending tabs!")


if __name__ == "__main__":
    main()
