#!/usr/bin/env python3
"""
Real Petty Cash Data Downloader
Downloads actual petty cash data from Google Sheets with data integrity validation
"""

import json
import logging
import os
import sys
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.intake.csv_downloader import download_petty_cash_csv, validate_csv_content, get_csv_metadata

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


def extract_spreadsheet_id(workbook_url: str) -> str:
    """Extract spreadsheet ID from Google Sheets URL"""
    # URL format: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit
    parts = workbook_url.split('/')
    for i, part in enumerate(parts):
        if part == 'd' and i + 1 < len(parts):
            return parts[i + 1]
    raise ValueError(f"Could not extract spreadsheet ID from URL: {workbook_url}")


def run_docker_sql(database: str, sql: str) -> str:
    """Run SQL command in Docker container"""
    try:
        result = subprocess.run([
            'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-d', database, 
            '-c', sql, '-t', '-A'
        ], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        log.error(f"SQL execution failed: {e}")
        return ""


def create_batch(company_id: str, source: str) -> int:
    """Create a new ingest batch and return batch ID"""
    sql = f"""
    INSERT INTO control.ingest_batches (source, company_id, started_at)
    VALUES ('{source}', '{company_id}', NOW())
    RETURNING batch_id;
    """
    result = run_docker_sql("kylo_global", sql)
    if result:
        return int(result)
    raise Exception(f"Failed to create batch for {company_id}")


def store_csv_data(company_id: str, csv_content: str, batch_id: int) -> int:
    """Store CSV data in raw_transactions table"""
    # Parse CSV and store in raw_transactions
    lines = csv_content.strip().split('\n')
    stored_count = 0
    
    for row_index, line in enumerate(lines):
        if not line.strip():
            continue
            
        # Store raw CSV line
        sql = f"""
        INSERT INTO intake.raw_transactions 
        (company_id, ingest_batch_id, raw_content, row_index_0based, source_file_fingerprint)
        VALUES (
            '{company_id}',
            {batch_id},
            '{line.replace("'", "''")}',
            {row_index},
            '{get_csv_metadata(csv_content)['file_fingerprint']}'
        );
        """
        run_docker_sql("kylo_global", sql)
        stored_count += 1
    
    return stored_count


def main():
    """Main function to download real petty cash data"""
    print("🔍 DOWNLOADING REAL PETTY CASH DATA")
    print("=" * 50)
    
    # Load company configuration
    with open('config/companies.json', 'r') as f:
        config = json.load(f)
    
    service_account_path = 'secrets/service_account.json'
    
    if not os.path.exists(service_account_path):
        print("❌ Service account file not found!")
        return
    
    total_transactions = 0
    
    for company in config['companies']:
        company_id = company['company_id']
        workbook_url = company['workbook']
        
        print(f"\n📊 Processing {company_id}...")
        
        try:
            # Extract spreadsheet ID
            spreadsheet_id = extract_spreadsheet_id(workbook_url)
            print(f"   Spreadsheet ID: {spreadsheet_id}")
            
            # Download CSV data
            print(f"   Downloading PETTY CASH data...")
            csv_content = download_petty_cash_csv(
                spreadsheet_id=spreadsheet_id,
                service_account_path=service_account_path
            )
            
            # Validate CSV content
            if not validate_csv_content(csv_content, min_rows=5):
                print(f"   ⚠️  CSV validation failed for {company_id}")
                continue
            
            # Get metadata
            metadata = get_csv_metadata(csv_content)
            print(f"   ✅ Downloaded {metadata['total_lines']} lines")
            print(f"   📄 File fingerprint: {metadata['file_fingerprint'][:16]}...")
            
            # Create batch
            batch_id = create_batch(company_id, "petty_cash_real")
            print(f"   📦 Created batch ID: {batch_id}")
            
            # Store raw data
            stored_count = store_csv_data(company_id, csv_content, batch_id)
            print(f"   💾 Stored {stored_count} raw transaction rows")
            
            total_transactions += stored_count
            
            # Show first few lines for verification
            lines = csv_content.strip().split('\n')
            print(f"   📋 First 3 lines preview:")
            for i, line in enumerate(lines[:3]):
                print(f"      {i+1}: {line[:80]}...")
            
        except Exception as e:
            print(f"   ❌ Error processing {company_id}: {e}")
            continue
    
    print(f"\n✅ COMPLETED")
    print(f"📊 Total transactions downloaded: {total_transactions}")
    
    # Verify data in database
    print(f"\n🔍 VERIFYING DATABASE DATA")
    print("=" * 30)
    
    # Check total raw transactions
    total_raw = run_docker_sql("kylo_global", "SELECT COUNT(*) FROM intake.raw_transactions;")
    print(f"📄 Total raw transactions: {total_raw}")
    
    # Check by company
    companies_data = run_docker_sql("kylo_global", 
        "SELECT company_id, COUNT(*) FROM intake.raw_transactions GROUP BY company_id ORDER BY company_id;")
    print(f"📊 By company:\n{companies_data}")
    
    # Check latest batches
    latest_batches = run_docker_sql("kylo_global",
        "SELECT batch_id, company_id, source, started_at FROM control.ingest_batches ORDER BY batch_id DESC LIMIT 5;")
    print(f"📦 Latest batches:\n{latest_batches}")


if __name__ == "__main__":
    main()
