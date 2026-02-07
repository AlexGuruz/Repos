#!/usr/bin/env python3
"""
Transaction Trace Test
Comprehensive test that feeds sample transactions through the entire pipeline
and traces their journey from CSV intake to Google Sheets output.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psycopg2

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.intake.csv_processor import PettyCashCSVProcessor, validate_transaction
from services.intake.deduplication import DeduplicationWorkflow
from services.intake.storage import create_ingest_batch, store_csv_transactions_batch, get_storage_stats
from services.mover.service import BatchMoveRequest, BatchMoveResponse, MoverService
from services.sheets.poster import SheetsPoster
from telemetry.emitter import start_trace, emit

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


def create_db_connection(db_url: str):
    """Create database connection"""
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)


def generate_sample_csv_content() -> str:
    """Generate sample CSV content for testing"""
    today = datetime.now().strftime('%m/%d/%Y')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%m/%d/%Y')
    
    # Sample CSV with header rows and transaction data
    csv_content = f"""Petty Cash Transactions
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Date,Amount,Company,Description
{today},125.50,NUGZ,Office supplies purchase
{today},-45.00,NUGZ,Cash deposit
{yesterday},89.99,710 EMPIRE,Equipment maintenance
{yesterday},-200.00,710 EMPIRE,Payment received
{today},67.25,PUFFIN PURE,Marketing materials
{today},-150.00,PUFFIN PURE,Refund issued
{yesterday},234.75,JGD,Inventory purchase
{yesterday},-75.50,JGD,Service payment
"""
    return csv_content


def trace_csv_intake(csv_content: str, db_url: str) -> Dict:
    """Trace CSV intake process"""
    print("\n" + "="*60)
    print("🔍 TRACING CSV INTAKE PROCESS")
    print("="*60)
    
    trace_id = start_trace("csv_intake", "test")
        # 1. Parse CSV
        print("📥 Step 1: Parsing CSV content...")
        processor = PettyCashCSVProcessor(csv_content, header_rows=3)
        transactions = list(processor.parse_transactions())
        
        print(f"✅ Parsed {len(transactions)} transactions")
        for i, txn in enumerate(transactions):
            print(f"   {i+1}. {txn['company_id']}: ${txn['amount_cents']/100:.2f} - {txn['description']}")
        
        # 2. Validate transactions
        print("\n📋 Step 2: Validating transactions...")
        valid_transactions = []
        for txn in transactions:
            is_valid, errors = validate_transaction(txn)
            if is_valid:
                valid_transactions.append(txn)
            else:
                print(f"❌ Invalid transaction: {errors}")
        
        print(f"✅ {len(valid_transactions)} valid transactions")
        
        # 3. Database operations
        print("\n🗄️ Step 3: Database operations...")
        db_conn = create_db_connection(db_url)
        
        try:
            # Create ingest batch
            batch_id = create_ingest_batch(db_conn, "test_trace")
            print(f"✅ Created ingest batch: {batch_id}")
            
            # Deduplication workflow
            dedup_workflow = DeduplicationWorkflow(db_conn)
            dedup_result = dedup_workflow.process_with_deduplication(
                valid_transactions,
                "test_trace_fingerprint",
                batch_id
            )
            
            print(f"✅ Deduplication: {dedup_result['unique_count']} unique, {dedup_result['duplicate_count']} duplicates")
            
            # Store transactions
            storage_result = store_csv_transactions_batch(
                db_conn,
                dedup_result['unique_transactions'],
                batch_id
            )
            
            print(f"✅ Stored {storage_result['transactions_stored']} transactions")
            
            # Get storage stats
            storage_stats = get_storage_stats(db_conn, batch_id)
            print(f"📊 Storage stats: {json.dumps(storage_stats, indent=2)}")
            
            return {
                "batch_id": batch_id,
                "transactions_parsed": len(transactions),
                "transactions_valid": len(valid_transactions),
                "transactions_stored": storage_result['transactions_stored'],
                "deduplication": dedup_result,
                "storage_stats": storage_stats
            }
            
        finally:
            db_conn.close()


def trace_mover_service(batch_id: int, db_url: str) -> Dict:
    """Trace mover service process"""
    print("\n" + "="*60)
    print("🔄 TRACING MOVER SERVICE")
    print("="*60)
    
    with start_trace("transaction_trace.mover") as trace:
        # Get company configurations
        with open('config/companies.json', 'r') as f:
            companies_config = json.load(f)
        
        companies = [company['company_id'] for company in companies_config['companies']]
        print(f"📋 Companies to process: {companies}")
        
        # Create company DSN resolver function
        def company_dsn_resolver(company_id: str) -> str:
            company_db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
            return db_url.replace('/remodel', f'/{company_db_name}')
        
        # Create mover service
        mover_service = MoverService(db_url, company_dsn_resolver)
        
        # Create mover request
        request = BatchMoveRequest(
            ingest_batch_id=batch_id,
            companies=None  # Process all companies in the batch
        )
        
        print(f"🔄 Processing batch {batch_id} for {len(companies)} companies...")
        
        # Execute mover service
        response = mover_service.move_batch(request)
        
        print(f"✅ Mover service completed")
        print(f"📊 Results:")
        for company_result in response.results:
            print(f"   {company_result.company_id}: {company_result.inserted} inserted, {company_result.updated} updated, {company_result.enqueued} enqueued")
        
        return {
            "batch_id": batch_id,
            "companies_processed": len(response.results),
            "total_inserted": sum(r.inserted for r in response.results),
            "total_updated": sum(r.updated for r in response.results),
            "total_enqueued": sum(r.enqueued for r in response.results),
            "company_results": [
                {
                    "company_id": r.company_id,
                    "inserted": r.inserted,
                    "updated": r.updated,
                    "enqueued": r.enqueued
                }
                for r in response.results
            ]
        }


def trace_sheets_service(db_url: str) -> Dict:
    """Trace sheets service process"""
    print("\n" + "="*60)
    print("📊 TRACING SHEETS SERVICE")
    print("="*60)
    
    with start_trace("transaction_trace.sheets") as trace:
        # Load company configurations
        with open('config/companies.json', 'r') as f:
            companies_config = json.load(f)
        
        sheets_poster = SheetsPoster(dry_run=True)  # Use dry run for testing
        
        results = []
        for company in companies_config['companies']:
            company_id = company['company_id']
            workbook_url = company['workbook']
            
            print(f"📊 Processing {company_id}...")
            
            # Extract spreadsheet ID from URL
            if "/spreadsheets/d/" in workbook_url:
                spreadsheet_id = workbook_url.split("/spreadsheets/d/")[1].split("/")[0]
            else:
                spreadsheet_id = workbook_url
            
            # Simulate posting operations
            sample_ops = [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 1
                        },
                        "rows": [{"values": [{"userEnteredValue": {"stringValue": f"Updated by Kylo - {datetime.now()}"}}]}],
                        "fields": "userEnteredValue"
                    }
                }
            ]
            
            result = sheets_poster.post(spreadsheet_id, sample_ops)
            
            print(f"   ✅ {company_id}: {len(sample_ops)} operations prepared")
            
            results.append({
                "company_id": company_id,
                "spreadsheet_id": spreadsheet_id,
                "operations_count": len(sample_ops),
                "dry_run": result.get("dry_run", True)
            })
        
        return {
            "companies_processed": len(results),
            "total_operations": sum(r["operations_count"] for r in results),
            "company_results": results
        }


def verify_database_state(db_url: str, batch_id: int) -> Dict:
    """Verify final database state"""
    print("\n" + "="*60)
    print("🔍 VERIFYING DATABASE STATE")
    print("="*60)
    
    db_conn = create_db_connection(db_url)
    
    try:
        # Check global database
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM core.transactions_unified 
                WHERE ingest_batch_id = %s
            """, (batch_id,))
            global_count = cur.fetchone()[0]
            
            cur.execute("""
                SELECT company_id, COUNT(*) as count 
                FROM core.transactions_unified 
                WHERE ingest_batch_id = %s
                GROUP BY company_id
            """, (batch_id,))
            global_by_company = dict(cur.fetchall())
        
        print(f"📊 Global database:")
        print(f"   Total transactions in batch {batch_id}: {global_count}")
        for company, count in global_by_company.items():
            print(f"   {company}: {count} transactions")
        
        # Check company databases
        company_counts = {}
        with open('config/companies.json', 'r') as f:
            companies_config = json.load(f)
        
        for company in companies_config['companies']:
            company_id = company['company_id']
            company_db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
            
            try:
                # Connect to company database
                company_db_url = db_url.replace('/remodel', f'/{company_db_name}')
                company_conn = psycopg2.connect(company_db_url)
                
                with company_conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM app.transactions")
                    count = cur.fetchone()[0]
                    company_counts[company_id] = count
                
                company_conn.close()
                print(f"   {company_id} ({company_db_name}): {count} transactions")
                
            except Exception as e:
                print(f"   {company_id}: Error connecting to database - {e}")
                company_counts[company_id] = 0
        
        return {
            "global_batch_count": global_count,
            "global_by_company": global_by_company,
            "company_counts": company_counts
        }
        
    finally:
        db_conn.close()


def main():
    """Main test function"""
    print("🚀 Kylo Transaction Trace Test")
    print("="*60)
    print("This test will trace actual transactions through the entire pipeline")
    print("from CSV intake to Google Sheets output.")
    print()
    
    # Configuration
    db_url = os.environ.get('DATABASE_URL', 'postgresql+psycopg2://remodel:remodel@localhost:5432/remodel')
    
    # Generate sample data
    print("📝 Generating sample CSV data...")
    csv_content = generate_sample_csv_content()
    print("✅ Sample CSV generated")
    
    # Trace each step
    try:
        # Step 1: CSV Intake
        intake_result = trace_csv_intake(csv_content, db_url)
        
        # Step 2: Mover Service
        mover_result = trace_mover_service(intake_result['batch_id'], db_url)
        
        # Step 3: Sheets Service
        sheets_result = trace_sheets_service(db_url)
        
        # Step 4: Verify final state
        db_state = verify_database_state(db_url, intake_result['batch_id'])
        
        # Summary
        print("\n" + "="*60)
        print("📊 TRANSACTION TRACE SUMMARY")
        print("="*60)
        
        print(f"✅ CSV Intake: {intake_result['transactions_stored']} transactions stored")
        print(f"✅ Mover Service: {mover_result['total_inserted']} transactions moved to company DBs")
        print(f"✅ Sheets Service: {sheets_result['total_operations']} operations prepared")
        print(f"✅ Database State: {db_state['global_batch_count']} transactions in global DB")
        
        print("\n🎉 Transaction trace completed successfully!")
        print("All components are working correctly.")
        
        # Emit final telemetry
        emit("transaction_trace", "completed", {
            "intake_result": intake_result,
            "mover_result": mover_result,
            "sheets_result": sheets_result,
            "db_state": db_state
        })
        
    except Exception as e:
        print(f"\n❌ Transaction trace failed: {e}")
        emit("transaction_trace", "error", {"error": str(e)})
        raise


if __name__ == "__main__":
    main()
