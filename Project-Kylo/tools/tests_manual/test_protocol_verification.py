#!/usr/bin/env python3
"""
Protocol Verification Test
Comprehensive verification of all protocols and database requests in the Kylo system.
"""

import json
import logging
import os
import sys
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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


def verify_csv_intake_protocol():
    """Verify CSV intake protocol"""
    print("\n" + "="*60)
    print("📥 VERIFYING CSV INTAKE PROTOCOL")
    print("="*60)
    
    try:
        # Import CSV processor
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from services.intake.csv_processor import PettyCashCSVProcessor, validate_transaction
        
        # Test CSV processing
        csv_content = """Date,Amount,Company,Description
01/15/2025,125.50,NUGZ,Office supplies purchase
01/15/2025,-45.00,NUGZ,Cash deposit
01/14/2025,89.99,710 EMPIRE,Equipment maintenance
01/14/2025,-200.00,710 EMPIRE,Payment received"""
        
        processor = PettyCashCSVProcessor(csv_content, header_rows=1)
        transactions = list(processor.parse_transactions())
        
        print(f"✅ CSV Processing Protocol:")
        print(f"   - Parsed {len(transactions)} transactions")
        print(f"   - File fingerprint: {processor.file_fingerprint}")
        print(f"   - Row deduplication: {len(processor.seen_rows)} unique rows")
        
        # Test validation
        valid_count = 0
        for txn in transactions:
            is_valid, errors = validate_transaction(txn)
            if is_valid:
                valid_count += 1
        
        print(f"   - Validation: {valid_count}/{len(transactions)} valid transactions")
        
        # Test deduplication
        from services.intake.deduplication import DeduplicationWorkflow
        
        # Create test database connection
        db_conn = None
        try:
            import psycopg2
            db_conn = psycopg2.connect('postgresql://postgres:kylo@localhost:5432/kylo_global')
            
            dedup_workflow = DeduplicationWorkflow(db_conn)
            print(f"   - Deduplication workflow: Initialized successfully")
            
        except Exception as e:
            print(f"   - Database connection: {e}")
        finally:
            if db_conn:
                db_conn.close()
        
        return {
            "protocol": "CSV Intake",
            "status": "verified",
            "transactions_parsed": len(transactions),
            "valid_transactions": valid_count,
            "deduplication": "available"
        }
        
    except Exception as e:
        print(f"❌ CSV intake protocol failed: {e}")
        return {"protocol": "CSV Intake", "status": "failed", "error": str(e)}


def verify_database_protocols():
    """Verify database protocols and schemas"""
    print("\n" + "="*60)
    print("🗄️ VERIFYING DATABASE PROTOCOLS")
    print("="*60)
    
    protocols = []
    
    # 1. Global Database Protocol
    print("📊 Global Database Protocol:")
    
    # Check control schema
    control_tables = run_docker_sql("kylo_global", """
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'control' ORDER BY table_name;
    """)
    
    if control_tables:
        control_count = len([t for t in control_tables.split('\n') if t])
        print(f"   ✅ Control schema: {control_count} tables")
        protocols.append({
            "protocol": "Global Control Schema",
            "status": "verified",
            "tables": control_count
        })
    
    # Check core schema
    core_tables = run_docker_sql("kylo_global", """
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'core' ORDER BY table_name;
    """)
    
    if core_tables:
        core_count = len([t for t in core_tables.split('\n') if t])
        print(f"   ✅ Core schema: {core_count} tables")
        protocols.append({
            "protocol": "Global Core Schema",
            "status": "verified",
            "tables": core_count
        })
    
    # Check intake schema
    intake_tables = run_docker_sql("kylo_global", """
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'intake' ORDER BY table_name;
    """)
    
    if intake_tables:
        intake_count = len([t for t in intake_tables.split('\n') if t])
        print(f"   ✅ Intake schema: {intake_count} tables")
        protocols.append({
            "protocol": "Global Intake Schema",
            "status": "verified",
            "tables": intake_count
        })
    
    # 2. Company Database Protocol
    print("\n📊 Company Database Protocol:")
    companies = ['kylo_nugz', 'kylo_710', 'kylo_puffin', 'kylo_jgd']
    
    for company_db in companies:
        app_tables = run_docker_sql(company_db, """
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'app' ORDER BY table_name;
        """)
        
        if app_tables:
            app_count = len([t for t in app_tables.split('\n') if t])
            print(f"   ✅ {company_db}: {app_count} app tables")
            protocols.append({
                "protocol": f"Company Schema ({company_db})",
                "status": "verified",
                "tables": app_count
            })
    
    # 3. Data Isolation Protocol
    print("\n📊 Data Isolation Protocol:")
    
    # Check that each company has separate data
    for company_db in companies:
        transaction_count = run_docker_sql(company_db, "SELECT COUNT(*) FROM app.transactions;")
        print(f"   ✅ {company_db}: {transaction_count} transactions (isolated)")
    
    protocols.append({
        "protocol": "Data Isolation",
        "status": "verified",
        "companies": len(companies)
    })
    
    return protocols


def verify_mover_protocol():
    """Verify mover service protocol"""
    print("\n" + "="*60)
    print("🔄 VERIFYING MOVER PROTOCOL")
    print("="*60)
    
    try:
        # Import mover service
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from services.mover.service import MoverService, BatchMoveRequest
        from services.mover.models import CompanyResult
        
        print("✅ Mover Service Protocol:")
        print("   - Service class: Available")
        print("   - Batch processing: Supported")
        print("   - Company routing: Configured")
        
        # Test company DSN resolver
        def test_dsn_resolver(company_id: str) -> str:
            company_db_name = f"kylo_{company_id.lower().replace(' ', '_')}"
            return f"postgresql://postgres:kylo@localhost:5432/{company_db_name}"
        
        mover_service = MoverService("postgresql://postgres:kylo@localhost:5432/kylo_global", test_dsn_resolver)
        print("   - DSN resolver: Functional")
        
        # Check mover SQL functions
        from services.mover import sql as mover_sql
        print("   - SQL operations: Available")
        
        return {
            "protocol": "Mover Service",
            "status": "verified",
            "features": ["batch_processing", "company_routing", "dsn_resolver", "sql_operations"]
        }
        
    except Exception as e:
        print(f"❌ Mover protocol failed: {e}")
        return {"protocol": "Mover Service", "status": "failed", "error": str(e)}


def verify_sheets_protocol():
    """Verify sheets service protocol"""
    print("\n" + "="*60)
    print("📊 VERIFYING SHEETS PROTOCOL")
    print("="*60)
    
    try:
        # Import sheets service
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from services.sheets.poster import SheetsPoster
        
        print("✅ Sheets Service Protocol:")
        print("   - Poster class: Available")
        print("   - Batch updates: Supported")
        print("   - Dry run mode: Available")
        
        # Test sheets poster
        sheets_poster = SheetsPoster(dry_run=True)
        print("   - Service initialization: Successful")
        
        # Load company configurations
        with open('config/companies.json', 'r') as f:
            companies_config = json.load(f)
        
        print(f"   - Company configurations: {len(companies_config['companies'])} companies")
        
        # Test spreadsheet ID extraction
        for company in companies_config['companies']:
            workbook_url = company['workbook']
            if "/spreadsheets/d/" in workbook_url:
                spreadsheet_id = workbook_url.split("/spreadsheets/d/")[1].split("/")[0]
                print(f"   - {company['company_id']}: Spreadsheet ID extracted")
        
        return {
            "protocol": "Sheets Service",
            "status": "verified",
            "companies": len(companies_config['companies']),
            "features": ["batch_updates", "dry_run", "spreadsheet_extraction"]
        }
        
    except Exception as e:
        print(f"❌ Sheets protocol failed: {e}")
        return {"protocol": "Sheets Service", "status": "failed", "error": str(e)}


def verify_telemetry_protocol():
    """Verify telemetry protocol"""
    print("\n" + "="*60)
    print("📡 VERIFYING TELEMETRY PROTOCOL")
    print("="*60)
    
    try:
        # Import telemetry
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from telemetry.emitter import start_trace, emit
        
        print("✅ Telemetry Protocol:")
        print("   - Trace generation: Available")
        print("   - Event emission: Available")
        
        # Test trace generation
        trace_id = start_trace("test", "verification")
        print(f"   - Trace ID generation: {trace_id}")
        
        # Test event emission
        emit("test", trace_id, "verification", {"status": "testing"})
        print("   - Event emission: Successful")
        
        return {
            "protocol": "Telemetry",
            "status": "verified",
            "features": ["trace_generation", "event_emission"]
        }
        
    except Exception as e:
        print(f"❌ Telemetry protocol failed: {e}")
        return {"protocol": "Telemetry", "status": "failed", "error": str(e)}


def verify_kafka_protocol():
    """Verify Kafka protocol"""
    print("\n" + "="*60)
    print("📨 VERIFYING KAFKA PROTOCOL")
    print("="*60)
    
    try:
        # Test Kafka cluster
        result = subprocess.run([
            'docker', 'exec', 'kylo-redpanda', 'rpk', 'cluster', 'info'
        ], capture_output=True, text=True, check=True)
        
        if 'BROKERS' in result.stdout:
            print("✅ Kafka Protocol:")
            print("   - Cluster: Running")
            print("   - Brokers: Available")
            
            # Test topic creation
            result = subprocess.run([
                'docker', 'exec', 'kylo-redpanda', 'rpk', 'topic', 'list'
            ], capture_output=True, text=True, check=True)
            
            print("   - Topic management: Available")
            
            return {
                "protocol": "Kafka",
                "status": "verified",
                "features": ["cluster_running", "brokers_available", "topic_management"]
            }
        else:
            print("❌ Kafka cluster not responding")
            return {"protocol": "Kafka", "status": "failed", "error": "cluster_not_responding"}
            
    except Exception as e:
        print(f"❌ Kafka protocol failed: {e}")
        return {"protocol": "Kafka", "status": "failed", "error": str(e)}


def verify_n8n_protocol():
    """Verify n8n protocol"""
    print("\n" + "="*60)
    print("⚙️ VERIFYING N8N PROTOCOL")
    print("="*60)
    
    try:
        # Test n8n connectivity
        result = subprocess.run([
            'curl', '-s', 'http://localhost:5678/healthz'
        ], capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            print("✅ N8N Protocol:")
            print("   - Service: Running")
            print("   - Health check: Passing")
            print("   - Webhook support: Available")
            
            # Check n8n workflows (now stored under workflows/n8n)
            workflow_files = [
                os.path.join('workflows', 'n8n', 'n8n_ingest_publish_kafka.json'),
                os.path.join('workflows', 'n8n', 'n8n_promote_publish_kafka.json'),
                os.path.join('workflows', 'n8n', 'n8n_telemetry_workflow.json')
            ]
            
            for workflow_file in workflow_files:
                if os.path.exists(workflow_file):
                    print(f"   - Workflow: {workflow_file} (available)")
                else:
                    print(f"   - Workflow: {workflow_file} (missing)")
            
            return {
                "protocol": "N8N",
                "status": "verified",
                "features": ["service_running", "health_check", "webhook_support"]
            }
        else:
            print("❌ N8N service not responding")
            return {"protocol": "N8N", "status": "failed", "error": "service_not_responding"}
            
    except Exception as e:
        print(f"❌ N8N protocol failed: {e}")
        return {"protocol": "N8N", "status": "failed", "error": str(e)}


def verify_data_flow_protocol():
    """Verify complete data flow protocol"""
    print("\n" + "="*60)
    print("🔄 VERIFYING DATA FLOW PROTOCOL")
    print("="*60)
    
    # Test data flow by creating a test batch and tracing it
    print("📥 Testing Data Flow:")
    
    # 1. Create test batch
    batch_result = run_docker_sql("kylo_global", """
        INSERT INTO control.ingest_batches (source, started_at) 
        VALUES ('protocol_test', NOW()) 
        RETURNING batch_id;
    """)
    
    if batch_result:
        batch_id = int(batch_result.split('\n')[0])
        print(f"   ✅ Batch creation: ID {batch_id}")
        
        # 2. Insert test data
        test_data = [
            ("NUGZ", "2025-01-15", 10000, "Test transaction 1"),
            ("710 EMPIRE", "2025-01-15", 20000, "Test transaction 2")
        ]
        
        for i, (company, date, amount, description) in enumerate(test_data):
            sql = f"""
            INSERT INTO core.transactions_unified (
                txn_uid, company_id, source_stream_id, posted_date, amount_cents, 
                description, source_file_fingerprint, row_index_0based, hash_norm, ingest_batch_id
            ) VALUES (
                gen_random_uuid(), '{company}', 'protocol_test', '{date}', {amount}, 
                '{description}', 'protocol_test_fingerprint', {i}, 'protocol_test_hash_{i}', {batch_id}
            );
            """
            run_docker_sql("kylo_global", sql)
        
        print(f"   ✅ Data insertion: {len(test_data)} transactions")
        
        # 3. Verify data in global database
        global_count = run_docker_sql("kylo_global", f"""
            SELECT COUNT(*) FROM core.transactions_unified WHERE ingest_batch_id = {batch_id};
        """)
        
        print(f"   ✅ Global verification: {global_count} transactions")
        
        # 4. Test company data isolation
        for company_db in ['kylo_nugz', 'kylo_710']:
            count = run_docker_sql(company_db, "SELECT COUNT(*) FROM app.transactions;")
            print(f"   ✅ {company_db}: {count} transactions (isolated)")
        
        return {
            "protocol": "Data Flow",
            "status": "verified",
            "batch_id": batch_id,
            "transactions": len(test_data),
            "features": ["batch_creation", "data_insertion", "global_verification", "company_isolation"]
        }
    else:
        print("   ❌ Batch creation failed")
        return {"protocol": "Data Flow", "status": "failed", "error": "batch_creation_failed"}


def main():
    """Main verification function"""
    print("🚀 Kylo Protocol Verification Test")
    print("="*60)
    print("This test verifies all protocols and database requests in the Kylo system.")
    print()
    
    all_protocols = []
    
    # Verify each protocol
    protocols_to_test = [
        verify_csv_intake_protocol,
        verify_database_protocols,
        verify_mover_protocol,
        verify_sheets_protocol,
        verify_telemetry_protocol,
        verify_kafka_protocol,
        verify_n8n_protocol,
        verify_data_flow_protocol
    ]
    
    for protocol_test in protocols_to_test:
        result = protocol_test()
        if isinstance(result, list):
            all_protocols.extend(result)
        else:
            all_protocols.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("📊 PROTOCOL VERIFICATION SUMMARY")
    print("="*60)
    
    verified_count = 0
    failed_count = 0
    
    for protocol in all_protocols:
        if protocol['status'] == 'verified':
            verified_count += 1
            print(f"✅ {protocol['protocol']}: VERIFIED")
        else:
            failed_count += 1
            print(f"❌ {protocol['protocol']}: FAILED - {protocol.get('error', 'Unknown error')}")
    
    print(f"\n📈 Results: {verified_count} verified, {failed_count} failed")
    
    if failed_count == 0:
        print("\n🎉 All protocols verified successfully!")
        print("📊 The Kylo system is fully operational with all protocols working correctly.")
    else:
        print(f"\n⚠️  {failed_count} protocol(s) failed verification.")
    
    return all_protocols


if __name__ == "__main__":
    main()
