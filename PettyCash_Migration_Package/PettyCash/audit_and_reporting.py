#!/usr/bin/env python3
"""
Audit and Reporting Module
Handles statistics, performance summaries, and detailed reporting
"""

import logging
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

class AuditAndReporting:
    """Handles audit trails, statistics, and reporting functionality."""
    
    def __init__(self):
        # Audit trail storage
        self.audit_trail = []
        self.audit_file = "logs/audit_trail.json"
        
        # Performance metrics
        self.performance_metrics = {
            'start_time': None,
            'end_time': None,
            'total_transactions': 0,
            'processed_transactions': 0,
            'matched_transactions': 0,
            'unmatched_transactions': 0,
            'failed_transactions': 0,
            'api_calls': 0,
            'api_errors': 0,
            'processing_time': 0,
            'memory_usage': []
        }
        
        # Statistics tracking
        self.match_statistics = {
            'total_matches': 0,
            'high_confidence_matches': 0,
            'medium_confidence_matches': 0,
            'low_confidence_matches': 0,
            'confidence_distribution': {},
            'rule_usage': {},
            'company_patterns': {},
            'source_patterns': {}
        }
        
        # Create directories
        Path("logs").mkdir(exist_ok=True)
        Path("reports").mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/audit_and_reporting.log'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("INITIALIZING AUDIT AND REPORTING")
        logging.info("=" * 60)
        
        # Load existing audit trail
        self.load_audit_trail()
    
    def start_audit_session(self, session_name: str, description: str = None):
        """Start a new audit session."""
        session = {
            'session_id': f"session_{int(time.time())}",
            'session_name': session_name,
            'description': description,
            'start_time': datetime.now().isoformat(),
            'events': []
        }
        
        self.audit_trail.append(session)
        self.performance_metrics['start_time'] = time.time()
        
        logging.info(f"🔍 Started audit session: {session_name}")
        if description:
            logging.info(f"📝 Description: {description}")
        
        return session['session_id']
    
    def log_audit_event(self, session_id: str, event_type: str, details: Dict, severity: str = 'info'):
        """Log an audit event."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': details,
            'severity': severity
        }
        
        # Find the session
        for session in self.audit_trail:
            if session['session_id'] == session_id:
                session['events'].append(event)
                break
        
        # Log to console based on severity
        if severity == 'error':
            logging.error(f"🚨 {event_type}: {details}")
        elif severity == 'warning':
            logging.warning(f"⚠️ {event_type}: {details}")
        elif severity == 'info':
            logging.info(f"ℹ️ {event_type}: {details}")
        else:
            logging.debug(f"🔍 {event_type}: {details}")
    
    def end_audit_session(self, session_id: str, summary: Dict = None):
        """End an audit session."""
        for session in self.audit_trail:
            if session['session_id'] == session_id:
                session['end_time'] = datetime.now().isoformat()
                if summary:
                    session['summary'] = summary
                
                # Calculate session duration
                start_time = datetime.fromisoformat(session['start_time'])
                end_time = datetime.fromisoformat(session['end_time'])
                duration = (end_time - start_time).total_seconds()
                session['duration_seconds'] = duration
                
                logging.info(f"✅ Ended audit session: {session['session_name']} (Duration: {duration:.1f}s)")
                break
        
        self.performance_metrics['end_time'] = time.time()
        if self.performance_metrics['start_time']:
            self.performance_metrics['processing_time'] = (
                self.performance_metrics['end_time'] - self.performance_metrics['start_time']
            )
    
    def update_match_statistics(self, match_data: Dict):
        """Update match statistics with new match data."""
        try:
            # Update basic counts
            self.match_statistics['total_matches'] += 1
            
            confidence = match_data.get('confidence', 0)
            if confidence >= 9:
                self.match_statistics['high_confidence_matches'] += 1
            elif confidence >= 7:
                self.match_statistics['medium_confidence_matches'] += 1
            else:
                self.match_statistics['low_confidence_matches'] += 1
            
            # Update confidence distribution
            confidence_bucket = f"{confidence}-{confidence+1}"
            if confidence_bucket not in self.match_statistics['confidence_distribution']:
                self.match_statistics['confidence_distribution'][confidence_bucket] = 0
            self.match_statistics['confidence_distribution'][confidence_bucket] += 1
            
            # Update rule usage
            rule_id = match_data.get('rule_id', 'unknown')
            if rule_id not in self.match_statistics['rule_usage']:
                self.match_statistics['rule_usage'][rule_id] = 0
            self.match_statistics['rule_usage'][rule_id] += 1
            
            # Update company patterns
            company = match_data.get('company', 'unknown')
            if company not in self.match_statistics['company_patterns']:
                self.match_statistics['company_patterns'][company] = 0
            self.match_statistics['company_patterns'][company] += 1
            
            # Update source patterns
            source = match_data.get('source', 'unknown')
            if source not in self.match_statistics['source_patterns']:
                self.match_statistics['source_patterns'][source] = 0
            self.match_statistics['source_patterns'][source] += 1
            
        except Exception as e:
            logging.error(f"Error updating match statistics: {e}")
    
    def update_performance_metrics(self, metrics_update: Dict):
        """Update performance metrics."""
        try:
            for key, value in metrics_update.items():
                if key in self.performance_metrics:
                    if isinstance(value, (int, float)):
                        self.performance_metrics[key] += value
                    else:
                        self.performance_metrics[key] = value
                elif key == 'memory_sample':
                    self.performance_metrics['memory_usage'].append(value)
            
        except Exception as e:
            logging.error(f"Error updating performance metrics: {e}")
    
    def get_match_statistics(self) -> Dict:
        """Get comprehensive match statistics."""
        try:
            stats = self.match_statistics.copy()
            
            # Calculate percentages
            total = stats['total_matches']
            if total > 0:
                stats['high_confidence_percentage'] = (stats['high_confidence_matches'] / total) * 100
                stats['medium_confidence_percentage'] = (stats['medium_confidence_matches'] / total) * 100
                stats['low_confidence_percentage'] = (stats['low_confidence_matches'] / total) * 100
            else:
                stats['high_confidence_percentage'] = 0
                stats['medium_confidence_percentage'] = 0
                stats['low_confidence_percentage'] = 0
            
            # Get top rules
            top_rules = sorted(stats['rule_usage'].items(), key=lambda x: x[1], reverse=True)[:10]
            stats['top_rules'] = top_rules
            
            # Get top companies
            top_companies = sorted(stats['company_patterns'].items(), key=lambda x: x[1], reverse=True)[:10]
            stats['top_companies'] = top_companies
            
            # Get top sources
            top_sources = sorted(stats['source_patterns'].items(), key=lambda x: x[1], reverse=True)[:10]
            stats['top_sources'] = top_sources
            
            return stats
            
        except Exception as e:
            logging.error(f"Error getting match statistics: {e}")
            return {}
    
    def log_performance_summary(self, duration: float, transaction_count: int):
        """Log a performance summary."""
        logging.info("=" * 60)
        logging.info("📊 PERFORMANCE SUMMARY")
        logging.info("=" * 60)
        
        logging.info(f"⏱️ Total processing time: {duration:.2f} seconds")
        logging.info(f"📈 Transactions processed: {transaction_count:,}")
        
        if transaction_count > 0:
            rate = transaction_count / duration
            logging.info(f"🚀 Processing rate: {rate:.2f} transactions/second")
        
        # Memory usage summary
        if self.performance_metrics['memory_usage']:
            memory_values = [m['rss'] for m in self.performance_metrics['memory_usage']]
            peak_memory = max(memory_values) / 1024 / 1024  # Convert to MB
            avg_memory = sum(memory_values) / len(memory_values) / 1024 / 1024
            
            logging.info(f"💾 Peak memory usage: {peak_memory:.1f} MB")
            logging.info(f"💾 Average memory usage: {avg_memory:.1f} MB")
        
        # API call summary
        api_calls = self.performance_metrics['api_calls']
        api_errors = self.performance_metrics['api_errors']
        
        if api_calls > 0:
            success_rate = ((api_calls - api_errors) / api_calls) * 100
            logging.info(f"🔌 API calls: {api_calls:,}")
            logging.info(f"❌ API errors: {api_errors:,}")
            logging.info(f"✅ API success rate: {success_rate:.1f}%")
        
        logging.info("=" * 60)
    
    def generate_comprehensive_report(self, session_id: str = None) -> Dict:
        """Generate a comprehensive report."""
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'performance_metrics': self.performance_metrics.copy(),
                'match_statistics': self.get_match_statistics(),
                'audit_sessions': []
            }
            
            # Add audit sessions
            for session in self.audit_trail:
                if session_id is None or session['session_id'] == session_id:
                    session_summary = {
                        'session_id': session['session_id'],
                        'session_name': session['session_name'],
                        'start_time': session['start_time'],
                        'end_time': session.get('end_time'),
                        'duration_seconds': session.get('duration_seconds'),
                        'event_count': len(session['events']),
                        'summary': session.get('summary', {})
                    }
                    report['audit_sessions'].append(session_summary)
            
            # Calculate overall statistics
            total_events = sum(len(session['events']) for session in self.audit_trail)
            total_duration = sum(session.get('duration_seconds', 0) for session in self.audit_trail)
            
            report['overall_statistics'] = {
                'total_sessions': len(self.audit_trail),
                'total_events': total_events,
                'total_duration': total_duration,
                'average_session_duration': total_duration / len(self.audit_trail) if self.audit_trail else 0
            }
            
            return report
            
        except Exception as e:
            logging.error(f"Error generating comprehensive report: {e}")
            return {'error': str(e)}
    
    def save_report_to_file(self, report: Dict, filename: str = None):
        """Save report to file."""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"reports/comprehensive_report_{timestamp}.json"
            
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            
            logging.info(f"📄 Report saved to: {filename}")
            return filename
            
        except Exception as e:
            logging.error(f"Error saving report: {e}")
            return None
    
    def generate_executive_summary(self) -> Dict:
        """Generate an executive summary of operations."""
        try:
            # Get latest performance metrics
            processing_time = self.performance_metrics.get('processing_time', 0)
            total_transactions = self.performance_metrics.get('total_transactions', 0)
            processed_transactions = self.performance_metrics.get('processed_transactions', 0)
            matched_transactions = self.performance_metrics.get('matched_transactions', 0)
            
            # Get match statistics
            match_stats = self.get_match_statistics()
            
            summary = {
                'executive_summary': {
                    'total_processing_time_minutes': processing_time / 60,
                    'total_transactions_processed': processed_transactions,
                    'successful_matches': matched_transactions,
                    'match_success_rate': (matched_transactions / processed_transactions * 100) if processed_transactions > 0 else 0,
                    'high_confidence_matches': match_stats.get('high_confidence_matches', 0),
                    'medium_confidence_matches': match_stats.get('medium_confidence_matches', 0),
                    'low_confidence_matches': match_stats.get('low_confidence_matches', 0)
                },
                'key_metrics': {
                    'processing_rate': processed_transactions / (processing_time / 60) if processing_time > 0 else 0,
                    'api_success_rate': ((self.performance_metrics.get('api_calls', 0) - self.performance_metrics.get('api_errors', 0)) / 
                                       self.performance_metrics.get('api_calls', 1) * 100) if self.performance_metrics.get('api_calls', 0) > 0 else 100,
                    'average_confidence': self._calculate_average_confidence(match_stats)
                },
                'top_performers': {
                    'most_used_rules': match_stats.get('top_rules', [])[:5],
                    'most_common_companies': match_stats.get('top_companies', [])[:5],
                    'most_common_sources': match_stats.get('top_sources', [])[:5]
                }
            }
            
            return summary
            
        except Exception as e:
            logging.error(f"Error generating executive summary: {e}")
            return {'error': str(e)}
    
    def _calculate_average_confidence(self, match_stats: Dict) -> float:
        """Calculate average confidence from match statistics."""
        try:
            total_matches = match_stats.get('total_matches', 0)
            if total_matches == 0:
                return 0.0
            
            # Calculate weighted average from confidence distribution
            total_confidence = 0
            total_weight = 0
            
            for confidence_range, count in match_stats.get('confidence_distribution', {}).items():
                # Parse confidence range (e.g., "8-9" -> 8.5)
                try:
                    start, end = confidence_range.split('-')
                    avg_confidence = (float(start) + float(end)) / 2
                    total_confidence += avg_confidence * count
                    total_weight += count
                except:
                    continue
            
            return total_confidence / total_weight if total_weight > 0 else 0.0
            
        except Exception as e:
            logging.error(f"Error calculating average confidence: {e}")
            return 0.0
    
    def load_audit_trail(self):
        """Load audit trail from file."""
        try:
            if Path(self.audit_file).exists():
                with open(self.audit_file, 'r') as f:
                    self.audit_trail = json.load(f)
                logging.info(f"Loaded audit trail with {len(self.audit_trail)} sessions")
            else:
                logging.info("No existing audit trail found")
                self.audit_trail = []
        except Exception as e:
            logging.error(f"Error loading audit trail: {e}")
            self.audit_trail = []
    
    def save_audit_trail(self):
        """Save audit trail to file."""
        try:
            with open(self.audit_file, 'w') as f:
                json.dump(self.audit_trail, f, indent=2)
            logging.info(f"Audit trail saved with {len(self.audit_trail)} sessions")
        except Exception as e:
            logging.error(f"Error saving audit trail: {e}")
    
    def clear_audit_trail(self):
        """Clear audit trail."""
        self.audit_trail = []
        self.save_audit_trail()
        logging.info("Audit trail cleared")

def main():
    """Test audit and reporting functionality."""
    print("AUDIT AND REPORTING TEST")
    print("=" * 60)
    
    audit = AuditAndReporting()
    
    # Start audit session
    session_id = audit.start_audit_session("Test Session", "Testing audit functionality")
    
    # Log some events
    audit.log_audit_event(session_id, "transaction_processed", {
        'transaction_id': 'test_001',
        'amount': 100.50,
        'source': 'Test Source'
    })
    
    audit.log_audit_event(session_id, "rule_matched", {
        'rule_id': 'rule_001',
        'confidence': 8.5,
        'target_sheet': 'Test Sheet'
    })
    
    audit.log_audit_event(session_id, "api_call", {
        'api_name': 'sheets_update',
        'response_time': 0.5,
        'success': True
    }, 'info')
    
    # Update statistics
    audit.update_match_statistics({
        'confidence': 8.5,
        'rule_id': 'rule_001',
        'company': 'Test Company',
        'source': 'Test Source'
    })
    
    audit.update_performance_metrics({
        'total_transactions': 1,
        'processed_transactions': 1,
        'matched_transactions': 1,
        'api_calls': 1
    })
    
    # End session
    audit.end_audit_session(session_id, {
        'status': 'success',
        'transactions_processed': 1
    })
    
    # Generate reports
    report = audit.generate_comprehensive_report()
    executive_summary = audit.generate_executive_summary()
    
    print(f"📊 Generated comprehensive report with {len(report['audit_sessions'])} sessions")
    print(f"📈 Executive summary: {executive_summary['executive_summary']['match_success_rate']:.1f}% match rate")
    
    # Save report
    filename = audit.save_report_to_file(report)
    if filename:
        print(f"💾 Report saved to: {filename}")
    
    # Save audit trail
    audit.save_audit_trail()
    
    print("✅ Audit and reporting test completed")

if __name__ == "__main__":
    main() 