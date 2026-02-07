#!/usr/bin/env python3
"""
Test Runner for Petty Cash Sorter
Executes comprehensive unit tests and provides detailed reporting
"""

import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime

def run_unit_tests():
    """Run all unit tests."""
    print("🧪 RUNNING UNIT TESTS")
    print("=" * 60)
    
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Import and run tests
        from tests.test_petty_cash_sorter import run_tests
        success = run_tests()
        
        if success:
            print("✅ All unit tests passed!")
        else:
            print("❌ Some unit tests failed!")
        
        return success
        
    except ImportError as e:
        print(f"❌ Could not import test module: {e}")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_integration_tests():
    """Run integration tests."""
    print("\n🔗 RUNNING INTEGRATION TESTS")
    print("=" * 60)
    
    try:
        # Test configuration loading
        print("Testing configuration management...")
        from config_manager import ConfigManager
        
        # Create test configuration
        test_config = {
            "system": {"name": "Test System", "version": "1.0.0", "environment": "test"},
            "google_sheets": {
                "petty_cash_url": "https://test.com",
                "financials_spreadsheet_url": "https://test.com",
                "petty_cash_worksheet": "TEST PETTY CASH",
                "service_account_file": "config/service_account.json",
                "scopes": ["https://test.com"]
            },
            "database": {"path": "config/test_db.db", "backup_enabled": False},
            "processing": {"batch_size": 10, "min_confidence": 5, "max_confidence": 10},
            "ai_matching": {"confidence_threshold": 0.75, "min_threshold": 0.5, "max_threshold": 0.95},
            "api_rate_limiting": {"enabled": True, "requests_per_minute": 60, "burst_limit": 10},
            "monitoring": {"enabled": True, "log_level": "INFO"},
            "files": {
                "jgd_truth_file": "JGD Truth Current.xlsx",
                "layout_map_cache": "config/layout_map_cache.json"
            },
            "directories": {
                "logs": "logs",
                "data": "data",
                "reports": "reports"
            },
            "sheets_to_skip": [],
            "column_mapping": {"initials": 0, "date": 1, "company": 2, "source": 3, "amount": 18}
        }
        
        # Write test config
        test_config_file = "config/test_config.json"
        import json
        with open(test_config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Test config manager
        config_manager = ConfigManager(test_config_file)
        validation_results = config_manager.validate_startup_requirements()
        
        if validation_results['overall_status'] == 'PASS':
            print("✅ Configuration management test passed")
        else:
            print("❌ Configuration management test failed")
            return False
        
        # Test API rate limiter
        print("Testing API rate limiter...")
        from api_rate_limiter import APIRateLimiter, RateLimitConfig
        
        rate_config = RateLimitConfig(requests_per_minute=10, burst_limit=3)
        rate_limiter = APIRateLimiter(rate_config)
        
        # Test token acquisition
        limiter = rate_limiter.get_limiter("test")
        for i in range(3):
            if not limiter.acquire_token():
                print("❌ API rate limiter test failed")
                return False
        
        print("✅ API rate limiter test passed")
        
        # Test database manager
        print("Testing database manager...")
        from database_manager import DatabaseManager
        
        db_manager = DatabaseManager("config/test_db.db")
        if db_manager.create_database():
            print("✅ Database manager test passed")
        else:
            print("❌ Database manager test failed")
            return False
        
        # Clean up test files
        if Path(test_config_file).exists():
            Path(test_config_file).unlink()
        if Path("config/test_db.db").exists():
            Path("config/test_db.db").unlink()
        
        print("✅ All integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test error: {e}")
        return False

def run_performance_tests():
    """Run performance tests."""
    print("\n⚡ RUNNING PERFORMANCE TESTS")
    print("=" * 60)
    
    try:
        # Test AI rule matcher performance
        print("Testing AI rule matcher performance...")
        from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher
        
        ai_matcher = AIEnhancedRuleMatcher()
        
        # Test source normalization performance
        test_sources = ["TEST SOURCE", "test source", "  Test Source  ", "TEST-SOURCE"] * 1000
        
        start_time = time.time()
        for source in test_sources:
            ai_matcher.normalize_source(source)
        normalization_time = time.time() - start_time
        
        print(f"✅ Normalized {len(test_sources)} sources in {normalization_time:.3f}s")
        print(f"   Rate: {len(test_sources) / normalization_time:.0f} sources/second")
        
        # Test similarity calculation performance
        test_pairs = [("TEST SOURCE", "TEST SOURCE"), ("TEST", "DIFFERENT")] * 500
        
        start_time = time.time()
        for source1, source2 in test_pairs:
            ai_matcher.calculate_similarity(source1, source2)
        similarity_time = time.time() - start_time
        
        print(f"✅ Calculated {len(test_pairs)} similarities in {similarity_time:.3f}s")
        print(f"   Rate: {len(test_pairs) / similarity_time:.0f} calculations/second")
        
        print("✅ All performance tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Performance test error: {e}")
        return False

def run_system_validation():
    """Run system validation tests."""
    print("\n🔍 RUNNING SYSTEM VALIDATION")
    print("=" * 60)
    
    try:
        # Check required files
        required_files = [
            "config/system_config.json",
            "config/service_account.json",
            "JGD Truth Current.xlsx"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ Missing required files: {missing_files}")
            return False
        else:
            print("✅ All required files present")
        
        # Check required directories
        required_dirs = ["logs", "data", "reports", "config"]
        missing_dirs = []
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                missing_dirs.append(dir_path)
        
        if missing_dirs:
            print(f"⚠️ Missing directories (will be created): {missing_dirs}")
        else:
            print("✅ All required directories present")
        
        # Test configuration loading
        print("Testing configuration loading...")
        from config_manager import ConfigManager
        
        config_manager = ConfigManager()
        validation_results = config_manager.validate_startup_requirements()
        
        if validation_results['overall_status'] == 'PASS':
            print("✅ Configuration validation passed")
        else:
            print("❌ Configuration validation failed")
            for error in validation_results['errors']:
                print(f"   • {error}")
            return False
        
        print("✅ All system validation tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ System validation error: {e}")
        return False

def generate_test_report(results):
    """Generate comprehensive test report."""
    report_file = f"reports/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'test_results': results,
        'summary': {
            'total_tests': len(results),
            'passed': sum(1 for result in results.values() if result),
            'failed': sum(1 for result in results.values() if not result),
            'success_rate': sum(1 for result in results.values() if result) / len(results) * 100
        }
    }
    
    # Ensure reports directory exists
    Path("reports").mkdir(exist_ok=True)
    
    # Save report
    import json
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report_file

def main():
    """Main test runner function."""
    print("🚀 PETTY CASH SORTER - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run all test suites
    test_results = {}
    
    # Unit tests
    test_results['unit_tests'] = run_unit_tests()
    
    # Integration tests
    test_results['integration_tests'] = run_integration_tests()
    
    # Performance tests
    test_results['performance_tests'] = run_performance_tests()
    
    # System validation
    test_results['system_validation'] = run_system_validation()
    
    # Generate report
    print("\n📊 GENERATING TEST REPORT")
    print("=" * 60)
    
    report_file = generate_test_report(test_results)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"Total Test Suites: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    print(f"\nDetailed Results:")
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n📄 Test report saved: {report_file}")
    
    if success_rate == 100:
        print("\n🎉 ALL TESTS PASSED! System is ready for production.")
        return 0
    else:
        print(f"\n⚠️ {failed_tests} test suite(s) failed. Please review and fix issues.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 