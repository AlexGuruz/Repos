#!/usr/bin/env python3
"""
System Health Check for Kylo
Tests all components from data ingestion to Google Sheets outputs
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import pytest

def test_docker_services():
    """Test if Docker services are running"""
    print("🔍 Testing Docker Services...")
    
    result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"Docker not available or not running (docker ps exit={result.returncode}): {result.stderr.strip()}")
    # Validate containers that exist in this repo's compose files
    required = ["kylo-pg", "kylo-redpanda", "kylo-redpanda-console"]
    missing = [c for c in required if c not in result.stdout]
    assert not missing, f"Missing required Docker containers: {missing}"

def test_database_schema():
    """Test database schema and connectivity"""
    print("\n🗄️ Testing Database Schema...")
    
    # Global schema must exist
    result = subprocess.run([
        'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-d', 'kylo_global',
        '-t', '-c', "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('control', 'core', 'intake');"
    ], capture_output=True, text=True)
    assert result.returncode == 0, f"Global DB query failed: {result.stderr.strip()}"
    table_count = int(result.stdout.strip() or "0")
    assert table_count >= 7, f"Global schema looks incomplete (tables={table_count})"

    # Company DBs may vary by setup; check one canonical company if present
    result = subprocess.run([
        'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-t', '-c',
        "SELECT 1 FROM pg_database WHERE datname = 'kylo_nugz';"
    ], capture_output=True, text=True)
    assert result.returncode == 0, f"DB existence query failed: {result.stderr.strip()}"
    if (result.stdout or "").strip() != "1":
        pytest.skip("Company DB kylo_nugz not present; run setup_db.py to provision company DBs.")

    result = subprocess.run([
        'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-d', 'kylo_nugz',
        '-t', '-c', "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'app';"
    ], capture_output=True, text=True)
    assert result.returncode == 0, f"Company DB query failed: {result.stderr.strip()}"
    table_count = int(result.stdout.strip() or "0")
    assert table_count >= 5, f"Company schema looks incomplete (tables={table_count})"

def test_csv_intake_service():
    """Test CSV intake service components"""
    print("\n📥 Testing CSV Intake Service...")
    
    from services.intake.csv_processor import PettyCashCSVProcessor, validate_transaction

    # Minimal petty-cash shaped CSV (legacy mapping)
    sample_csv = """Initials,Date,Company,Description,Amount,Posted
ZAC,01/15/2025,NUGZ,STARBUCKS COFFEE,25.50,FALSE
ZAC,01/15/2025,710 EMPIRE,WALMART GROCERIES,150.00,FALSE"""

    processor = PettyCashCSVProcessor(sample_csv, header_rows=1)
    transactions = list(processor.parse_transactions())
    assert len(transactions) == 2, f"CSV processor expected 2 transactions, got {len(transactions)}"

    is_valid, errors = validate_transaction(transactions[0])
    assert is_valid, f"Transaction validation failed: {errors}"

def test_mover_service():
    """Test mover service components"""
    print("\n🔄 Testing Mover Service...")
    
    from services.mover.models import BatchMoveRequest, CompanyScope

    request = BatchMoveRequest(
        ingest_batch_id=1,
        companies=[CompanyScope(company_id="test")]
    )
    assert request.ingest_batch_id == 1

def test_sheets_service():
    """Test sheets service components"""
    print("\n📊 Testing Sheets Service...")
    
    from services.sheets.poster import SheetsPoster, build_batch_update

    poster = SheetsPoster(dry_run=True)
    assert poster.dry_run is True

    changes = [{"test": "data"}]
    batch = build_batch_update(changes)
    assert "requests" in batch

def test_telemetry():
    """Test telemetry system"""
    print("\n📡 Testing Telemetry System...")
    
    from telemetry.emitter import start_trace, emit

    trace_id = start_trace("test", "test-company")
    assert trace_id
    emit("test", trace_id, "test_step", {"test": "data"})

def test_kafka():
    """Test Kafka connectivity"""
    print("\n📨 Testing Kafka Connectivity...")
    
    result = subprocess.run([
        'docker', 'exec', 'kylo-redpanda', 'rpk', 'cluster', 'info'
    ], capture_output=True, text=True)
    assert result.returncode == 0, f"Kafka cluster info failed: {result.stderr.strip()}"
    assert 'BROKERS' in result.stdout, "Kafka cluster did not return BROKERS output"

def test_configuration():
    """Test configuration files"""
    print("\n⚙️ Testing Configuration...")
    
    with open('config/companies.json', 'r') as f:
        companies_config = json.load(f)

    assert 'companies' in companies_config and len(companies_config['companies']) > 0, "companies.json missing/empty"

    for company in companies_config['companies']:
        layout_file = company.get('layout_ref')
        assert layout_file and Path(layout_file).exists(), f"Layout file missing for {company.get('company_id')}"

def test_unit_tests():
    """Run unit tests"""
    print("\n🧪 Running Unit Tests...")
    
    result = subprocess.run([
        'python', '-m', 'pytest', 'scaffold/tests/test_csv_intake.py', '-q'
    ], capture_output=True, text=True)
    assert result.returncode == 0, f"Unit tests failed:\n{result.stdout}\n{result.stderr}"

def main():
    """Run all system health checks"""
    print("🚀 Kylo System Health Check")
    print("=" * 50)
    
    tests = [
        test_docker_services,
        test_database_schema,
        test_csv_intake_service,
        test_mover_service,
        test_sheets_service,
        test_telemetry,
        test_kafka,
        test_configuration,
        test_unit_tests
    ]
    
    passed = 0
    total = len(tests)
    for test in tests:
        try:
            test()
            passed += 1
        except pytest.SkipTest as e:
            print(f"⏭️  Skipped {test.__name__}: {e}")
        except Exception as e:
            print(f"❌ Failed {test.__name__}: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Health Check Summary: {passed}/{total} checks passed (some may be skipped)")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
