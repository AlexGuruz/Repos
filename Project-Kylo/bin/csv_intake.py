#!/usr/bin/env python3
"""
CSV Intake CLI Tool
Processes petty cash CSV data with comprehensive deduplication
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional

import psycopg2

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.intake.csv_downloader import download_petty_cash_csv, validate_csv_content, get_csv_metadata
from services.intake.csv_processor import PettyCashCSVProcessor, validate_transaction
from services.intake.deduplication import DeduplicationWorkflow, get_deduplication_stats, get_file_processing_history
from services.intake.storage import create_ingest_batch, store_csv_transactions_batch, get_storage_stats, cleanup_temp_data
from telemetry.emitter import start_trace, emit
from services.common.config_loader import load_config
from services.sheets.poster import _extract_spreadsheet_id


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def create_db_connection(db_url: str):
    """Create database connection"""
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)


def _copy_csv_to_configured_paths(csv_content: str, company_key: Optional[str] = None) -> List[str]:
    """
    If config has intake.csv_copy_paths for this company (or _default), write csv_content
    to each path. Paths can be on any drive (e.g. D:, E:). Returns list of paths written.
    """
    written: List[str] = []
    try:
        cfg = load_config()
        raw = cfg.get("intake.csv_copy_paths")
        if not raw:
            return written
        paths: List[str] = []
        if isinstance(raw, list):
            paths = [p for p in raw if isinstance(p, str) and p.strip()]
        elif isinstance(raw, dict):
            key = (company_key or "").strip().upper() or "_default"
            val = raw.get(key) or raw.get("_default")
            if isinstance(val, str):
                paths = [val] if val.strip() else []
            elif isinstance(val, list):
                paths = [p for p in val if isinstance(p, str) and p.strip()]
        for path in paths:
            path = path.strip()
            if not path:
                continue
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(csv_content)
                written.append(path)
                print(f"Copied CSV to {path}")
            except Exception as e:
                print(f"Warning: failed to copy CSV to {path}: {e}", file=sys.stderr)
        return written
    except Exception as e:
        print(f"Warning: could not resolve csv_copy_paths: {e}", file=sys.stderr)
        return written


def process_csv_intake(
    spreadsheet_id: str,
    service_account_path: str,
    db_url: str,
    header_rows: int = 19,
    force_process: bool = False,
    dry_run: bool = False,
    company_key: Optional[str] = None,
) -> Dict:
    """
    Process CSV intake with comprehensive deduplication
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        service_account_path: Path to service account JSON file
        db_url: Database connection URL
        header_rows: Number of header rows to skip
        force_process: Force processing even if file already processed
        dry_run: Don't actually store data, just validate
        company_key: Optional company key (e.g. NUGZ, JGD) for intake.csv_copy_paths routing
    
    Returns:
        Dictionary with processing results
    """
    
    # Start telemetry trace
    with start_trace("csv_intake") as trace:
        emit("csv_intake", "started", {
            "spreadsheet_id": spreadsheet_id,
            "header_rows": header_rows,
            "force_process": force_process,
            "dry_run": dry_run
        })
        
        try:
            # 1. Download CSV
            print("Downloading CSV from Google Sheets...")
            csv_content = download_petty_cash_csv(spreadsheet_id, service_account_path)
            
            # Validate CSV content
            if not validate_csv_content(csv_content):
                raise ValueError("CSV content validation failed")
            
            # Get CSV metadata
            metadata = get_csv_metadata(csv_content)
            print(f"CSV metadata: {json.dumps(metadata, indent=2)}")
            
            emit("csv_intake", "csv_downloaded", {
                "file_fingerprint": metadata['file_fingerprint'],
                "total_lines": metadata['total_lines'],
                "non_empty_lines": metadata['non_empty_lines']
            })
            
            # Copy to configured paths (e.g. D:, E:) if intake.csv_copy_paths is set
            copy_paths = _copy_csv_to_configured_paths(csv_content, company_key=company_key)
            if copy_paths:
                emit("csv_intake", "csv_copied", {"paths": copy_paths})
            
            # 2. Parse transactions
            print("Parsing CSV transactions...")
            processor = PettyCashCSVProcessor(csv_content, header_rows)
            transactions = list(processor.parse_transactions())
            
            processing_stats = processor.get_processing_stats()
            print(f"Processing stats: {json.dumps(processing_stats, indent=2)}")
            
            emit("csv_intake", "transactions_parsed", {
                "transactions_count": len(transactions),
                "unique_rows_processed": processing_stats['unique_rows_processed'],
                "duplicate_rows_skipped": processing_stats['duplicate_rows_skipped']
            })
            
            # 3. Validate transactions
            print("Validating transactions...")
            valid_transactions = []
            invalid_count = 0
            
            for txn in transactions:
                is_valid, errors = validate_transaction(txn)
                if is_valid:
                    valid_transactions.append(txn)
                else:
                    invalid_count += 1
                    print(f"Invalid transaction: {errors}")
            
            print(f"Validation complete: {len(valid_transactions)} valid, {invalid_count} invalid")
            
            if not valid_transactions:
                raise ValueError("No valid transactions found")
            
            emit("csv_intake", "transactions_validated", {
                "valid_count": len(valid_transactions),
                "invalid_count": invalid_count
            })
            
            # 4. Database operations (if not dry run)
            if dry_run:
                print("DRY RUN: Skipping database operations")
                return {
                    "status": "dry_run_completed",
                    "file_fingerprint": metadata['file_fingerprint'],
                    "transactions_parsed": len(transactions),
                    "valid_transactions": len(valid_transactions),
                    "invalid_transactions": invalid_count
                }
            
            # Connect to database
            db_conn = create_db_connection(db_url)
            
            try:
                # 5. Deduplication workflow
                print("Running deduplication workflow...")
                dedup_workflow = DeduplicationWorkflow(db_conn)
                
                # Check if file already processed
                if not force_process and dedup_workflow.check_file_already_processed(metadata['file_fingerprint']):
                    print(f"File {metadata['file_fingerprint']} already processed. Use --force to reprocess.")
                    return {
                        "status": "skipped",
                        "reason": "file_already_processed",
                        "file_fingerprint": metadata['file_fingerprint']
                    }
                
                # 6. Create ingest batch
                print("Creating ingest batch...")
                batch_id = create_ingest_batch(db_conn, "petty_cash_csv")
                print(f"Created batch ID: {batch_id}")
                
                # 7. Process with deduplication
                dedup_result = dedup_workflow.process_with_deduplication(
                    valid_transactions, 
                    metadata['file_fingerprint'], 
                    batch_id
                )
                
                print(f"Deduplication result: {json.dumps(dedup_result, indent=2)}")
                
                if dedup_result['status'] == 'skipped':
                    return dedup_result
                
                # 8. Store transactions
                print("Storing transactions...")
                storage_result = store_csv_transactions_batch(
                    db_conn, 
                    dedup_result['unique_transactions'], 
                    batch_id
                )
                
                print(f"Storage result: {json.dumps(storage_result, indent=2)}")
                
                # 9. Record file processing
                dedup_workflow.record_file_processing(
                    metadata['file_fingerprint'],
                    batch_id,
                    len(valid_transactions)
                )
                
                # 10. Cleanup
                cleanup_temp_data(db_conn)
                
                # 11. Get final stats
                storage_stats = get_storage_stats(db_conn, batch_id)
                
                result = {
                    "status": "completed",
                    "batch_id": batch_id,
                    "file_fingerprint": metadata['file_fingerprint'],
                    "deduplication": dedup_result,
                    "storage": storage_result,
                    "storage_stats": storage_stats
                }
                
                emit("csv_intake", "completed", {
                    "batch_id": batch_id,
                    "file_fingerprint": metadata['file_fingerprint'],
                    "transactions_stored": storage_result['transactions_stored'],
                    "duplicates_skipped": storage_result['duplicates_skipped']
                })
                
                return result
            finally:
                db_conn.close()
                
        except Exception as e:
            emit("csv_intake", "error", {
                "error": str(e),
                "spreadsheet_id": spreadsheet_id
            })
            raise


def run_intake_for_company(company: str, *, dry_run: bool = True, force_process: bool = False, header_rows: Optional[int] = None) -> Dict:
    """Resolve spreadsheetId, service account, and DB DSN from unified config and run intake.

    Returns processing result dict.
    """
    cfg = load_config()
    # Resolve company workbook url
    companies = (cfg.get("sheets.companies") or [])
    url = None
    resolved_key: Optional[str] = None
    for it in companies:
        key = (it.get("key") or "").strip().upper()
        if key == company.strip().upper() or (key == "710" and company.strip().upper() == "710"):
            url = it.get("workbook_url")
            resolved_key = key
            break
    if not url:
        raise RuntimeError(f"Workbook URL not found for company {company}")
    spreadsheet_id = _extract_spreadsheet_id(url)
    sa = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "secrets/service_account.json")
    db_url = cfg.get("database.global_dsn") or os.environ.get("KYLO_GLOBAL_DSN")
    if header_rows is None:
        header_rows = int((cfg.get("intake.csv_processor.header_rows") or 19))
    return process_csv_intake(
        spreadsheet_id, sa, db_url,
        header_rows=header_rows, force_process=force_process, dry_run=dry_run,
        company_key=resolved_key,
    )


def show_stats(db_url: str, days: int = 7):
    """Show deduplication and processing statistics"""
    db_conn = create_db_connection(db_url)
    
    try:
        print(f"\n=== Deduplication Statistics (Last {days} days) ===")
        stats = get_deduplication_stats(db_conn, days)
        
        if not stats['daily_stats']:
            print("No deduplication data found")
            return
        
        for day in stats['daily_stats']:
            print(f"Date: {day['date']}")
            print(f"  Batches: {day['batches_processed']}")
            print(f"  Parsed: {day['total_parsed']}")
            print(f"  Stored: {day['total_stored']}")
            print(f"  Skipped: {day['total_skipped']}")
            print(f"  Dedup %: {day['dedup_percentage']}%")
            print()
        
        print("=== Recent File Processing History ===")
        history = get_file_processing_history(db_conn, 5)
        
        if not history:
            print("No file processing history found")
            return
        
        for record in history:
            print(f"File: {record['file_fingerprint'][:16]}...")
            print(f"  Processed: {record['processed_at']}")
            print(f"  Rows: {record['row_count']}")
            print(f"  Status: {record['status']}")
            print(f"  Batch: {record['batch_id']}")
            print()
            
    finally:
        db_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Process petty cash CSV intake")
    parser.add_argument("--spreadsheet-id", help="Google Sheets spreadsheet ID")
    parser.add_argument("--service-account", help="Service account JSON file path")
    parser.add_argument("--db-url", help="Database connection URL")
    parser.add_argument("--header-rows", type=int, default=19, help="Number of header rows to skip")
    parser.add_argument("--force", action="store_true", help="Force processing even if file already processed")
    parser.add_argument("--dry-run", action="store_true", help="Validate and parse but don't store data")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--stats", action="store_true", help="Show deduplication statistics")
    parser.add_argument("--stats-days", type=int, default=7, help="Number of days for statistics")
    parser.add_argument("--company", help="Resolve spreadsheet and paths from unified config for this company (e.g., NUGZ, 710, PUFFIN, JGD)")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Resolve from config if company provided
    if args.company:
        try:
            res = run_intake_for_company(args.company, dry_run=args.dry_run, force_process=args.force, header_rows=args.header_rows)
            print("\n=== Processing Complete ===")
            print(json.dumps(res, indent=2))
            return
        except Exception as e:
            print(f"\n❌ Processing failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)

    # Validate direct arguments
    if not args.spreadsheet_id or not args.db_url:
        print("Missing --spreadsheet-id or --db-url (or use --company)")
        sys.exit(2)
    if args.service_account and not os.path.exists(args.service_account):
        print(f"Service account file not found: {args.service_account}")
        sys.exit(1)
    
    try:
        if args.stats:
            show_stats(args.db_url, args.stats_days)
        else:
            result = process_csv_intake(
                spreadsheet_id=args.spreadsheet_id,
                service_account_path=args.service_account or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "secrets/service_account.json"),
                db_url=args.db_url,
                header_rows=args.header_rows,
                force_process=args.force,
                dry_run=args.dry_run
            )
            
            print("\n=== Processing Complete ===")
            print(json.dumps(result, indent=2))
            
            if result.get('status') == 'completed':
                print(f"\n✅ Successfully processed {result['storage']['transactions_stored']} transactions")
                print(f"📊 Skipped {result['storage']['duplicates_skipped']} duplicates")
                print(f"🆔 Batch ID: {result['batch_id']}")
            elif result.get('status') == 'skipped':
                print(f"\n⏭️  Skipped processing: {result.get('reason', 'unknown')}")
            else:
                print(f"\n❓ Processing result: {result.get('status', 'unknown')}")
    
    except Exception as e:
        print(f"\n❌ Processing failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
