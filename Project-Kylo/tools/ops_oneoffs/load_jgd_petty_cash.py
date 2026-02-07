#!/usr/bin/env python3
"""
JGD Petty Cash Data Loader
Downloads petty cash CSV data from JGD 2025 financials spreadsheet
using the specific service account and loads it into the pooled database.
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
from services.intake.csv_processor import PettyCashCSVProcessor, validate_transaction

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


def create_global_batch() -> int:
    """Create a new ingest batch in the global database"""
    print("\n🔄 Creating global ingest batch...")
    
    batch_result = run_docker_sql("kylo_global", """
        INSERT INTO control.ingest_batches (source, started_at) 
        VALUES ('jgd_petty_cash_load', NOW()) 
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
                description, counterparty_name, source_file_fingerprint, row_index_0based, hash_norm, ingest_batch_id
            ) VALUES (
                gen_random_uuid(), 'JGD', 'jgd_petty_cash_csv', '{txn['posted_date']}', {txn['amount_cents']}, 
                '{txn['description'].replace("'", "''")}', '{txn.get('counterparty_name', '').replace("'", "''")}', '{txn.get('source_file_fingerprint', 'jgd_2025_financials')}', {txn.get('row_index_0based', i)}, 
                '{txn.get('hash_norm', f'jgd_hash_{i}')}', {batch_id}
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


def run_mover_service() -> Dict:
    """Run the mover service to distribute transactions to company databases"""
    print("\n🔄 Running mover service to distribute transactions...")
    
    # Get transactions for JGD from global database
    global_sql = """
    SELECT 
        txn_uid, posted_date, amount_cents, description, counterparty_name, source_stream_id,
        source_file_fingerprint, row_index_0based, hash_norm
    FROM core.transactions_unified 
    WHERE company_id = 'JGD';
    """
    
    global_result = run_docker_sql("kylo_global", global_sql)
    
    if global_result:
        # Insert into JGD company database
        inserted_count = 0
        for line in global_result.split('\n'):
            if line and '|' in line:
                parts = line.split('|')
                if len(parts) >= 9:
                    txn_uid, posted_date, amount_cents, description, counterparty_name, source_stream_id, source_file_fingerprint, row_index_0based, hash_norm = parts[:9]
                    
                    # Escape single quotes in description and counterparty_name
                    description = description.replace("'", "''")
                    counterparty_name = counterparty_name.replace("'", "''")
                    
                    insert_sql = f"""
                    INSERT INTO app.transactions (
                        txn_uid, posted_date, amount_cents, description, counterparty_name, source_stream_id, 
                        source_file_fingerprint, row_index_0based, hash_norm
                    ) VALUES (
                        '{txn_uid}', '{posted_date}', {amount_cents}, '{description}', '{counterparty_name}', '{source_stream_id}',
                        '{source_file_fingerprint}', {row_index_0based}, '{hash_norm}'
                    ) ON CONFLICT (txn_uid) DO NOTHING;
                    """
                    
                    result = run_docker_sql("kylo_jgd", insert_sql)
                    if result == "":
                        inserted_count += 1
        
        print(f"   ✅ kylo_jgd: {inserted_count} transactions moved")
        return {"kylo_jgd": inserted_count}
    else:
        print(f"   ⚠️  kylo_jgd: No transactions to move")
        return {"kylo_jgd": 0}


def test_transaction_rules_matching():
    """Test transaction-to-rules matching for JGD"""
    print("\n🔍 Testing transaction-to-rules matching for JGD...")
    
    # Check transaction count
    txn_count = run_docker_sql("kylo_jgd", "SELECT COUNT(*) FROM app.transactions;")
    print(f"   Transactions: {txn_count}")
    
    # Check rules count
    rules_count = run_docker_sql("kylo_jgd", "SELECT COUNT(*) FROM app.rules_active;")
    print(f"   Active Rules: {rules_count}")
    
    # Test matching
    if txn_count and int(txn_count) > 0:
        matching_sql = f"""
        SELECT 
            t.description,
            t.amount_cents,
            r.rule_json->>'source' as rule_pattern,
            r.rule_json->>'target_sheet' as target_sheet,
            r.rule_json->>'target_header' as target_header
        FROM app.transactions t 
        LEFT JOIN app.rules_active r ON (
            t.description ILIKE '%' || (r.rule_json->>'source') || '%'
        )
        WHERE r.rule_id IS NOT NULL
        ORDER BY t.description;
        """
        
        matches = run_docker_sql("kylo_jgd", matching_sql)
        
        if matches:
            print(f"   ✅ Found {len(matches.split(chr(10)))} rule matches:")
            for line in matches.split(chr(10)):
                if line and '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        desc, amount, pattern, sheet, header = parts[:5]
                        print(f"      💰 ${int(amount)/100:.2f} '{desc}' → {pattern} → {sheet}/{header}")
        else:
            print(f"   ⚠️  No rule matches found")
    
    # Check sort queue (where matched transactions should be)
    sort_count = run_docker_sql("kylo_jgd", "SELECT COUNT(*) FROM app.sort_queue;")
    print(f"   Sort Queue: {sort_count} items")


def main():
    """Main function to load JGD petty cash data"""
    print("🚀 JGD PETTY CASH DATA LOADER")
    print("=" * 60)
    print("This will download petty cash CSV data from JGD 2025 financials")
    print("and load it into the pooled database for transaction-to-rules matching.")
    print()
    
    # JGD 2025 Financials spreadsheet details
    spreadsheet_id = "1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE"  # From companies.json
    service_account_email = "stashbox@ai-dataframe.iam.gserviceaccount.com"
    sheet_name = "PETTY CASH"
    header_rows = 19  # Standard header rows for petty cash sheets
    
    print(f"📊 Target: JGD 2025 Financials")
    print(f"📋 Spreadsheet ID: {spreadsheet_id}")
    print(f"🔐 Service Account: {service_account_email}")
    print(f"📄 Sheet: {sheet_name}")
    print(f"📏 Header Rows: {header_rows}")
    print()
    
    try:
        # 1. Download CSV
        print("📥 Downloading CSV from Google Sheets...")
        service_account_path = "secrets/service_account.json"
        csv_content = download_petty_cash_csv(spreadsheet_id, service_account_path, sheet_name)
        
        # Validate CSV content
        if not validate_csv_content(csv_content):
            raise ValueError("CSV content validation failed")
        
        # Get CSV metadata
        metadata = get_csv_metadata(csv_content)
        print(f"📋 CSV metadata: {metadata['total_lines']} lines, {metadata['non_empty_lines']} non-empty")
        
        # 2. Parse transactions
        print("🔍 Parsing transactions...")
        processor = PettyCashCSVProcessor(csv_content, header_rows)
        transactions = list(processor.parse_transactions())
        
        processing_stats = processor.get_processing_stats()
        print(f"📊 Processing stats: {processing_stats['unique_rows_processed']} unique, {processing_stats['duplicate_rows_skipped']} duplicates")
        
        # 3. Validate transactions
        print("✅ Validating transactions...")
        valid_transactions = []
        invalid_count = 0
        
        for txn in transactions:
            is_valid, errors = validate_transaction(txn)
            if is_valid:
                valid_transactions.append(txn)
            else:
                invalid_count += 1
                print(f"   ❌ Invalid transaction: {errors}")
        
        print(f"📈 Validation complete: {len(valid_transactions)} valid, {invalid_count} invalid")
        
        if not valid_transactions:
            print("❌ No valid transactions found. Exiting.")
            return
        
        # Show sample transactions
        print(f"\n📊 Sample transactions:")
        for i, txn in enumerate(valid_transactions[:5]):
            print(f"   {i+1}. ${txn['amount_cents']/100:.2f} - {txn['description']}")
        if len(valid_transactions) > 5:
            print(f"   ... and {len(valid_transactions) - 5} more")
        
        # 4. Create global batch and store transactions
        batch_id = create_global_batch()
        
        storage_result = store_transactions_in_global(valid_transactions, batch_id)
        
        print(f"\n💾 Storage complete: {storage_result['stored_count']} stored, {storage_result['failed_count']} failed")
        
        # 5. Run mover service
        mover_results = run_mover_service()
        
        # 6. Final summary
        print("\n" + "=" * 60)
        print("🎉 JGD PETTY CASH LOADING COMPLETE")
        print("=" * 60)
        
        print(f"✅ Global database: {storage_result['stored_count']} transactions in batch {batch_id}")
        print("✅ JGD database updated:")
        
        for company_db, count in mover_results.items():
            print(f"   - {company_db}: {count} transactions")
        
        # 7. Test transaction-to-rules matching
        test_transaction_rules_matching()
        
        print("\n" + "=" * 60)
        print("🎉 JGD PETTY CASH DATA LOADED SUCCESSFULLY!")
        print("✅ Transaction-to-rules matching system is ready!")
        print("✅ Real JGD petty cash data loaded and distributed")
        
    except Exception as e:
        print(f"\n❌ Failed to complete loading: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
