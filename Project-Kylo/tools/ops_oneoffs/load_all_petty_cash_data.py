#!/usr/bin/env python3
"""
Comprehensive Petty Cash Data Loader
Downloads and processes all petty cash CSV data from all companies
and loads it into the pooled database for transaction-to-rules matching.
"""

import json
import logging
import os
import sys
import subprocess
import csv
import hashlib
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


def run_docker_sql(database: str, sql: str) -> str:
    """Run SQL command in Docker container"""
    try:
        result = subprocess.run([
            'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-d', database, 
            '-c', sql, '-t', '-A'
        ], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"SQL execution failed: {e}")
        print(f"Error output: {e.stderr}")
        return ""


def load_company_config() -> Dict:
    """Load company configuration from config file"""
    try:
        with open('config/companies.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load company config: {e}")
        sys.exit(1)


def extract_spreadsheet_id(workbook_url: str) -> str:
    """Extract spreadsheet ID from Google Sheets URL"""
    # URL format: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit
    parts = workbook_url.split('/')
    for i, part in enumerate(parts):
        if part == 'd' and i + 1 < len(parts):
            return parts[i + 1]
    raise ValueError(f"Could not extract spreadsheet ID from URL: {workbook_url}")


def parse_csv_to_transactions(csv_content: str, batch_id: int, companies: List[Dict], config_path: str = "config/csv_processor_config.json") -> List[Dict]:
    """Parse CSV content and convert to transaction records using configuration"""
    transactions = []
    lines = csv_content.strip().split('\n')
    
    # Load configuration
    try:
        import json
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"   ❌ Failed to load configuration: {e}")
        return transactions
    
    petty_cash_config = config.get('petty_cash', {})
    start_row = petty_cash_config.get('start_row', 5)
    columns_config = petty_cash_config.get('columns', {})
    validation_config = petty_cash_config.get('validation', {})
    min_columns = validation_config.get('min_columns', 19)
    
    print(f"   📋 Using configuration: start_row={start_row}, min_columns={min_columns}")
    
    for row_index, line in enumerate(lines[start_row:], start=start_row):
        if not line.strip():
            continue
            
        try:
            # Parse CSV line
            reader = csv.reader([line])
            row = next(reader)
            
            # Skip empty rows or rows with insufficient data
            if len(row) < min_columns:
                continue
                
            # Check if row has meaningful data (not just empty cells)
            if all(not cell.strip() for cell in row[:4]):
                continue
                
            # Extract data using configuration
            initials = row[columns_config.get('initials', {}).get('index', 0)].strip() if len(row) > columns_config.get('initials', {}).get('index', 0) else ""
            date_str = row[columns_config.get('date', {}).get('index', 1)].strip() if len(row) > columns_config.get('date', {}).get('index', 1) else ""
            company_id = row[columns_config.get('company', {}).get('index', 2)].strip() if len(row) > columns_config.get('company', {}).get('index', 2) else ""
            description = row[columns_config.get('description', {}).get('index', 3)].strip() if len(row) > columns_config.get('description', {}).get('index', 3) else ""
            amount_str = row[columns_config.get('amount', {}).get('index', 4)].strip() if len(row) > columns_config.get('amount', {}).get('index', 4) else "0"
            
            # Skip if essential data is missing
            if not date_str or not company_id or not description:
                continue
            
            # Parse date using configuration formats
            date_formats = columns_config.get('date', {}).get('format', ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y'])
            posted_date = None
            
            for date_format in date_formats:
                try:
                    posted_date = datetime.strptime(date_str, date_format).strftime('%Y-%m-%d')
                    break
                except:
                    continue
            
            if not posted_date:
                print(f"   ⚠️  Could not parse date '{date_str}' in row {row_index + 1}")
                continue
            
            # Parse amount (convert to cents)
            try:
                amount_str = amount_str.replace('$', '').replace(',', '').replace('(', '').replace(')', '')
                if amount_str.strip() == '':
                    amount_cents = 0
                else:
                    amount_cents = int(float(amount_str) * 100)
            except:
                amount_cents = 0
            
            # Generate unique transaction ID
            txn_uid = hashlib.md5(f"{company_id}_{date_str}_{description}_{amount_str}".encode()).hexdigest()
            
            # Generate hash for deduplication
            hash_norm = hashlib.sha256(f"{company_id}_{posted_date}_{description}_{amount_cents}".encode()).hexdigest()
            
            transaction = {
                "txn_uid": txn_uid,
                "company_id": company_id,
                "posted_date": posted_date,
                "amount_cents": amount_cents,
                "description": description,
                "source_stream_id": "petty_cash_csv",
                "source_file_fingerprint": get_csv_metadata(csv_content)['file_fingerprint'],
                "row_index_0based": row_index,
                "hash_norm": hash_norm,
                "ingest_batch_id": batch_id
            }
            
            transactions.append(transaction)
            
        except Exception as e:
            print(f"   ⚠️  Failed to parse row {row_index + 1}: {e}")
            continue
    
    return transactions


def create_global_batch(source: str) -> int:
    """Create a new ingest batch in the global database"""
    print(f"\n🔄 Creating global ingest batch...")
    
    batch_result = run_docker_sql("kylo_global", f"""
        INSERT INTO control.ingest_batches (source, started_at) 
        VALUES ('{source}', NOW()) 
        RETURNING batch_id;
    """)
    
    if batch_result:
        batch_id = int(batch_result.split('\n')[0])
        print(f"✅ Created batch ID: {batch_id}")
        return batch_id
    else:
        raise Exception("Failed to create ingest batch")


def store_transactions_in_global(transactions: List[Dict], batch_id: int) -> Dict:
    """Store transactions in the global database"""
    print(f"\n💾 Storing {len(transactions)} transactions in global database...")
    
    stored_count = 0
    failed_count = 0
    
    for i, txn in enumerate(transactions):
        try:
            # Insert into core.transactions_unified
            sql = f"""
            INSERT INTO core.transactions_unified (
                txn_uid, company_id, source_stream_id, posted_date, amount_cents, 
                description, source_file_fingerprint, row_index_0based, hash_norm, ingest_batch_id
            ) VALUES (
                '{txn['txn_uid']}', '{txn['company_id']}', 'petty_cash_csv', '{txn['posted_date']}', {txn['amount_cents']}, 
                '{txn['description'].replace("'", "''")}', '{txn.get('source_file_fingerprint', 'unknown')}', {txn.get('row_index_0based', i)}, 
                '{txn.get('hash_norm', f'hash_{i}')}', {batch_id}
            );
            """
            
            result = run_docker_sql("kylo_global", sql)
            if result == "":
                stored_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            print(f"   ❌ Failed to store transaction {i+1}: {e}")
            failed_count += 1
    
    print(f"✅ Stored {stored_count} transactions, {failed_count} failed")
    
    return {
        "stored_count": stored_count,
        "failed_count": failed_count,
        "total_processed": len(transactions)
    }


def verify_global_database() -> Dict:
    """Verify the global database structure and content"""
    print("\n🔍 Verifying global database...")
    
    # Check if global database exists
    db_check = run_docker_sql("kylo_global", "SELECT current_database();")
    if not db_check:
        print("❌ Global database 'kylo_global' not found")
        return {"status": "failed", "reason": "database_not_found"}
    
    print(f"✅ Connected to database: {db_check}")
    
    # Check tables exist
    tables = [
        "control.ingest_batches",
        "core.transactions_unified", 
        "intake.raw_transactions"
    ]
    
    for table in tables:
        table_check = run_docker_sql("kylo_global", f"SELECT COUNT(*) FROM {table};")
        if table_check == "":
            print(f"❌ Table {table} not found")
        else:
            print(f"✅ Table {table}: {table_check} rows")
    
    # Check recent batches
    batches = run_docker_sql("kylo_global", """
        SELECT batch_id, source, started_at 
        FROM control.ingest_batches 
        ORDER BY batch_id DESC 
        LIMIT 5;
    """)
    
    if batches:
        print(f"✅ Recent batches found: {len(batches.split(chr(10)))}")
    else:
        print("⚠️  No ingest batches found")
    
    return {"status": "success"}


def main():
    """Main function to load all petty cash data"""
    print("🚀 COMPREHENSIVE PETTY CASH DATA LOADER")
    print("=" * 60)
    print("This will download real petty cash data from Google Sheets")
    print("and load it into the global database for processing.")
    print()
    
    # Load company configuration
    print("📋 Loading company configuration...")
    config = load_company_config()
    companies = config['companies']
    print(f"✅ Loaded {len(companies)} companies")
    
    # Verify global database
    db_status = verify_global_database()
    if db_status["status"] != "success":
        print("❌ Global database verification failed")
        return
    
    # Check service account
    service_account_path = 'secrets/service_account.json'
    if not os.path.exists(service_account_path):
        print("❌ Service account file not found!")
        return
    
    print("✅ Service account file found")
    
    # Get intake configuration
    intake_config = config.get('intake', {})
    intake_workbook_url = intake_config.get('workbook')
    intake_sheet_name = intake_config.get('input_sheet_cash', 'PETTY CASH')
    
    if not intake_workbook_url:
        print("❌ No intake workbook configured!")
        return
    
    print(f"\n📊 Processing intake workbook...")
    print(f"   Intake URL: {intake_workbook_url}")
    print(f"   Sheet name: {intake_sheet_name}")
    
    total_transactions = 0
    all_transactions = []
    
    try:
        # Extract spreadsheet ID from intake workbook
        spreadsheet_id = extract_spreadsheet_id(intake_workbook_url)
        print(f"   Spreadsheet ID: {spreadsheet_id}")
        
        # Download CSV data from intake workbook
        print(f"   Downloading {intake_sheet_name} data...")
        csv_content = download_petty_cash_csv(
            spreadsheet_id=spreadsheet_id,
            service_account_path=service_account_path
        )
        
        # Validate CSV content
        if not validate_csv_content(csv_content, min_rows=5):
            print(f"   ⚠️  CSV validation failed")
            return
        
        # Get metadata
        metadata = get_csv_metadata(csv_content)
        print(f"   ✅ Downloaded {metadata['total_lines']} lines")
        print(f"   📄 File fingerprint: {metadata['file_fingerprint'][:16]}...")
        
        # Show first few lines for verification
        lines = csv_content.strip().split('\n')
        print(f"   📋 First 3 lines preview:")
        for i, line in enumerate(lines[:3]):
            print(f"      {i+1}: {line[:80]}...")
        
        # Create batch for intake data
        batch_id = create_global_batch("petty_cash_real")
        
        # Parse CSV to transactions (will determine company_id from data)
        transactions = parse_csv_to_transactions(csv_content, batch_id, companies, "config/csv_processor_config.json")
        print(f"   📊 Parsed {len(transactions)} transactions")
        
        if transactions:
            # Store transactions
            storage_result = store_transactions_in_global(transactions, batch_id)
            print(f"   💾 Stored {storage_result['stored_count']} transactions")
            total_transactions += storage_result['stored_count']
            all_transactions.extend(transactions)
        else:
            print(f"   ⚠️  No valid transactions found")
        
    except Exception as e:
        print(f"   ❌ Error processing intake workbook: {e}")
        return
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎉 LOADING COMPLETE")
    print("=" * 60)
    
    print(f"✅ Total transactions loaded: {total_transactions}")
    print("✅ Real petty cash data loaded successfully!")
    print("✅ Global database is ready for the mover service")
    
    # Verify final data
    print("\n🔍 FINAL VERIFICATION")
    print("=" * 30)
    
    total_stored = run_docker_sql("kylo_global", "SELECT COUNT(*) FROM core.transactions_unified;")
    print(f"📊 Total transactions in global database: {total_stored}")
    
    # Check by company
    for company in companies:
        company_id = company['company_id']
        company_count = run_docker_sql("kylo_global", f"SELECT COUNT(*) FROM core.transactions_unified WHERE company_id = '{company_id}';")
        print(f"   - {company_id}: {company_count} transactions")
    
    print("\n📋 Next steps:")
    print("   1. Run mover service to distribute to company databases")
    print("   2. Load rules into company databases")
    print("   3. Test transaction-to-rules matching")


if __name__ == "__main__":
    main()
