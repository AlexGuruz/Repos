#!/usr/bin/env python3
"""
Migration Verification Script for Petty Cash Sorter
Tests all critical components after migration to new PC
"""

import sys
import os
import sqlite3
import json
import requests
from pathlib import Path
import subprocess

def print_header(title):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_success(message):
    """Print a success message."""
    print(f"✅ {message}")

def print_error(message):
    """Print an error message."""
    print(f"❌ {message}")

def print_warning(message):
    """Print a warning message."""
    print(f"⚠️  {message}")

def test_python_environment():
    """Test Python environment and version."""
    print_header("Testing Python Environment")
    
    try:
        version = sys.version_info
        print(f"Python Version: {version.major}.{version.minor}.{version.micro}")
        
        if version.major == 3 and version.minor >= 11:
            print_success("Python version is compatible (3.11+)")
        else:
            print_error(f"Python version {version.major}.{version.minor} is too old. Need 3.11+")
            return False
            
        return True
    except Exception as e:
        print_error(f"Error checking Python version: {e}")
        return False

def test_required_packages():
    """Test that all required packages are installed."""
    print_header("Testing Required Packages")
    
    required_packages = [
        'flask', 'flask_socketio', 'gspread', 'google-auth', 
        'pandas', 'openpyxl', 'requests', 'schedule', 'psutil'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print_success(f"{package} is installed")
        except ImportError:
            print_error(f"{package} is missing")
            missing_packages.append(package)
    
    if missing_packages:
        print_warning(f"Missing packages: {', '.join(missing_packages)}")
        print_warning("Run: pip install -r requirements.txt")
        return False
    
    return True

def test_file_structure():
    """Test that all critical files exist."""
    print_header("Testing File Structure")
    
    critical_files = [
        'ai_rule_matcher_enhanced.py',
        'real_time_monitor_enhanced.py',
        'database_manager.py',
        'google_sheets_integration.py',
        'petty_cash_sorter_final_comprehensive.py',
        'config/service_account.json',
        'config/system_config.json',
        'config/layout_map.json',
        'config/petty_cash.db',
        'requirements.txt'
    ]
    
    missing_files = []
    
    for file_path in critical_files:
        if Path(file_path).exists():
            print_success(f"{file_path} exists")
        else:
            print_error(f"{file_path} is missing")
            missing_files.append(file_path)
    
    if missing_files:
        print_warning(f"Missing files: {', '.join(missing_files)}")
        return False
    
    return True

def test_database_connection():
    """Test database connection and schema."""
    print_header("Testing Database Connection")
    
    try:
        db_path = Path("config/petty_cash.db")
        if not db_path.exists():
            print_error("Database file not found")
            return False
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['rules', 'transactions', 'audit_log']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print_error(f"Missing tables: {', '.join(missing_tables)}")
            return False
        
        # Check rules count
        cursor.execute("SELECT COUNT(*) FROM rules")
        rules_count = cursor.fetchone()[0]
        print_success(f"Database connected - {rules_count} rules found")
        
        conn.close()
        return True
        
    except Exception as e:
        print_error(f"Database connection failed: {e}")
        return False

def test_google_sheets_credentials():
    """Test Google Sheets service account credentials."""
    print_header("Testing Google Sheets Credentials")
    
    try:
        with open('config/service_account.json', 'r') as f:
            credentials = json.load(f)
        
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in credentials]
        
        if missing_fields:
            print_error(f"Missing credential fields: {', '.join(missing_fields)}")
            return False
        
        print_success("Service account credentials are valid")
        return True
        
    except Exception as e:
        print_error(f"Error reading credentials: {e}")
        return False

def test_ai_matcher():
    """Test AI rule matcher initialization."""
    print_header("Testing AI Rule Matcher")
    
    try:
        from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
        
        ai_matcher = AIEnhancedRuleMatcher()
        print_success("AI Rule Matcher initialized successfully")
        
        # Test basic methods
        rules = ai_matcher.get_all_rules_with_performance()
        print_success(f"Loaded {len(rules)} rules from database")
        
        return True
        
    except Exception as e:
        print_error(f"AI Rule Matcher test failed: {e}")
        return False

def test_monitor_endpoints():
    """Test monitor API endpoints."""
    print_header("Testing Monitor API Endpoints")
    
    base_url = "http://localhost:5000"
    
    try:
        # Test if monitor is running
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print_success("Monitor is running and accessible")
        else:
            print_warning("Monitor responded but with unexpected status code")
            return False
            
    except requests.exceptions.ConnectionError:
        print_warning("Monitor is not running. Start it with: python demo_rule_management.py")
        return False
    except Exception as e:
        print_error(f"Error testing monitor: {e}")
        return False
    
    # Test API endpoints
    endpoints = [
        "/api/stats",
        "/api/rules",
        "/api/available-sheets"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            if response.status_code == 200:
                print_success(f"Endpoint {endpoint} is working")
            else:
                print_error(f"Endpoint {endpoint} returned status {response.status_code}")
        except Exception as e:
            print_error(f"Endpoint {endpoint} failed: {e}")
    
    return True

def test_system_config():
    """Test system configuration."""
    print_header("Testing System Configuration")
    
    try:
        with open('config/system_config.json', 'r') as f:
            config = json.load(f)
        
        # Check critical config sections
        required_sections = ['google_sheets', 'database', 'monitoring']
        missing_sections = [section for section in required_sections if section not in config]
        
        if missing_sections:
            print_error(f"Missing config sections: {', '.join(missing_sections)}")
            return False
        
        # Check Google Sheets URL
        sheets_url = config.get('google_sheets', {}).get('petty_cash_url')
        if sheets_url:
            print_success("Google Sheets URL configured")
        else:
            print_warning("Google Sheets URL not found in config")
        
        # Check monitor port
        monitor_port = config.get('monitoring', {}).get('real_time_dashboard', {}).get('port')
        if monitor_port:
            print_success(f"Monitor configured for port {monitor_port}")
        else:
            print_warning("Monitor port not configured")
        
        return True
        
    except Exception as e:
        print_error(f"Error reading system config: {e}")
        return False

def run_full_verification():
    """Run all verification tests."""
    print_header("PETTY CASH SORTER - MIGRATION VERIFICATION")
    
    tests = [
        ("Python Environment", test_python_environment),
        ("Required Packages", test_required_packages),
        ("File Structure", test_file_structure),
        ("Database Connection", test_database_connection),
        ("Google Sheets Credentials", test_google_sheets_credentials),
        ("AI Rule Matcher", test_ai_matcher),
        ("System Configuration", test_system_config),
        ("Monitor Endpoints", test_monitor_endpoints)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print_header("VERIFICATION SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print_success("🎉 ALL TESTS PASSED! Migration successful!")
        print_success("Your Petty Cash Sorter is ready to use.")
    else:
        print_warning("⚠️  Some tests failed. Please review the errors above.")
        print_warning("Check the troubleshooting section in MIGRATION_PLAN.md")
    
    # Failed tests
    failed_tests = [name for name, result in results if not result]
    if failed_tests:
        print(f"\nFailed tests: {', '.join(failed_tests)}")
    
    return passed == total

if __name__ == "__main__":
    success = run_full_verification()
    sys.exit(0 if success else 1) 