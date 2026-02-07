#!/usr/bin/env python3
"""
Test script for Kylo Telemetry Workflow
Demonstrates all telemetry events from the complete Kylo system workflow
"""

import os
import time
from telemetry.emitter import emit, start_trace

def test_full_kylo_workflow():
    """Test the complete Kylo system workflow telemetry"""
    
    # Set up telemetry to send to n8n
    os.environ["TELEMETRY_SINK"] = "http"
    os.environ["N8N_WEBHOOK_URL"] = "http://localhost:5678/webhook/kylo-telemetry"
    
    print("🚀 Testing Complete Kylo System Workflow...")
    print("📡 Sending events to n8n at: http://localhost:5678/webhook/kylo-telemetry")
    print()
    
    # Test companies
    companies = ["test-company", "demo-corp", "sample-llc"]
    
    for company_id in companies:
        print(f"🏢 Processing company: {company_id}")
        
        # 1. IMPORTER EVENTS (Rule Processing Pipeline)
        print("  📥 Importer events...")
        importer_trace = start_trace("importer", company_id)
        
        emit("importer", importer_trace, "validation_started", {
            "company_id": company_id,
            "file_name": f"rules_{company_id}_2025.xlsx",
            "total_rows": 150
        })
        time.sleep(0.3)
        
        emit("importer", importer_trace, "validation_completed", {
            "company_id": company_id,
            "valid_rows": 145,
            "invalid_rows": 5,
            "errors": ["FUTURE_DATE", "SOURCE_EMPTY"]
        })
        time.sleep(0.3)
        
        emit("importer", importer_trace, "duplicates_found", {
            "company_id": company_id,
            "duplicates_count": 3,
            "duplicate_sources": ["amazon.com", "netflix.com"]
        })
        time.sleep(0.3)
        
        emit("importer", importer_trace, "file_loaded", {
            "company_id": company_id,
            "file_name": f"rules_{company_id}_2025.xlsx",
            "rows_processed": 150
        })
        time.sleep(0.3)
        
        emit("importer", importer_trace, "rules_promoted", {
            "company_id": company_id,
            "rules_count": 45,
            "version": 3,
            "checksum": "md5:abc123def456"
        })
        time.sleep(0.3)
        
        emit("importer", importer_trace, "active_updated", {
            "company_id": company_id,
            "active_rules": 42,
            "duplicates_skipped": 3,
            "sheets_updated": [f"Active Rules – {company_id}"]
        })
        time.sleep(0.3)
        
        # 2. MOVER EVENTS (Data Movement Pipeline)
        print("  🔄 Mover events...")
        mover_trace = start_trace("mover", company_id)
        
        emit("mover", mover_trace, "batch_fetched", {
            "company_id": company_id,
            "batch_id": 20250101,
            "total_companies": 3,
            "global_connection": "established"
        })
        time.sleep(0.3)
        
        emit("mover", mover_trace, "company_processing_started", {
            "company_id": company_id,
            "batch_id": 20250101,
            "company_connection": "established"
        })
        time.sleep(0.3)
        
        emit("mover", mover_trace, "upsert_started", {
            "company_id": company_id,
            "batch_size": 1250,
            "batch_id": 20250101,
            "temp_table": "stg_txn_created"
        })
        time.sleep(0.3)
        
        emit("mover", mover_trace, "transaction_processed", {
            "company_id": company_id,
            "transactions_processed": 1250,
            "hash_collisions": 0
        })
        time.sleep(0.3)
        
        emit("mover", mover_trace, "rows_enqueued", {
            "company_id": company_id,
            "enqueued": 1180,
            "inserted": 950,
            "updated": 230,
            "sort_queue_updated": True
        })
        time.sleep(0.3)
        
        emit("mover", mover_trace, "watermark_advanced", {
            "company_id": company_id,
            "batch_id": 20250101,
            "watermark_updated": True,
            "last_batch_id": 20250101
        })
        time.sleep(0.3)
        
        emit("mover", mover_trace, "company_processing_completed", {
            "company_id": company_id,
            "batch_id": 20250101,
            "duration_ms": 2500,
            "success": True
        })
        time.sleep(0.3)
        
        # 3. POSTER EVENTS (Sheets Update Pipeline)
        print("  📤 Poster events...")
        poster_trace = start_trace("poster", company_id)
        
        emit("poster", poster_trace, "sheets_connected", {
            "company_id": company_id,
            "spreadsheet_id": f"1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "connection_status": "authenticated"
        })
        time.sleep(0.3)
        
        emit("poster", poster_trace, "projection_calculated", {
            "company_id": company_id,
            "transactions_count": 1180,
            "categories_count": 45,
            "projection_time_ms": 150
        })
        time.sleep(0.3)
        
        emit("poster", poster_trace, "batch_update_built", {
            "company_id": company_id,
            "updates_count": 1180,
            "sheets_updated": ["Transactions", "Categories"],
            "batch_size": 1180,
            "request_built": True
        })
        time.sleep(0.3)
        
        emit("poster", poster_trace, "batch_update_sent", {
            "company_id": company_id,
            "batch_id": "batch_20250101_001",
            "success": True,
            "response_time_ms": 1250,
            "sheets_api_calls": 1
        })
        time.sleep(0.3)
        
        emit("poster", poster_trace, "sheets_response_received", {
            "company_id": company_id,
            "response_status": 200,
            "updated_cells": 1180,
            "response_time_ms": 1250
        })
        time.sleep(0.3)
        
        emit("poster", poster_trace, "cells_updated", {
            "company_id": company_id,
            "cells_updated": 1180,
            "sheets_updated": ["Transactions", "Categories"],
            "update_success": True
        })
        time.sleep(0.3)
        
        print(f"  ✅ Completed processing for {company_id}")
        print()
        time.sleep(1)
    
    print("🎉 All Kylo system telemetry events sent!")
    print("📊 Check n8n at http://localhost:5678 to see the complete workflow in action")
    print("🔗 Webhook URL: http://localhost:5678/webhook/kylo-telemetry")
    print()
    print("📋 System Components Tested:")
    print("  • Importer: Rule validation, promotion, and active sheet updates")
    print("  • Mover: Batch fetching, company processing, database operations")
    print("  • Poster: Sheets connection, projection calculation, batch updates")

if __name__ == "__main__":
    test_full_kylo_workflow()
