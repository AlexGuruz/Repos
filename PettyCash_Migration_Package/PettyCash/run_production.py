#!/usr/bin/env python3
"""
Production Launch Script for Petty Cash Sorter
Comprehensive startup with validation, monitoring, and error handling
"""

import sys
import os
import time
import signal
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from petty_cash_sorter_final_comprehensive import PettyCashSorterFinal
from config_manager import ConfigManager

class ProductionLauncher:
    """Production launcher with comprehensive startup and monitoring."""
    
    def __init__(self):
        self.sorter = None
        self.config_manager = None
        self.running = False
        self.startup_time = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n⚠️ Received signal {signum}, shutting down gracefully...")
        self.shutdown()
    
    def validate_environment(self) -> bool:
        """Validate the production environment."""
        print("🔍 VALIDATING PRODUCTION ENVIRONMENT")
        print("=" * 60)
        
        try:
            # Load configuration
            self.config_manager = ConfigManager()
            
            # Run startup validation
            validation_results = self.config_manager.validate_startup_requirements()
            
            # Print validation report
            self.config_manager.print_validation_report(validation_results)
            
            if validation_results['overall_status'] != 'PASS':
                print("❌ Environment validation failed!")
                return False
            
            print("✅ Environment validation passed!")
            return True
            
        except Exception as e:
            print(f"❌ Environment validation error: {e}")
            return False
    
    def run_preflight_checks(self) -> bool:
        """Run preflight checks before starting the system."""
        print("\n✈️ RUNNING PREFLIGHT CHECKS")
        print("=" * 60)
        
        try:
            # Check Python version
            python_version = sys.version_info
            if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
                print(f"❌ Python version {python_version.major}.{python_version.minor} is too old. Required: 3.8+")
                return False
            print(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
            
            # Check required packages
            required_packages = [
                ('gspread', 'gspread'),
                ('google-auth', 'google.auth'),
                ('openpyxl', 'openpyxl'),
                ('pandas', 'pandas'),
                ('psutil', 'psutil'),
                ('flask', 'flask'),
                ('flask_socketio', 'flask_socketio')
            ]
            
            missing_packages = []
            for package_name, import_name in required_packages:
                try:
                    __import__(import_name)
                    print(f"✅ {package_name}")
                except ImportError:
                    missing_packages.append(package_name)
                    print(f"❌ {package_name} - MISSING")
            
            if missing_packages:
                print(f"\n❌ Missing required packages: {missing_packages}")
                print("Install with: pip install -r requirements.txt")
                return False
            
            # Check disk space
            disk_usage = self._check_disk_space()
            if disk_usage < 100:  # Less than 100MB free
                print(f"❌ Low disk space: {disk_usage}MB free")
                return False
            print(f"✅ Disk space: {disk_usage}MB free")
            
            # Check memory
            memory_available = self._check_memory()
            if memory_available < 512:  # Less than 512MB available
                print(f"❌ Low memory: {memory_available}MB available")
                return False
            print(f"✅ Memory: {memory_available}MB available")
            
            print("✅ All preflight checks passed!")
            return True
            
        except Exception as e:
            print(f"❌ Preflight check error: {e}")
            return False
    
    def _check_disk_space(self) -> int:
        """Check available disk space in MB."""
        try:
            import shutil
            total, used, free = shutil.disk_usage('.')
            return free // (1024 * 1024)  # Convert to MB
        except:
            return 1000  # Assume sufficient space
    
    def _check_memory(self) -> int:
        """Check available memory in MB."""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.available // (1024 * 1024)  # Convert to MB
        except:
            return 1000  # Assume sufficient memory
    
    def initialize_system(self) -> bool:
        """Initialize the petty cash sorter system."""
        print("\n🚀 INITIALIZING SYSTEM")
        print("=" * 60)
        
        try:
            self.startup_time = time.time()
            
            # Initialize the sorter
            self.sorter = PettyCashSorterFinal()
            
            # Initialize system
            if not self.sorter.initialize_system():
                print("❌ System initialization failed!")
                return False
            
            print("✅ System initialized successfully!")
            
            # Get initial system status
            status = self.sorter.get_system_status()
            health = status.get('system_health', {})
            
            print(f"📊 System Health: {health.get('status', 'unknown')} ({health.get('health_score', 0)}/100)")
            
            if health.get('health_score', 0) < 70:
                print("⚠️ System health is below optimal levels")
            
            return True
            
        except Exception as e:
            print(f"❌ System initialization error: {e}")
            return False
    
    def run_processing(self) -> bool:
        """Run the main processing operation."""
        print("\n⚙️ STARTING TRANSACTION PROCESSING")
        print("=" * 60)
        
        try:
            # Process all transactions
            result = self.sorter.process_all_transactions()
            
            if result['status'] == 'success':
                print("✅ Processing completed successfully!")
                
                # Print final statistics
                final_stats = result.get('final_stats', {})
                print(f"📊 Final Statistics:")
                print(f"  • Total transactions processed: {final_stats.get('total_transactions_processed', 0)}")
                print(f"  • Total batches: {final_stats.get('total_batches', 0)}")
                print(f"  • Rule suggestions: {final_stats.get('rule_suggestions', 0)}")
                print(f"  • Retry successes: {final_stats.get('retry_successes', 0)}")
                print(f"  • Remaining failures: {final_stats.get('remaining_failures', 0)}")
                
                return True
            else:
                print(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Processing error: {e}")
            return False
    
    def generate_reports(self) -> bool:
        """Generate comprehensive reports."""
        print("\n📊 GENERATING REPORTS")
        print("=" * 60)
        
        try:
            # Generate comprehensive report
            report_file = self.sorter.generate_comprehensive_report()
            
            if report_file:
                print(f"✅ Comprehensive report saved: {report_file}")
            else:
                print("❌ Failed to generate comprehensive report")
                return False
            
            # Print system status summary
            status = self.sorter.get_system_status()
            
            print(f"\n📈 System Status Summary:")
            print(f"  • Database transactions: {status.get('database', {}).get('total_transactions', 0)}")
            print(f"  • Rules loaded: {status.get('rules', {}).get('total_rules', 0)}")
            print(f"  • Pending transactions: {status.get('pending_transactions', 0)}")
            print(f"  • AI matcher rules: {status.get('ai_matcher_rules_loaded', 0)}")
            print(f"  • System health: {status.get('system_health', {}).get('status', 'unknown')}")
            
            return True
            
        except Exception as e:
            print(f"❌ Report generation error: {e}")
            return False
    
    def shutdown(self):
        """Graceful shutdown of the system."""
        print("\n🔄 SHUTTING DOWN SYSTEM")
        print("=" * 60)
        
        try:
            self.running = False
            
            if self.sorter:
                # Cleanup and shutdown
                self.sorter.cleanup_and_shutdown()
            
            # Calculate runtime
            if self.startup_time:
                runtime = time.time() - self.startup_time
                print(f"⏱️ Total runtime: {runtime:.1f} seconds")
            
            print("✅ System shutdown complete")
            
        except Exception as e:
            print(f"❌ Shutdown error: {e}")
    
    def run(self) -> int:
        """Main production run method."""
        print("🚀 PETTY CASH SORTER - PRODUCTION LAUNCH")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            self.running = True
            
            # Step 1: Validate environment
            if not self.validate_environment():
                return 1
            
            # Step 2: Run preflight checks
            if not self.run_preflight_checks():
                return 1
            
            # Step 3: Initialize system
            if not self.initialize_system():
                return 1
            
            # Step 4: Run processing
            if not self.run_processing():
                return 1
            
            # Step 5: Generate reports
            if not self.generate_reports():
                return 1
            
            print("\n🎉 PRODUCTION RUN COMPLETED SUCCESSFULLY!")
            return 0
            
        except KeyboardInterrupt:
            print("\n⚠️ Process interrupted by user")
            return 1
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return 1
        finally:
            self.shutdown()

def main():
    """Main entry point."""
    launcher = ProductionLauncher()
    exit_code = launcher.run()
    
    print(f"\n👋 Goodbye! Exit code: {exit_code}")
    return exit_code

if __name__ == "__main__":
    sys.exit(main()) 