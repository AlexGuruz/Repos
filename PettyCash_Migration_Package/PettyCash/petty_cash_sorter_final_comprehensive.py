#!/usr/bin/env python3
"""
Petty Cash Sorter - Final Comprehensive Version
Complete integration with all advanced features from the final script
"""

import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from database_manager import DatabaseManager
from csv_downloader_fixed import CSVDownloader
from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher as AIRuleMatcher
from google_sheets_integration import GoogleSheetsIntegration
from performance_monitor import ProgressMonitor, ErrorRecovery, PerformanceMetrics
from audit_and_reporting import AuditAndReporting
from config_manager import ConfigManager
from api_rate_limiter import APIRateLimiter, RateLimitConfig
from real_time_monitor import RealTimeMonitor
from processed_transaction_manager import ProcessedTransactionManager
import threading

class PettyCashSorterFinal:
    """Complete petty cash sorter with all advanced features."""
    
    def __init__(self, config_file: str = "config/system_config.json"):
        # Initialize configuration manager first
        try:
            self.config_manager = ConfigManager(config_file)
            logging.info("✅ Configuration loaded successfully")
        except Exception as e:
            logging.error(f"❌ Failed to load configuration: {e}")
            raise
        
        # Initialize all components with configuration
        self.db_manager = DatabaseManager(self.config_manager.get('database.path'))
        self.csv_downloader = CSVDownloader()
        # Remove rule_loader - AI matcher will handle rules from database
        self.ai_matcher = AIRuleMatcher()
        self.sheets_integration = GoogleSheetsIntegration()
        
        # Filing system for processed transactions
        filing_path = self.config_manager.get('filing_system.base_path', 'data/processed_transactions')
        self.filing_manager = ProcessedTransactionManager(filing_path)
        
        # Performance and monitoring components
        self.progress_monitor = ProgressMonitor()
        self.error_recovery = ErrorRecovery()
        self.performance_metrics = PerformanceMetrics()
        self.audit_reporter = AuditAndReporting()
        
        # API rate limiting
        rate_limit_config = RateLimitConfig(
            requests_per_minute=self.config_manager.get('api_rate_limiting.requests_per_minute', 60),
            burst_limit=self.config_manager.get('api_rate_limiting.burst_limit', 10),
            cooldown_period_seconds=self.config_manager.get('api_rate_limiting.cooldown_period_seconds', 60),
            enabled=self.config_manager.get('api_rate_limiting.enabled', True)
        )
        self.api_rate_limiter = APIRateLimiter(rate_limit_config)
        
        # Real-time monitoring
        self.real_time_monitor = None
        if self.config_manager.get('monitoring.real_time_dashboard.enabled', False):
            try:
                self.real_time_monitor = RealTimeMonitor(self.config_manager.get_section('monitoring'))
                logging.info("✅ Real-time monitoring initialized")
            except Exception as e:
                logging.warning(f"⚠️ Real-time monitoring not available: {e}")
        
        # Configuration
        self.batch_size = self.config_manager.get('processing.batch_size', 100)
        self.min_confidence = self.config_manager.get('processing.min_confidence', 5)
        self.session_id = None
        
        # Create directories
        for dir_name, dir_path in self.config_manager.get_section('directories').items():
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        log_level = getattr(logging, self.config_manager.get('monitoring.log_level', 'INFO'))
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f"{self.config_manager.get('directories.logs')}/petty_cash_sorter_final.log"),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING PETTY CASH SORTER - FINAL COMPREHENSIVE VERSION")
        logging.info("=" * 80)
        
        # Log startup validation
        self._log_startup_validation()
    
    def _log_startup_validation(self):
        """Log startup validation results."""
        validation_results = self.config_manager.validate_startup_requirements()
        
        logging.info("STARTUP VALIDATION RESULTS:")
        logging.info("=" * 50)
        
        for check_name, check_result in validation_results['checks'].items():
            status_icon = {
                'PASS': '✅',
                'FAIL': '❌',
                'WARNING': '⚠️',
                'INFO': 'ℹ️'
            }.get(check_result['status'], '❓')
            
            logging.info(f"{status_icon} {check_name}: {check_result['message']}")
        
        if validation_results['errors']:
            logging.error("VALIDATION ERRORS:")
            for error in validation_results['errors']:
                logging.error(f"  • {error}")
        
        if validation_results['warnings']:
            logging.warning("VALIDATION WARNINGS:")
            for warning in validation_results['warnings']:
                logging.warning(f"  • {warning}")
        
        logging.info(f"Overall Status: {validation_results['overall_status']}")
        logging.info("=" * 50)
    
    def initialize_system(self) -> bool:
        """Initialize the complete system with all components."""
        try:
            logging.info("🚀 Initializing complete system...")
            
            # Validate startup requirements
            validation_results = self.config_manager.validate_startup_requirements()
            if validation_results['overall_status'] != 'PASS':
                logging.error("❌ Startup validation failed")
                return False
            
            # Start audit session
            self.session_id = self.audit_reporter.start_audit_session(
                "System Initialization",
                "Complete system initialization including database, rules, and Google Sheets"
            )
            
            # Start performance monitoring
            self.performance_metrics.start_monitoring()
            
            # Start real-time monitoring if enabled
            if self.real_time_monitor:
                monitor_config = self.config_manager.get_section('monitoring')['real_time_dashboard']
                monitor_thread = threading.Thread(
                    target=self.real_time_monitor.start_monitoring,
                    kwargs={
                        'port': monitor_config.get('port', 5000),
                        'host': monitor_config.get('host', 'localhost')
                    },
                    daemon=True
                )
                monitor_thread.start()
                logging.info("🚀 Real-time monitoring started")
            
            # Test Google Sheets connection (skip if using in-memory calculation)
            logging.info("🔗 Testing Google Sheets connection...")
            try:
                # Check if we have cached layout map data
                layout_map_file = Path("config/layout_map.json")
                if layout_map_file.exists() and layout_map_file.stat().st_size > 1000:
                    logging.info("✅ Using cached layout map - skipping connection test")
                    sheets_connected = True
                else:
                    @self.api_rate_limiter.rate_limited("sheets_connection")
                    def test_sheets_connection():
                        return self.sheets_integration.test_connection()
                    
                    sheets_connected = test_sheets_connection()
                
                if not sheets_connected:
                    logging.warning("⚠️ Google Sheets connection test failed - continuing with cached layout map")
                    # Don't fail initialization - we can work with cached data
                else:
                    logging.info("✅ Google Sheets connection successful")
            except Exception as e:
                logging.warning(f"⚠️ Google Sheets connection test failed: {e} - continuing with cached layout map")
                # Don't fail initialization - we can work with cached data
            
            # 2. Create database
            self.audit_reporter.log_audit_event(
                self.session_id, "database_creation", {"status": "creating"}
            )
            
            if not self.db_manager.create_database():
                self.audit_reporter.log_audit_event(
                    self.session_id, "database_creation_failed", {"error": "Database creation failed"}, "error"
                )
                return False
            
            self.audit_reporter.log_audit_event(
                self.session_id, "database_creation_success", {"status": "created"}
            )
            
            # 3. Load rules into AI matcher from database (persistent memory)
            self.audit_reporter.log_audit_event(
                self.session_id, "ai_matcher_loading", {"status": "loading from database"}
            )
            
            if not self.ai_matcher.load_rules_from_database():
                self.audit_reporter.log_audit_event(
                    self.session_id, "ai_matcher_loading_failed", {"error": "AI matcher loading failed"}, "error"
                )
                return False
            
            self.audit_reporter.log_audit_event(
                self.session_id, "ai_matcher_loading_success", {"status": "loaded from database"}
            )
            
            # Layout map will be created after transaction download
            # to ensure proper sequence and configuration
            
            # Update real-time monitor
            if self.real_time_monitor:
                try:
                    self.real_time_monitor.update_system_status('healthy')
                    self.real_time_monitor.add_log_entry('SUCCESS', 'System initialization completed successfully')
                except Exception as monitor_error:
                    logging.warning(f"Failed to update system status: {monitor_error}")
            
            # End initialization session
            self.audit_reporter.end_audit_session(self.session_id, {
                "status": "success",
                "components_initialized": 5
            })
            
            logging.info("✅ Complete system initialization successful")
            return True
            
        except Exception as e:
            logging.error(f"❌ Error initializing system: {e}")
            if self.session_id:
                self.audit_reporter.log_audit_event(
                    self.session_id, "initialization_error", {"error": str(e)}, "error"
                )
                self.audit_reporter.end_audit_session(self.session_id, {"status": "failed"})
            
            if self.real_time_monitor:
                try:
                    self.real_time_monitor.update_system_status('error')
                    self.real_time_monitor.add_log_entry('ERROR', f'System initialization failed: {e}')
                except Exception as monitor_error:
                    logging.warning(f"Failed to log initialization error: {monitor_error}")
            
            return False
    
    def download_and_process_transactions(self) -> Optional[List[Dict]]:
        """Download transactions and identify new ones with error recovery."""
        try:
            logging.info("📥 Loading transactions from existing CSV file...")
            
            # Start progress monitoring
            self.progress_monitor.start_operation(
                "Transaction Loading",
                0,  # Will update with actual count
                "Loading and processing petty cash transactions from CSV"
            )
            
            # Use existing CSV file instead of downloading fresh data
            csv_file = self.csv_downloader.get_latest_csv_file()
            if not csv_file:
                logging.error("No CSV file found - cannot proceed without transaction data")
                return None
            
            logging.info(f"📄 Using existing CSV file: {csv_file}")
            
            # Load transactions from CSV file
            import pandas as pd
            df = pd.read_csv(csv_file)
            
            # Convert DataFrame to list of dictionaries
            all_transactions = []
            for index, row in df.iterrows():
                transaction = {
                    'transaction_id': row.get('transaction_id', f"row_{index}"),
                    'row_number': row.get('row_number', index + 1),
                    'initials': row.get('initials', ''),
                    'date': row.get('date', ''),
                    'company': row.get('company', ''),
                    'source': row.get('source', ''),
                    'amount': row.get('amount', 0.0),
                    'processed': False
                }
                all_transactions.append(transaction)
            
            # Update progress monitor with actual count
            self.progress_monitor.total_items = len(all_transactions)
            self.progress_monitor.update_progress(0, f"Loaded {len(all_transactions)} transactions from CSV")
            
            logging.info(f"📊 Loaded {len(all_transactions)} total transactions from CSV")
            
            # Identify new transactions (not in database)
            new_transactions = []
            for i, transaction in enumerate(all_transactions):
                existing = self.db_manager.get_transaction_by_row(transaction['row_number'])
                if not existing:
                    new_transactions.append(transaction)
                
                # Update progress every 100 transactions
                if (i + 1) % 100 == 0:
                    self.progress_monitor.update_progress(100, f"Processed {i + 1} transactions")
            
            self.progress_monitor.update_progress(
                len(all_transactions) - (len(all_transactions) % 100),
                f"Found {len(new_transactions)} new transactions"
            )
            
            logging.info(f"🆕 Found {len(new_transactions)} new transactions to process")
            
            # Create layout map after transaction download (skip if using cached layout map)
            self.audit_reporter.log_audit_event(
                self.session_id, "layout_map_creation", {"status": "using cached layout map"}
            )
            
            logging.info("🗺️ Using cached layout map for coordinate calculation")
            # Skip layout map creation since we have the cached version working
            # @self.api_rate_limiter.rate_limited("layout_map")
            # def create_layout_map():
            #     return self.sheets_integration.create_layout_map(self.config_manager)
            # 
            # layout_map_created = create_layout_map()
            # if not layout_map_created:
            #     logging.warning("⚠️ Layout map creation failed - continuing with cached version")
            # else:
            #     logging.info("✅ Layout map created successfully")
            
            # Update real-time monitor
            if self.real_time_monitor:
                try:
                    self.real_time_monitor.update_transaction_count(len(all_transactions))
                    self.real_time_monitor.update_new_transaction_count(len(new_transactions))
                    self.real_time_monitor.add_log_entry('INFO', f'Loaded {len(all_transactions)} transactions, {len(new_transactions)} new')
                except Exception as monitor_error:
                    logging.warning(f"Failed to update monitor: {monitor_error}")
            
            return new_transactions
            
        except Exception as e:
            logging.error(f"Error loading transactions from CSV: {e}")
            return None
    
    def process_transactions_batch(self, transactions: List[Dict]) -> Dict:
        """Process a batch of transactions with comprehensive tracking."""
        try:
            logging.info(f"⚙️ Processing batch of {len(transactions)} transactions...")
            
            # Start progress monitoring for this batch
            self.progress_monitor.start_operation(
                f"Batch Processing",
                len(transactions),
                f"Processing batch of {len(transactions)} transactions"
            )
            
            # Add transactions to database
            added_count = 0
            for transaction in transactions:
                if self.db_manager.add_transaction(transaction):
                    added_count += 1
                    # Update status to pending
                    self.db_manager.update_transaction_status(
                        transaction['transaction_id'], 
                        'pending', 
                        'Added to processing queue'
                    )
                
                self.progress_monitor.update_progress(1)
            
            logging.info(f"💾 Added {added_count}/{len(transactions)} transactions to database")
            
            # Match transactions to rules
            self.progress_monitor.update_progress(0, "Matching transactions to rules...")
            match_results = self.ai_matcher.batch_match_transactions(transactions)
            
            # Process matched transactions
            processed_count = 0
            sheet_groups = {}  # Group updates by sheet for batch processing
            
            # Prepare coordinate requests for batch processing
            coordinate_requests = []
            for match_data in match_results['matched']:
                transaction = match_data['transaction']
                match = match_data['match']
                
                # Extract target sheet and header from rule
                target_sheet = match['rule']['target_sheet']
                target_header = match['rule']['target_header']
                
                coordinate_requests.append({
                    'target_sheet': target_sheet,
                    'target_header': target_header,
                    'date': transaction['date'],
                    'transaction': transaction,
                    'match': match
                })
            
            # Batch find all coordinates in memory (no API calls)
            if coordinate_requests:
                logging.info(f"🧮 Calculating coordinates in memory for {len(coordinate_requests)} transactions...")
                
                coordinate_results = self.sheets_integration.batch_calculate_coordinates_in_memory(coordinate_requests)
                logging.info(f"✅ Calculated coordinates for {len([r for r in coordinate_results.values() if r])} transactions")
            
            # Process each matched transaction with pre-found coordinates
            for i, match_data in enumerate(match_results['matched']):
                transaction = match_data['transaction']
                match = match_data['match']
                
                # Update match statistics
                self.audit_reporter.update_match_statistics(match)
                
                # Update status based on confidence
                if match['confidence'] >= 0.9:
                    status = 'high_confidence'
                elif match['confidence'] >= 0.7:
                    status = 'medium_confidence'
                else:
                    status = 'low_confidence'
                
                # Extract target sheet and header from rule
                target_sheet = match['rule']['target_sheet']
                target_header = match['rule']['target_header']
                
                # Get pre-found coordinates
                request_key = f"{target_sheet}_{target_header}_{transaction['date']}"
                cell_coords = coordinate_results.get(request_key) if coordinate_requests else None
                
                if cell_coords:
                    # Update transaction with match information including coordinates
                    self.db_manager.update_transaction_with_match(
                        transaction['transaction_id'],
                        status,
                        match['matched_source'],
                        target_sheet,
                        target_header,
                        f"Matched to '{match['matched_source']}' with confidence {match['confidence']}",
                        target_cell_row=cell_coords['row'],
                        target_cell_col=cell_coords['col'],
                        target_cell_address=f"{cell_coords['sheet']}!{cell_coords['row']}{cell_coords['col']}"
                    )
                    
                    # Group by sheet for batch update
                    sheet_name = cell_coords['sheet']
                    if sheet_name not in sheet_groups:
                        sheet_groups[sheet_name] = {}
                    
                    cell_key = f"{cell_coords['row']}_{cell_coords['col']}"
                    
                    # Accumulate amounts for the same cell (don't overwrite!)
                    if cell_key in sheet_groups[sheet_name]:
                        # Add to existing amount
                        sheet_groups[sheet_name][cell_key]['amount'] += transaction['amount']
                        logging.info(f"➕ Accumulated: {sheet_name} cell ({cell_coords['row']},{cell_coords['col']}) += ${transaction['amount']:.2f} (Total: ${sheet_groups[sheet_name][cell_key]['amount']:.2f})")
                    else:
                        # First transaction for this cell
                        sheet_groups[sheet_name][cell_key] = {
                            'row': cell_coords['row'],
                            'col': cell_coords['col'],
                            'amount': transaction['amount']
                        }
                        logging.info(f"✅ Queued: {sheet_name} cell ({cell_coords['row']},{cell_coords['col']}) = ${transaction['amount']:.2f}")
                    
                    processed_count += 1
                else:
                    # Update transaction without coordinates (coordinates not found)
                    self.db_manager.update_transaction_with_match(
                        transaction['transaction_id'],
                        status,
                        match['matched_source'],
                        target_sheet,
                        target_header,
                        f"Matched to '{match['matched_source']}' with confidence {match['confidence']} - COORDINATES NOT FOUND"
                    )
                    logging.warning(f"⚠️ Could not find coordinates for {target_sheet} -> {target_header} on {transaction['date']}")
                
                self.progress_monitor.update_progress(1)
            
            # Mark unmatched transactions
            for transaction in match_results['unmatched']:
                self.db_manager.update_transaction_status(
                    transaction['transaction_id'],
                    'unmatched',
                    'No matching rule found'
                )
                
                # File unmatched transaction
                try:
                    self.filing_manager.file_unmatched_transaction(transaction)
                except Exception as e:
                    logging.warning(f"⚠️ Failed to file unmatched transaction {transaction['transaction_id']}: {e}")
                
                self.progress_monitor.update_progress(1)
            
            # Execute batch updates grouped by sheet/tab
            if sheet_groups:
                logging.info(f"📊 Executing batch updates for {len(sheet_groups)} sheets...")
                
                @self.api_rate_limiter.rate_limited("batch_update_sheets")
                def batch_update_sheets():
                    return self.sheets_integration.batch_update_sheets_by_tab(sheet_groups)
                
                update_results = batch_update_sheets()
                
                if update_results:
                    successful_updates = update_results.get('successful_updates', 0)
                    sheets_updated = update_results.get('sheets_updated', 0)
                    total_cells = update_results.get('total_cells_updated', 0)
                    
                    logging.info(f"✅ Batch updates completed: {successful_updates} cells updated across {sheets_updated} sheets")
                    logging.info(f"📊 Total cells processed: {total_cells}")
                    
                    if update_results.get('errors'):
                        logging.warning(f"⚠️ {len(update_results['errors'])} errors occurred during batch updates")
                        for error in update_results['errors']:
                            logging.warning(f"  • {error}")
                else:
                    logging.error("❌ Batch update failed")
            else:
                logging.info("📭 No sheet updates to process")
            
            # Get statistics
            stats = self.ai_matcher.get_matching_statistics(match_results)
            
            # Update real-time monitor
            if self.real_time_monitor:
                try:
                    success_rate = stats.get('match_rate_percent', 0)
                    self.real_time_monitor.update_transaction_stats(
                        stats.get('total_transactions', 0), 
                        success_rate
                    )
                    self.real_time_monitor.add_log_entry('INFO', f'Batch processed: {stats.get("matched_count", 0)}/{stats.get("total_transactions", 0)} matched ({success_rate:.1f}%)')
                except Exception as monitor_error:
                    logging.warning(f"Real-time monitor update failed: {monitor_error}")
            
            # Update API rate limiter stats
            try:
                api_stats = self.api_rate_limiter.get_all_stats()
                if self.real_time_monitor and 'global' in api_stats:
                    self.real_time_monitor.update_api_stats(api_stats['global'].get('success_rate', 0))
            except Exception as api_error:
                logging.warning(f"API stats update failed: {api_error}")
            
            # Update performance metrics
            self.audit_reporter.update_performance_metrics({
                'processed_transactions': len(transactions),
                'matched_transactions': stats['matched_count'],
                'api_calls': len(sheet_groups) if sheet_groups else 0
            })
            
            self.progress_monitor.finish_operation()
            
            logging.info(f"✅ Batch processing complete:")
            logging.info(f"  📊 Total: {stats['total_transactions']}")
            logging.info(f"  ✅ Matched: {stats['matched_count']}")
            logging.info(f"  ❌ Unmatched: {stats['unmatched_count']}")
            logging.info(f"  📈 Match rate: {stats['match_rate_percent']}%")
            
            return {
                'batch_size': len(transactions),
                'added_to_db': added_count,
                'match_results': match_results,
                'statistics': stats,
                'sheets_updated': len(sheet_groups) if sheet_groups else 0
            }
        
        except Exception as e:
            logging.error(f"❌ Error processing transaction batch: {e}")
            self.progress_monitor.finish_operation()
            
            if self.real_time_monitor:
                try:
                    self.real_time_monitor.add_log_entry('ERROR', f'Batch processing failed: {e}')
                except Exception as monitor_error:
                    logging.warning(f"Failed to log error to real-time monitor: {monitor_error}")
            
            return {'error': str(e)}
    
    def process_all_transactions(self, max_batch_size: int = None) -> Dict:
        """Process all new transactions with comprehensive monitoring and reporting."""
        try:
            if max_batch_size:
                self.batch_size = max_batch_size
            
            # Start new audit session for full processing
            processing_session_id = self.audit_reporter.start_audit_session(
                "Full Transaction Processing",
                f"Processing all new transactions with batch size {self.batch_size}"
            )
            
            logging.info(f"🚀 Starting full transaction processing (batch size: {self.batch_size})")
            
            # Download and identify new transactions
            new_transactions = self.download_and_process_transactions()
            if not new_transactions:
                logging.info("📭 No new transactions to process")
                self.audit_reporter.end_audit_session(processing_session_id, {
                    'status': 'no_new_transactions'
                })
                return {'status': 'no_new_transactions'}
            
            # Start progress monitoring for full processing
            self.progress_monitor.start_operation(
                "Full Processing",
                len(new_transactions),
                f"Processing {len(new_transactions)} new transactions"
            )
            
            # Process in batches
            total_processed = 0
            batch_results = []
            
            for i in range(0, len(new_transactions), self.batch_size):
                batch = new_transactions[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(new_transactions) + self.batch_size - 1) // self.batch_size
                
                logging.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} transactions)")
                
                # Log batch start
                self.audit_reporter.log_audit_event(
                    processing_session_id,
                    "batch_start",
                    {
                        'batch_number': batch_num,
                        'total_batches': total_batches,
                        'batch_size': len(batch)
                    }
                )
                
                batch_result = self.process_transactions_batch(batch)
                batch_results.append(batch_result)
                total_processed += len(batch)
                
                # Log batch completion
                self.audit_reporter.log_audit_event(
                    processing_session_id,
                    "batch_complete",
                    {
                        'batch_number': batch_num,
                        'results': batch_result
                    }
                )
                
                # Small delay between batches
                time.sleep(1)
            
            # Generate rule suggestions for unmatched transactions
            unmatched_transactions = []
            for batch_result in batch_results:
                if 'match_results' in batch_result:
                    unmatched_transactions.extend(batch_result['match_results']['unmatched'])
            
            suggestions = []
            if unmatched_transactions:
                logging.info(f"💡 Generating rule suggestions for {len(unmatched_transactions)} unmatched transactions...")
                
                # Use the new AI analysis system with sheet/header analysis and learning
                suggestions = self.ai_matcher.analyze_unmatched_transactions(
                    unmatched_transactions, 
                    self.sheets_integration,
                    self.db_manager
                )
                
                if suggestions:
                    # Save suggestions for user review
                    self.ai_matcher.save_rule_suggestions(suggestions)
                    logging.info(f"💡 Generated and saved {len(suggestions)} rule suggestions for user review")
                else:
                    logging.info("💡 No rule suggestions generated")
            
            # Retry failed Google Sheets updates
            retry_results = self.sheets_integration.retry_failed_cells()
            if retry_results['successful_retries'] > 0:
                logging.info(f"🔄 Successfully retried {retry_results['successful_retries']} failed updates")
            
            # Flush all pending filing transactions
            try:
                self.filing_manager.flush_all_pending()
                logging.info("✅ All pending transactions filed successfully")
            except Exception as e:
                logging.warning(f"⚠️ Error flushing filing transactions: {e}")
            
            # Get filing statistics
            filing_stats = self.filing_manager.get_filing_statistics()
            
            # Final statistics
            final_stats = {
                'total_transactions_processed': total_processed,
                'total_batches': len(batch_results),
                'batch_size_used': self.batch_size,
                'rule_suggestions': len(suggestions),
                'retry_successes': retry_results['successful_retries'],
                'remaining_failures': retry_results['remaining_failed'],
                'filing_statistics': filing_stats
            }
            
            # Update performance metrics
            self.audit_reporter.update_performance_metrics({
                'processed_transactions': total_processed
            })
            
            # Generate performance summary
            processing_time = self.performance_metrics.get_current_stats()['uptime']
            self.audit_reporter.log_performance_summary(processing_time, total_processed)
            
            # End processing session
            self.audit_reporter.end_audit_session(processing_session_id, final_stats)
            
            self.progress_monitor.finish_operation()
            
            logging.info("✅ Full transaction processing complete")
            logging.info(f"📊 Final stats: {final_stats}")
            
            return {
                'status': 'success',
                'final_stats': final_stats,
                'batch_results': batch_results,
                'rule_suggestions': suggestions,
                'retry_results': retry_results
            }
            
        except Exception as e:
            logging.error(f"❌ Error in full transaction processing: {e}")
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")
            print(f"❌ Processing error: {e}")
            print("Full error details:")
            traceback.print_exc()
            
            if 'processing_session_id' in locals():
                self.audit_reporter.log_audit_event(
                    processing_session_id, "processing_error", {"error": str(e)}, "error"
                )
                self.audit_reporter.end_audit_session(processing_session_id, {"status": "failed"})
            
            if self.real_time_monitor:
                self.real_time_monitor.add_log_entry('ERROR', f'Full processing failed: {e}')
            
            return {'status': 'error', 'error': str(e)}
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status."""
        try:
            # Database stats
            db_stats = self.db_manager.get_database_stats()
            
            # Rule stats from AI matcher
            rule_stats = {
                'total_rules': len(self.ai_matcher.rules_cache),
                'source_variations': len(self.ai_matcher.source_variations),
                'match_history': len(self.ai_matcher.match_history),
                'pending_suggestions': len(self.ai_matcher.get_pending_rule_suggestions())
            }
            
            # Get pending transactions
            pending_transactions = self.db_manager.get_pending_transactions()
            
            # Performance metrics
            perf_stats = self.performance_metrics.get_current_stats()
            
            # Match statistics
            match_stats = self.audit_reporter.get_match_statistics()
            
            # Google Sheets status
            sheets_status = {
                'connection': self.sheets_integration.test_connection(),
                'layout_map_sheets': len(self.sheets_integration.layout_map_cache),
                'failed_transactions': len(self.sheets_integration.failed_transactions)
            }
            
            # Error recovery stats
            recovery_stats = self.error_recovery.get_recovery_stats()
            
            # API rate limiter stats
            api_stats = self.api_rate_limiter.get_all_stats()
            
            # Filing system stats
            filing_stats = self.filing_manager.get_filing_statistics()
            
            status = {
                'database': db_stats,
                'rules': rule_stats,
                'pending_transactions': len(pending_transactions),
                'ai_matcher_rules_loaded': len(self.ai_matcher.rules_cache),
                'performance': perf_stats,
                'match_statistics': match_stats,
                'google_sheets': sheets_status,
                'error_recovery': recovery_stats,
                'api_rate_limiter': api_stats,
                'filing_system': filing_stats,
                'system_health': self._assess_system_health()
            }
            
            return status
            
        except Exception as e:
            logging.error(f"Error getting system status: {e}")
            return {'error': str(e)}
    
    def show_pending_rule_suggestions(self):
        """Display pending rule suggestions."""
        try:
            suggestions = self.ai_matcher.get_pending_rule_suggestions()
            
            if not suggestions:
                print("📭 No pending rule suggestions found.")
                return
            
            print(f"\n📋 PENDING RULE SUGGESTIONS ({len(suggestions)} total)")
            print("=" * 80)
            
            for i, suggestion in enumerate(suggestions, 1):
                print(f"\n{i}. {suggestion['source']}")
                print(f"   Target: {suggestion['target_sheet']} → {suggestion['target_header']}")
                print(f"   Company: {suggestion.get('company', 'Unknown')}")
                print(f"   Confidence: {suggestion['confidence']:.2f}")
                print(f"   Reason: {suggestion.get('reason', 'N/A')}")
                print("-" * 60)
            
            print(f"\n💡 Run 'review_suggestions.bat' to review and approve/reject these suggestions.")
            
        except Exception as e:
            logging.error(f"Error showing pending suggestions: {e}")
            print(f"❌ Error: {e}")
    
    def _assess_system_health(self) -> Dict:
        """Assess overall system health."""
        try:
            health_score = 100
            issues = []
            
            # Check database
            db_stats = self.db_manager.get_database_stats()
            if db_stats.get('total_transactions', 0) == 0:
                health_score -= 10
                issues.append("No transactions in database")
            
            # Check rules in AI matcher
            if len(self.ai_matcher.rules_cache) == 0:
                health_score -= 20
                issues.append("No rules loaded in AI matcher")
            
            # Check Google Sheets connection
            if not self.sheets_integration.test_connection():
                health_score -= 30
                issues.append("Google Sheets connection failed")
            
            # Check failed transactions
            if len(self.sheets_integration.failed_transactions) > 0:
                health_score -= 5
                issues.append(f"{len(self.sheets_integration.failed_transactions)} failed transactions")
            
            # Check API rate limiter
            api_stats = self.api_rate_limiter.get_all_stats()
            if 'global' in api_stats:
                global_stats = api_stats['global']
                if global_stats.get('rate_limited_requests', 0) > 0:
                    health_score -= 5
                    issues.append(f"{global_stats['rate_limited_requests']} rate-limited requests")
            
            # Determine health status
            if health_score >= 90:
                status = "excellent"
            elif health_score >= 70:
                status = "good"
            elif health_score >= 50:
                status = "fair"
            else:
                status = "poor"
            
            return {
                'health_score': health_score,
                'status': status,
                'issues': issues
            }
            
        except Exception as e:
            logging.error(f"Error assessing system health: {e}")
            return {
                'health_score': 0,
                'status': 'unknown',
                'issues': [f"Health assessment error: {e}"]
            }
    
    def generate_comprehensive_report(self) -> str:
        """Generate and save a comprehensive report."""
        try:
            logging.info("📊 Generating comprehensive report...")
            
            # Generate report
            report = self.audit_reporter.generate_comprehensive_report()
            
            # Add system status
            report['system_status'] = self.get_system_status()
            
            # Add executive summary
            report['executive_summary'] = self.audit_reporter.generate_executive_summary()
            
            # Add API rate limiter statistics
            report['api_rate_limiter_stats'] = self.api_rate_limiter.get_all_stats()
            
            # Save report
            filename = self.audit_reporter.save_report_to_file(report)
            
            if filename:
                logging.info(f"📄 Comprehensive report saved: {filename}")
                return filename
            else:
                logging.error("Failed to save comprehensive report")
                return None
                
        except Exception as e:
            logging.error(f"Error generating comprehensive report: {e}")
            return None
    
    def cleanup_and_shutdown(self):
        """Cleanup and shutdown the system."""
        try:
            logging.info("🔄 Shutting down system...")
            
            # Flush any remaining filing transactions
            try:
                self.filing_manager.flush_all_pending()
                logging.info("✅ Final filing transactions flushed")
            except Exception as e:
                logging.warning(f"⚠️ Error flushing final filing transactions: {e}")
            
            # Stop performance monitoring
            self.performance_metrics.stop_monitoring()
            
            # Stop real-time monitoring
            if self.real_time_monitor:
                self.real_time_monitor.stop_monitoring()
            
            # Save audit trail
            self.audit_reporter.save_audit_trail()
            
            # Generate final report
            self.generate_comprehensive_report()
            
            # Print final statistics
            self.api_rate_limiter.print_stats()
            
            # Print filing statistics
            filing_stats = self.filing_manager.get_filing_statistics()
            logging.info(f"📊 Final filing statistics: {filing_stats}")
            
            logging.info("✅ System shutdown complete")
            
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
    
    def test_small_batch(self, sample_size: int = 10) -> Dict:
        """Test the system with a small batch of transactions."""
        try:
            logging.info(f"🧪 Testing system with {sample_size} transactions...")
            
            # Start test session
            test_session_id = self.audit_reporter.start_audit_session(
                "System Test",
                f"Testing system with {sample_size} transactions"
            )
            
            # Download transactions
            all_transactions = self.csv_downloader.download_petty_cash_data()
            if not all_transactions:
                return {'error': 'No transactions available for testing'}
            
            # Take sample
            test_transactions = all_transactions[:sample_size]
            
            # Process test batch
            result = self.process_transactions_batch(test_transactions)
            
            # End test session
            self.audit_reporter.end_audit_session(test_session_id, {
                'test_size': sample_size,
                'result': result
            })
            
            logging.info(f"✅ Test completed: {result}")
            return result
            
        except Exception as e:
            logging.error(f"Error in test: {e}")
            return {'error': str(e)}

    def run(self, dry_run: bool = False) -> bool:
        """Run the complete petty cash sorting process."""
        
        logging.info("🚀 STARTING PETTY CASH SORTER - COMPLETE PIPELINE")
        logging.info("=" * 60)
        
        try:
            # Step 1: Initialize system
            logging.info("📋 Step 1: Initializing system...")
            if not self.initialize_system():
                logging.error("❌ System initialization failed")
                return False
            logging.info("✅ System initialized successfully")
            
            # Step 2: Download and process transactions
            logging.info("📋 Step 2: Downloading and processing transactions...")
            transactions = self.download_and_process_transactions()
            if not transactions:
                logging.warning("⚠️ No new transactions to process")
                return True
            logging.info(f"✅ Downloaded {len(transactions)} transactions")
            
            # Step 3: Process all transactions
            logging.info("📋 Step 3: Processing all transactions...")
            if dry_run:
                logging.info("🔍 DRY RUN MODE - No actual processing")
                result = self.test_small_batch(10)
            else:
                result = self.process_all_transactions()
            
            if result.get('success', False):
                logging.info("✅ Transaction processing completed successfully")
                logging.info(f"📊 Results: {result}")
            else:
                logging.error(f"❌ Transaction processing failed: {result}")
                return False
            
            # Step 4: Generate report
            logging.info("📋 Step 4: Generating comprehensive report...")
            report = self.generate_comprehensive_report()
            logging.info("✅ Report generated")
            
            # Step 5: Cleanup
            logging.info("📋 Step 5: Cleaning up...")
            self.cleanup_and_shutdown()
            logging.info("✅ Cleanup completed")
            
            logging.info("🎉 PETTY CASH SORTER COMPLETED SUCCESSFULLY!")
            return True
            
        except Exception as e:
            logging.error(f"❌ Fatal error in run method: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main execution function."""
    print("PETTY CASH SORTER - FINAL COMPREHENSIVE VERSION")
    print("=" * 80)
    
    # Initialize the sorter
    sorter = PettyCashSorterFinal()
    
    try:
        # Initialize system
        if not sorter.initialize_system():
            print("❌ System initialization failed")
            return
        
        print("[SUCCESS] System initialized successfully")
        
        # Get system status
        status = sorter.get_system_status()
        print(f"[INFO] System Health: {status['system_health']['status']} ({status['system_health']['health_score']}/100)")
        
        # Process all transactions
        print("\n[START] Starting transaction processing...")
        result = sorter.process_all_transactions()
        
        if result['status'] == 'success':
            print("[SUCCESS] Processing completed successfully")
            print(f"[INFO] Final stats: {result['final_stats']}")
            
            # Show pending rule suggestions if any
            if result['final_stats'].get('rule_suggestions', 0) > 0:
                print(f"\n[INFO] {result['final_stats']['rule_suggestions']} rule suggestions generated!")
                sorter.show_pending_rule_suggestions()
        elif result['status'] == 'no_new_transactions':
            print("[INFO] No new transactions to process - all transactions have been processed")
            print("[INFO] Check database for existing transaction status")
            
            # Show database stats
            db_stats = sorter.db_manager.get_database_stats()
            print(f"[INFO] Database stats: {db_stats}")
        else:
            print(f"[ERROR] Processing failed: {result.get('error', 'Unknown error')}")
        
        # Generate report
        print("\n[INFO] Generating comprehensive report...")
        report_file = sorter.generate_comprehensive_report()
        if report_file:
            print(f"[INFO] Report saved: {report_file}")
        
    except KeyboardInterrupt:
        print("\n[WARNING] Process interrupted by user")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        print("Full error details:")
        traceback.print_exc()
        logging.error(f"Unexpected error in main: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
    finally:
        # Cleanup
        sorter.cleanup_and_shutdown()
        print("[INFO] Goodbye!")

if __name__ == "__main__":
    main() 