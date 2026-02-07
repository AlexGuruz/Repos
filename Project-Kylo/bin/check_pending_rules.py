from __future__ import annotations

import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scaffold.tools.sheets_cli import load_companies_config


def check_pending_rules():
    """Check for pending rules that could be promoted to generate banner rows"""
    
    # Load companies configuration
    cfg_path = os.environ.get("KYLO_COMPANIES_CONFIG", os.path.join("config", "companies.json"))
    if not os.path.exists(cfg_path):
        print(f"Error: Companies config not found at {cfg_path}")
        return
    
    cfg = load_companies_config(cfg_path)
    
    print("=== Checking Pending Rules in Database ===\n")
    
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        print(f"🔍 Checking {company_id}...")
        
        try:
            # Check if Docker container is running
            result = subprocess.run([
                "docker", "ps", "--filter", "name=kylo-pg", "--format", "{{.Names}}"
            ], capture_output=True, text=True)
            
            if "kylo-pg" not in result.stdout:
                print(f"  ❌ Docker container 'kylo-pg' not running")
                continue
            
            # Check pending rules table
            db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
            result = subprocess.run([
                "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                "-c", "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'rules_pending_%';", "-t"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"  ❌ Error checking database: {result.stderr}")
                continue
            
            pending_tables = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            
            if not pending_tables:
                print(f"  ⚠️  No pending rules tables found")
                continue
            
            for table in pending_tables:
                print(f"  📋 Checking table: {table}")
                
                # Count total pending rules
                result = subprocess.run([
                    "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                    "-c", f"SELECT COUNT(*) FROM {table};", "-t"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    total_count = result.stdout.strip()
                    print(f"    📊 Total pending rules: {total_count}")
                    
                    # Count approved pending rules
                    result = subprocess.run([
                        "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                        "-c", f"SELECT COUNT(*) FROM {table} WHERE approved = true;", "-t"
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        approved_count = result.stdout.strip()
                        print(f"    ✅ Approved pending rules: {approved_count}")
                        
                        if approved_count != "0":
                            print(f"    🎯 Ready for promotion! Run promotion to generate banner rows.")
                            
                            # Show sample approved rules
                            result = subprocess.run([
                                "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", db_name,
                                "-c", f"SELECT source, target_sheet, target_header FROM {table} WHERE approved = true LIMIT 3;", "-t"
                            ], capture_output=True, text=True)
                            
                            if result.returncode == 0 and result.stdout.strip():
                                print(f"    📋 Sample approved rules:")
                                for line in result.stdout.strip().split('\n'):
                                    if line.strip():
                                        print(f"      - {line.strip()}")
                        else:
                            print(f"    ⚠️  No approved rules to promote")
                    else:
                        print(f"    ❌ Error counting approved rules: {result.stderr}")
                else:
                    print(f"    ❌ Error counting total rules: {result.stderr}")
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()  # Empty line between companies


def promote_rules_to_generate_banners():
    """Promote approved pending rules to generate banner rows"""
    print("\n=== Promoting Rules to Generate Banner Rows ===\n")
    
    # Load companies configuration
    cfg_path = os.environ.get("KYLO_COMPANIES_CONFIG", os.path.join("config", "companies.json"))
    if not os.path.exists(cfg_path):
        print(f"Error: Companies config not found at {cfg_path}")
        return
    
    cfg = load_companies_config(cfg_path)
    
    # Check if DSN map is available
    default_dsn_map = os.path.join("config", "dsn_map.json")
    local_override = os.path.join("config", "dsn_map_local.json")
    dsn_map_file = os.environ.get("KYLO_DSN_MAP_PATH", None)
    if dsn_map_file:
        dsn_map_file = os.path.abspath(dsn_map_file)
    else:
        dsn_map_file = local_override if os.path.exists(local_override) else default_dsn_map

    if not os.path.exists(dsn_map_file):
        print(f"Error: DSN map not found at {dsn_map_file}")
        print("Please ensure config/dsn_map.json exists with database connections")
        return
    
    with open(dsn_map_file, 'r', encoding='utf-8') as f:
        dsn_map = json.load(f)
    
    print("Available companies for promotion:")
    for company in cfg.get("companies", []):
        company_id = company.get("company_id")
        if company_id in dsn_map:
            print(f"  - {company_id}")
        else:
            print(f"  - {company_id} (no DSN configured)")
    
    print("\nTo promote rules and generate banner rows, run:")
    print("python scaffold/tools/promote_from_pending.py --cids <company_ids> --dsn-map-file config/dsn_map.json")
    print("\nExample:")
    print("python scaffold/tools/promote_from_pending.py --cids NUGZ,710_EMPIRE --dsn-map-file config/dsn_map.json")


if __name__ == "__main__":
    check_pending_rules()
    
    print("="*50)
    response = input("Do you want to see how to promote rules to generate banner rows? (y/N): ")
    if response.lower() in ['y', 'yes']:
        promote_rules_to_generate_banners()
    else:
        print("Skipping promotion instructions.")
