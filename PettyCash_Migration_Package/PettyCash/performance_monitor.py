#!/usr/bin/env python3
"""
Performance Monitor for Petty Cash Sorter
Includes progress tracking, error recovery, and performance metrics
"""

import logging
import json
import time
import psutil
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from functools import wraps

class ProgressMonitor:
    """Monitors and displays progress of operations."""
    
    def __init__(self):
        self.current_operation = None
        self.total_items = 0
        self.processed_items = 0
        self.start_time = None
        self.last_milestone = 0
        self.milestone_interval = 10  # Log every 10 items
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/progress_monitor.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING PROGRESS MONITOR")
        logging.info("=" * 50)
    
    def start_operation(self, operation_name: str, total_items: int, description: str = None):
        """Start monitoring a new operation."""
        self.current_operation = operation_name
        self.total_items = total_items
        self.processed_items = 0
        self.start_time = time.time()
        self.last_milestone = 0
        
        logging.info(f"🚀 Starting operation: {operation_name}")
        if description:
            logging.info(f"📝 Description: {description}")
        logging.info(f"📊 Total items to process: {total_items:,}")
        logging.info("=" * 60)
    
    def update_progress(self, count: int = 1, message: str = None):
        """Update progress counter."""
        self.processed_items += count
        
        # Calculate progress percentage
        if self.total_items > 0:
            percentage = (self.processed_items / self.total_items) * 100
        else:
            percentage = 0
        
        # Log milestone if reached
        if self.processed_items - self.last_milestone >= self.milestone_interval:
            self._log_milestone(self.processed_items, self.total_items)
            self.last_milestone = self.processed_items
        
        # Log custom message if provided
        if message:
            logging.info(f"📈 Progress: {self.processed_items:,}/{self.total_items:,} ({percentage:.1f}%) - {message}")
    
    def _log_milestone(self, processed: int, total: int):
        """Log a progress milestone."""
        if total > 0:
            percentage = (processed / total) * 100
            elapsed_time = time.time() - self.start_time
            
            # Calculate estimated time remaining
            if processed > 0:
                rate = processed / elapsed_time
                remaining_items = total - processed
                eta_seconds = remaining_items / rate
                eta_minutes = eta_seconds / 60
                
                logging.info(f"🎯 Milestone: {processed:,}/{total:,} ({percentage:.1f}%) - "
                           f"Elapsed: {elapsed_time:.1f}s - ETA: {eta_minutes:.1f}min")
            else:
                logging.info(f"🎯 Milestone: {processed:,}/{total:,} ({percentage:.1f}%) - "
                           f"Elapsed: {elapsed_time:.1f}s")
    
    def finish_operation(self):
        """Finish the current operation and log summary."""
        if not self.current_operation:
            return
        
        elapsed_time = time.time() - self.start_time
        
        logging.info("=" * 60)
        logging.info(f"✅ Operation completed: {self.current_operation}")
        logging.info(f"📊 Final count: {self.processed_items:,}/{self.total_items:,}")
        
        if self.total_items > 0:
            percentage = (self.processed_items / self.total_items) * 100
            logging.info(f"📈 Success rate: {percentage:.1f}%")
        
        logging.info(f"⏱️ Total time: {elapsed_time:.1f} seconds")
        
        if self.processed_items > 0:
            rate = self.processed_items / elapsed_time
            logging.info(f"🚀 Processing rate: {rate:.1f} items/second")
        
        logging.info("=" * 60)
        
        # Reset for next operation
        self.current_operation = None
        self.total_items = 0
        self.processed_items = 0
        self.start_time = None
    
    def get_operation_summary(self) -> dict:
        """Get summary of current operation."""
        if not self.current_operation:
            return {}
        
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        
        return {
            'operation': self.current_operation,
            'processed': self.processed_items,
            'total': self.total_items,
            'percentage': (self.processed_items / self.total_items * 100) if self.total_items > 0 else 0,
            'elapsed_time': elapsed_time,
            'rate': (self.processed_items / elapsed_time) if elapsed_time > 0 else 0
        }

class ErrorRecovery:
    """Handles error recovery with exponential backoff and retry logic."""
    
    def __init__(self):
        self.max_retries = 3
        self.base_delay = 1  # seconds
        self.max_delay = 60  # seconds
        self.retry_stats = {
            'total_retries': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'error_types': {}
        }
        
        # Progress saving
        self.progress_file = "config/operation_progress.json"
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/error_recovery.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING ERROR RECOVERY SYSTEM")
        logging.info("=" * 50)
    
    def exponential_backoff(self, func: Callable):
        """Decorator for exponential backoff retry logic."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    if attempt > 0:
                        delay = self._calculate_delay(attempt)
                        error_type = self._diagnose_error(last_exception)
                        
                        logging.warning(f"Retry attempt {attempt}/{self.max_retries} for {func.__name__}")
                        logging.info(f"Error type: {error_type}")
                        logging.info(f"Waiting {delay:.1f} seconds before retry...")
                        
                        time.sleep(delay)
                        
                        # Apply recovery strategy
                        self._apply_recovery_strategy(error_type, attempt)
                    
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Success - update stats
                    if attempt > 0:
                        self.retry_stats['successful_recoveries'] += 1
                        logging.info(f"✅ Recovery successful after {attempt} retries")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    self.retry_stats['total_retries'] += 1
                    
                    # Update error type stats
                    error_type = self._diagnose_error(e)
                    if error_type not in self.retry_stats['error_types']:
                        self.retry_stats['error_types'][error_type] = 0
                    self.retry_stats['error_types'][error_type] += 1
                    
                    if attempt == self.max_retries:
                        self.retry_stats['failed_recoveries'] += 1
                        self._log_final_failure(func.__name__, e, args, kwargs)
                        raise e
                    else:
                        logging.warning(f"Attempt {attempt + 1} failed: {e}")
            
            return None
        
        return wrapper
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for exponential backoff."""
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)
    
    def _diagnose_error(self, error: Exception) -> str:
        """Diagnose the type of error."""
        error_str = str(error).lower()
        
        if 'rate limit' in error_str or 'quota' in error_str:
            return 'rate_limit'
        elif 'network' in error_str or 'connection' in error_str:
            return 'network_error'
        elif 'auth' in error_str or 'unauthorized' in error_str:
            return 'auth_error'
        elif 'api' in error_str or 'service' in error_str:
            return 'api_error'
        elif 'resource' in error_str or 'not found' in error_str:
            return 'resource_error'
        else:
            return 'unknown_error'
    
    def _get_recovery_message(self, error_type: str, attempt: int) -> str:
        """Get recovery message for error type."""
        messages = {
            'rate_limit': f"Rate limit hit, waiting before retry {attempt}",
            'network_error': f"Network error, retrying connection {attempt}",
            'auth_error': f"Authentication error, checking credentials {attempt}",
            'api_error': f"API service error, retrying request {attempt}",
            'resource_error': f"Resource not found, checking availability {attempt}",
            'unknown_error': f"Unknown error, retrying operation {attempt}"
        }
        return messages.get(error_type, f"Retrying operation {attempt}")
    
    def _apply_recovery_strategy(self, error_type: str, attempt: int):
        """Apply specific recovery strategy based on error type."""
        if error_type == 'rate_limit':
            self._handle_rate_limit(attempt)
        elif error_type == 'network_error':
            self._handle_network_error(attempt)
        elif error_type == 'auth_error':
            self._handle_auth_error(attempt)
        elif error_type == 'api_error':
            self._handle_api_error(attempt)
        elif error_type == 'resource_error':
            self._handle_resource_error(attempt)
    
    def _handle_rate_limit(self, attempt: int):
        """Handle rate limit errors."""
        logging.info("🔄 Rate limit detected, applying rate limit strategy")
        # Could implement rate limit specific logic here
    
    def _handle_network_error(self, attempt: int):
        """Handle network errors."""
        logging.info("🌐 Network error detected, applying network strategy")
        # Could implement network specific logic here
    
    def _handle_auth_error(self, attempt: int):
        """Handle authentication errors."""
        logging.info("🔐 Authentication error detected, applying auth strategy")
        # Could implement auth specific logic here
    
    def _handle_api_error(self, attempt: int):
        """Handle API errors."""
        logging.info("🔌 API error detected, applying API strategy")
        # Could implement API specific logic here
    
    def _handle_resource_error(self, attempt: int):
        """Handle resource errors."""
        logging.info("📁 Resource error detected, applying resource strategy")
        # Could implement resource specific logic here
    
    def save_progress(self, operation: str, completed_items: int, total_items: int, context: dict = None):
        """Save operation progress to file."""
        try:
            progress_data = {
                'operation': operation,
                'completed_items': completed_items,
                'total_items': total_items,
                'timestamp': datetime.now().isoformat(),
                'context': context or {}
            }
            
            Path(self.progress_file).parent.mkdir(exist_ok=True)
            with open(self.progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            
            logging.info(f"💾 Progress saved: {completed_items}/{total_items} items completed")
            
        except Exception as e:
            logging.error(f"Error saving progress: {e}")
    
    def resume_from_progress(self) -> Optional[dict]:
        """Resume operation from saved progress."""
        try:
            if not Path(self.progress_file).exists():
                return None
            
            with open(self.progress_file, 'r') as f:
                progress_data = json.load(f)
            
            logging.info(f"🔄 Resuming operation: {progress_data['operation']}")
            logging.info(f"📊 Progress: {progress_data['completed_items']}/{progress_data['total_items']} items")
            
            return progress_data
            
        except Exception as e:
            logging.error(f"Error resuming progress: {e}")
            return None
    
    def clear_progress(self):
        """Clear saved progress."""
        try:
            if Path(self.progress_file).exists():
                Path(self.progress_file).unlink()
                logging.info("🗑️ Progress file cleared")
        except Exception as e:
            logging.error(f"Error clearing progress: {e}")
    
    def _log_final_failure(self, func_name: str, error: Exception, args: tuple, kwargs: dict):
        """Log final failure after all retries exhausted."""
        logging.error("=" * 60)
        logging.error(f"❌ FINAL FAILURE: {func_name}")
        logging.error(f"🔍 Error: {error}")
        logging.error(f"📝 Args: {args}")
        logging.error(f"📝 Kwargs: {kwargs}")
        logging.error("=" * 60)
    
    def get_recovery_stats(self) -> dict:
        """Get error recovery statistics."""
        return self.retry_stats.copy()

class PerformanceMetrics:
    """Tracks performance metrics and generates reports."""
    
    def __init__(self):
        self.start_time = None
        self.operation_times = {}
        self.api_calls = []
        self.memory_usage = []
        self.monitoring = False
        self.monitor_thread = None
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/performance_metrics.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING PERFORMANCE METRICS")
        logging.info("=" * 50)
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.monitoring = True
        
        # Start memory monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_memory, daemon=True)
        self.monitor_thread.start()
        
        logging.info("📊 Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        
        logging.info("📊 Performance monitoring stopped")
    
    def _monitor_memory(self):
        """Monitor memory usage in background thread."""
        while self.monitoring:
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                
                self.memory_usage.append({
                    'timestamp': time.time(),
                    'rss': memory_info.rss,  # Resident Set Size
                    'vms': memory_info.vms,  # Virtual Memory Size
                    'percent': process.memory_percent()
                })
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logging.error(f"Error monitoring memory: {e}")
                time.sleep(5)
    
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        return OperationTimer(self, operation_name)
    
    def track_api_call(self, api_name: str, response_time: float, success: bool, error_type: str = None):
        """Track API call performance."""
        self.api_calls.append({
            'api_name': api_name,
            'response_time': response_time,
            'success': success,
            'error_type': error_type,
            'timestamp': time.time()
        })
    
    def _generate_performance_report(self) -> dict:
        """Generate comprehensive performance report."""
        if not self.start_time:
            return {}
        
        total_time = time.time() - self.start_time
        
        # Calculate API call statistics
        api_stats = {}
        for call in self.api_calls:
            api_name = call['api_name']
            if api_name not in api_stats:
                api_stats[api_name] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0,
                    'total_time': 0,
                    'avg_response_time': 0
                }
            
            stats = api_stats[api_name]
            stats['total_calls'] += 1
            stats['total_time'] += call['response_time']
            
            if call['success']:
                stats['successful_calls'] += 1
            else:
                stats['failed_calls'] += 1
        
        # Calculate averages
        for api_name, stats in api_stats.items():
            if stats['total_calls'] > 0:
                stats['avg_response_time'] = stats['total_time'] / stats['total_calls']
                stats['success_rate'] = stats['successful_calls'] / stats['total_calls']
        
        # Calculate memory statistics
        memory_stats = {}
        if self.memory_usage:
            rss_values = [m['rss'] for m in self.memory_usage]
            vms_values = [m['vms'] for m in self.memory_usage]
            percent_values = [m['percent'] for m in self.memory_usage]
            
            memory_stats = {
                'peak_rss': max(rss_values),
                'avg_rss': sum(rss_values) / len(rss_values),
                'peak_vms': max(vms_values),
                'avg_vms': sum(vms_values) / len(vms_values),
                'peak_percent': max(percent_values),
                'avg_percent': sum(percent_values) / len(percent_values)
            }
        
        return {
            'total_time': total_time,
            'operation_times': self.operation_times,
            'api_stats': api_stats,
            'memory_stats': memory_stats,
            'total_api_calls': len(self.api_calls),
            'memory_samples': len(self.memory_usage)
        }
    
    def _analyze_memory_usage(self) -> dict:
        """Analyze memory usage patterns."""
        if not self.memory_usage:
            return {}
        
        # Detect memory leaks
        leak_detected = self._detect_memory_leak()
        
        # Generate optimization suggestions
        suggestions = self._generate_optimization_suggestions()
        
        return {
            'leak_detected': leak_detected,
            'suggestions': suggestions
        }
    
    def _detect_memory_leak(self) -> bool:
        """Detect potential memory leaks."""
        if len(self.memory_usage) < 10:
            return False
        
        # Check if memory usage is consistently increasing
        recent_samples = self.memory_usage[-10:]
        rss_values = [m['rss'] for m in recent_samples]
        
        # Simple linear regression to detect trend
        x = list(range(len(rss_values)))
        n = len(x)
        
        if n < 2:
            return False
        
        sum_x = sum(x)
        sum_y = sum(rss_values)
        sum_xy = sum(x[i] * rss_values[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        # If slope is positive and significant, potential leak
        return slope > 1000  # 1MB per sample threshold
    
    def _generate_optimization_suggestions(self) -> List[str]:
        """Generate optimization suggestions based on metrics."""
        suggestions = []
        
        # Analyze API call patterns
        if self.api_calls:
            avg_response_time = sum(call['response_time'] for call in self.api_calls) / len(self.api_calls)
            if avg_response_time > 2.0:
                suggestions.append("Consider implementing API call caching to reduce response times")
            
            success_rate = sum(1 for call in self.api_calls if call['success']) / len(self.api_calls)
            if success_rate < 0.9:
                suggestions.append("High API failure rate detected - review error handling and retry logic")
        
        # Analyze memory usage
        if self.memory_usage:
            avg_memory = sum(m['rss'] for m in self.memory_usage) / len(self.memory_usage)
            if avg_memory > 100 * 1024 * 1024:  # 100MB
                suggestions.append("High memory usage detected - consider optimizing data structures")
        
        # Analyze operation times
        if self.operation_times:
            slow_operations = [op for op, time in self.operation_times.items() if time > 10]
            if slow_operations:
                suggestions.append(f"Slow operations detected: {', '.join(slow_operations)} - consider optimization")
        
        return suggestions
    
    def _log_performance_summary(self, report: dict):
        """Log performance summary."""
        logging.info("=" * 60)
        logging.info("📊 PERFORMANCE SUMMARY")
        logging.info("=" * 60)
        
        logging.info(f"⏱️ Total execution time: {report.get('total_time', 0):.1f} seconds")
        logging.info(f"🔌 Total API calls: {report.get('total_api_calls', 0)}")
        logging.info(f"💾 Memory samples: {report.get('memory_samples', 0)}")
        
        # Log API statistics
        api_stats = report.get('api_stats', {})
        if api_stats:
            logging.info("\n🔌 API Call Statistics:")
            for api_name, stats in api_stats.items():
                logging.info(f"  {api_name}: {stats['total_calls']} calls, "
                           f"{stats['success_rate']:.1%} success rate, "
                           f"{stats['avg_response_time']:.2f}s avg response")
        
        # Log memory statistics
        memory_stats = report.get('memory_stats', {})
        if memory_stats:
            logging.info(f"\n💾 Memory Statistics:")
            logging.info(f"  Peak RSS: {memory_stats['peak_rss'] / 1024 / 1024:.1f} MB")
            logging.info(f"  Average RSS: {memory_stats['avg_rss'] / 1024 / 1024:.1f} MB")
            logging.info(f"  Peak Usage: {memory_stats['peak_percent']:.1f}%")
        
        # Log operation times
        operation_times = report.get('operation_times', {})
        if operation_times:
            logging.info(f"\n⚡ Operation Times:")
            for operation, time_taken in operation_times.items():
                logging.info(f"  {operation}: {time_taken:.2f} seconds")
        
        logging.info("=" * 60)
    
    def get_current_stats(self) -> dict:
        """Get current performance statistics."""
        return {
            'uptime': time.time() - self.start_time if self.start_time else 0,
            'total_api_calls': len(self.api_calls),
            'memory_samples': len(self.memory_usage),
            'monitoring': self.monitoring
        }

class OperationTimer:
    """Context manager for timing operations."""
    
    def __init__(self, metrics: PerformanceMetrics, operation_name: str):
        self.metrics = metrics
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.metrics.operation_times[self.operation_name] = duration
            logging.debug(f"⏱️ Operation '{self.operation_name}' took {duration:.2f} seconds")

def main():
    """Test performance monitoring components."""
    print("PERFORMANCE MONITOR TEST")
    print("=" * 60)
    
    # Test progress monitor
    print("\n📊 Testing Progress Monitor:")
    progress = ProgressMonitor()
    progress.start_operation("Test Operation", 100, "Testing progress tracking")
    
    for i in range(25):
        progress.update_progress(1, f"Processing item {i+1}")
        time.sleep(0.1)
    
    progress.finish_operation()
    
    # Test error recovery
    print("\n🔄 Testing Error Recovery:")
    recovery = ErrorRecovery()
    
    @recovery.exponential_backoff
    def test_function():
        import random
        if random.random() < 0.7:  # 70% chance of failure
            raise Exception("Simulated error")
        return "Success"
    
    try:
        result = test_function()
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Final failure: {e}")
    
    stats = recovery.get_recovery_stats()
    print(f"📈 Recovery stats: {stats}")
    
    # Test performance metrics
    print("\n📊 Testing Performance Metrics:")
    metrics = PerformanceMetrics()
    metrics.start_monitoring()
    
    with metrics.time_operation("test_operation"):
        time.sleep(1)
    
    metrics.track_api_call("test_api", 0.5, True)
    metrics.track_api_call("test_api", 1.2, False, "timeout")
    
    time.sleep(2)  # Let memory monitoring collect some data
    
    metrics.stop_monitoring()
    
    report = metrics._generate_performance_report()
    metrics._log_performance_summary(report)
    
    print("✅ Performance monitoring test completed")

if __name__ == "__main__":
    main() 