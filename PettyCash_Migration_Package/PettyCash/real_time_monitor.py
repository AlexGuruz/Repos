#!/usr/bin/env python3
"""
Real-time Monitoring Dashboard for Petty Cash Sorter
Live monitoring with WebSocket updates and performance metrics
"""

import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    from flask import Flask, render_template_string, jsonify, request
    from flask_socketio import SocketIO, emit
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    logging.warning("Flask not available - real-time monitoring disabled")

# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Petty Cash Sorter - Real-time Monitor</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .status-bar {
            background: rgba(255,255,255,0.95);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .status-card {
            background: white;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #4CAF50;
        }
        .status-card.warning {
            border-left-color: #FF9800;
        }
        .status-card.error {
            border-left-color: #F44336;
        }
        .status-card h3 {
            margin: 0 0 10px 0;
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
        }
        .status-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .status-card .unit {
            font-size: 0.8em;
            color: #666;
        }
        .charts-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .chart-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-card h3 {
            margin: 0 0 15px 0;
            color: #333;
        }
        .log-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-height: 400px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .log-entry:last-child {
            border-bottom: none;
        }
        .log-time {
            color: #666;
            font-size: 0.8em;
        }
        .log-level {
            font-weight: bold;
            margin: 0 5px;
        }
        .log-level.INFO { color: #2196F3; }
        .log-level.WARNING { color: #FF9800; }
        .log-level.ERROR { color: #F44336; }
        .log-level.SUCCESS { color: #4CAF50; }
        .refresh-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(255,255,255,0.9);
            padding: 10px;
            border-radius: 5px;
            font-size: 0.8em;
            color: #666;
        }
        @media (max-width: 768px) {
            .charts-container {
                grid-template-columns: 1fr;
            }
            .status-grid {
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Petty Cash Sorter Monitor</h1>
            <p>Real-time system monitoring and performance tracking</p>
        </div>
        
        <div class="refresh-indicator" id="refreshIndicator">
            Last update: <span id="lastUpdate">Connecting...</span>
        </div>
        
        <div class="status-bar">
            <div class="status-grid">
                <div class="status-card" id="systemStatus">
                    <h3>System Status</h3>
                    <div class="value" id="systemStatusValue">Initializing...</div>
                </div>
                <div class="status-card" id="uptimeCard">
                    <h3>Uptime</h3>
                    <div class="value" id="uptimeValue">--</div>
                    <div class="unit">hours</div>
                </div>
                <div class="status-card" id="transactionsCard">
                    <h3>Transactions Processed</h3>
                    <div class="value" id="transactionsValue">0</div>
                    <div class="unit">total</div>
                </div>
                <div class="status-card" id="successRateCard">
                    <h3>Success Rate</h3>
                    <div class="value" id="successRateValue">0%</div>
                    <div class="unit">matches</div>
                </div>
                <div class="status-card" id="memoryCard">
                    <h3>Memory Usage</h3>
                    <div class="value" id="memoryValue">0</div>
                    <div class="unit">MB</div>
                </div>
                <div class="status-card" id="apiRateCard">
                    <h3>API Rate</h3>
                    <div class="value" id="apiRateValue">0</div>
                    <div class="unit">req/min</div>
                </div>
            </div>
        </div>
        
        <div class="charts-container">
            <div class="chart-card">
                <h3>Processing Performance</h3>
                <canvas id="performanceChart" width="400" height="200"></canvas>
            </div>
            <div class="chart-card">
                <h3>Memory Usage Trend</h3>
                <canvas id="memoryChart" width="400" height="200"></canvas>
            </div>
        </div>
        
        <div class="log-container">
            <h3>Recent Activity Log</h3>
            <div id="logEntries"></div>
        </div>
    </div>

    <script>
        const socket = io();
        let performanceChart, memoryChart;
        let performanceData = { labels: [], datasets: [] };
        let memoryData = { labels: [], datasets: [] };
        
        // Initialize charts
        function initCharts() {
            const ctx1 = document.getElementById('performanceChart').getContext('2d');
            const ctx2 = document.getElementById('memoryChart').getContext('2d');
            
            performanceChart = new Chart(ctx1, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Transactions/min',
                        data: [],
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
            
            memoryChart = new Chart(ctx2, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Memory (MB)',
                        data: [],
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
        }
        
        // Update status cards
        function updateStatusCard(id, value, unit = '', className = '') {
            const card = document.getElementById(id);
            const valueEl = card.querySelector('.value');
            const unitEl = card.querySelector('.unit');
            
            valueEl.textContent = value;
            if (unitEl) unitEl.textContent = unit;
            
            card.className = 'status-card ' + className;
        }
        
        // Add log entry
        function addLogEntry(entry) {
            const logContainer = document.getElementById('logEntries');
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            
            const time = new Date(entry.timestamp).toLocaleTimeString();
            logEntry.innerHTML = `
                <span class="log-time">${time}</span>
                <span class="log-level ${entry.level}">${entry.level}</span>
                <span class="log-message">${entry.message}</span>
            `;
            
            logContainer.insertBefore(logEntry, logContainer.firstChild);
            
            // Keep only last 50 entries
            while (logContainer.children.length > 50) {
                logContainer.removeChild(logContainer.lastChild);
            }
        }
        
        // Update charts
        function updateCharts(data) {
            if (data.performance) {
                const time = new Date().toLocaleTimeString();
                performanceChart.data.labels.push(time);
                performanceChart.data.datasets[0].data.push(data.performance.transactions_per_minute);
                
                if (performanceChart.data.labels.length > 20) {
                    performanceChart.data.labels.shift();
                    performanceChart.data.datasets[0].data.shift();
                }
                
                performanceChart.update();
            }
            
            if (data.memory) {
                const time = new Date().toLocaleTimeString();
                memoryChart.data.labels.push(time);
                memoryChart.data.datasets[0].data.push(data.memory.usage_mb);
                
                if (memoryChart.data.labels.length > 20) {
                    memoryChart.data.labels.shift();
                    memoryChart.data.datasets[0].data.shift();
                }
                
                memoryChart.update();
            }
        }
        
        // Socket event handlers
        socket.on('connect', function() {
            console.log('Connected to monitoring server');
            document.getElementById('lastUpdate').textContent = 'Connected';
        });
        
        socket.on('disconnect', function() {
            console.log('Disconnected from monitoring server');
            document.getElementById('lastUpdate').textContent = 'Disconnected';
        });
        
        socket.on('status_update', function(data) {
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            
            // Update status cards
            updateStatusCard('systemStatus', data.system_status, '', data.system_status === 'healthy' ? '' : 'warning');
            updateStatusCard('uptimeCard', data.uptime_hours.toFixed(1), 'hours');
            updateStatusCard('transactionsCard', data.total_transactions, 'total');
            updateStatusCard('successRateCard', data.success_rate.toFixed(1) + '%', 'matches');
            updateStatusCard('memoryCard', data.memory_usage.toFixed(1), 'MB');
            updateStatusCard('apiRateCard', data.api_rate.toFixed(1), 'req/min');
            
            // Update charts
            updateCharts(data);
        });
        
        socket.on('log_entry', function(entry) {
            addLogEntry(entry);
        });
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            initCharts();
        });
    </script>
</body>
</html>
"""

class RealTimeMonitor:
    """Real-time monitoring system with WebSocket updates."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.app = None
        self.socketio = None
        self.monitoring_thread = None
        self.running = False
        
        # Monitoring data
        self.current_stats = {
            'system_status': 'initializing',
            'uptime_hours': 0.0,
            'total_transactions': 0,
            'success_rate': 0.0,
            'memory_usage': 0.0,
            'api_rate': 0.0,
            'performance': {
                'transactions_per_minute': 0.0
            },
            'memory': {
                'usage_mb': 0.0
            }
        }
        
        # Performance history
        self.performance_history = []
        self.memory_history = []
        
        # Log entries
        self.recent_logs = []
        self.max_logs = 100
        
        if not FLASK_AVAILABLE:
            logging.warning("Flask not available - real-time monitoring disabled")
            return
        
        self._initialize_flask()
    
    def _initialize_flask(self):
        """Initialize Flask application and SocketIO."""
        try:
            self.app = Flask(__name__)
            self.app.config['SECRET_KEY'] = 'petty_cash_monitor_secret'
            self.socketio = SocketIO(self.app, cors_allowed_origins="*")
            
            # Register routes
            self._register_routes()
            
            logging.info("Flask application initialized for real-time monitoring")
            
        except Exception as e:
            logging.error(f"Failed to initialize Flask: {e}")
    
    def _register_routes(self):
        """Register Flask routes."""
        
        @self.app.route('/')
        def dashboard():
            return render_template_string(DASHBOARD_HTML)
        
        @self.app.route('/api/stats')
        def get_stats():
            return jsonify(self.current_stats)
        
        @self.app.route('/api/logs')
        def get_logs():
            return jsonify(self.recent_logs)
    
    def start_monitoring(self, port: int = 5000, host: str = 'localhost'):
        """Start the monitoring server."""
        if not FLASK_AVAILABLE or not self.app:
            logging.error("Cannot start monitoring - Flask not available")
            return False
        
        try:
            self.running = True
            
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitoring_thread.start()
            
            # Start Flask server
            logging.info(f"Starting real-time monitor on http://{host}:{port}")
            self.socketio.run(self.app, host=host, port=port, debug=False)
            
        except Exception as e:
            logging.error(f"Failed to start monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop the monitoring server."""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Update system statistics
                self._update_system_stats()
                
                # Emit updates via WebSocket
                if self.socketio:
                    self.socketio.emit('status_update', self.current_stats)
                
                # Sleep for update interval
                time.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _update_system_stats(self):
        """Update system statistics."""
        try:
            import psutil
            
            # Get system information
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Update current stats
            self.current_stats.update({
                'memory_usage': memory_info.rss / 1024 / 1024,  # MB
                'uptime_hours': (time.time() - process.create_time()) / 3600
            })
            
            # Update memory history
            self.memory_history.append({
                'timestamp': time.time(),
                'usage_mb': self.current_stats['memory_usage']
            })
            
            # Keep only last 100 entries
            if len(self.memory_history) > 100:
                self.memory_history.pop(0)
            
            # Calculate performance metrics
            self._calculate_performance_metrics()
            
        except Exception as e:
            logging.error(f"Error updating system stats: {e}")
    
    def _calculate_performance_metrics(self):
        """Calculate performance metrics from history."""
        try:
            # Calculate transactions per minute (simplified)
            if len(self.performance_history) > 1:
                recent_transactions = self.performance_history[-10:]  # Last 10 entries
                if len(recent_transactions) > 1:
                    time_span = recent_transactions[-1]['timestamp'] - recent_transactions[0]['timestamp']
                    total_transactions = sum(entry['transactions'] for entry in recent_transactions)
                    
                    if time_span > 0:
                        self.current_stats['performance']['transactions_per_minute'] = (
                            total_transactions / time_span * 60
                        )
            
            # Update memory trend
            if len(self.memory_history) > 1:
                self.current_stats['memory']['usage_mb'] = self.current_stats['memory_usage']
            
        except Exception as e:
            logging.error(f"Error calculating performance metrics: {e}")
    
    def update_transaction_stats(self, total_transactions: int, success_rate: float):
        """Update transaction statistics."""
        self.current_stats.update({
            'total_transactions': total_transactions,
            'success_rate': success_rate
        })
        
        # Add to performance history
        self.performance_history.append({
            'timestamp': time.time(),
            'transactions': total_transactions
        })
        
        # Keep only last 100 entries
        if len(self.performance_history) > 100:
            self.performance_history.pop(0)
    
    def update_transaction_count(self, count: int):
        """Update transaction count (alias for update_transaction_stats)."""
        self.update_transaction_stats(count, self.current_stats.get('success_rate', 0.0))
    
    def update_new_transaction_count(self, count: int):
        """Update new transaction count."""
        self.current_stats['new_transactions'] = count
        self.add_log_entry('INFO', f'Processing {count} new transactions')
    
    def update_api_stats(self, api_rate: float):
        """Update API rate statistics."""
        self.current_stats['api_rate'] = api_rate
    
    def update_system_status(self, status: str):
        """Update system status."""
        self.current_stats['system_status'] = status
    
    def add_log_entry(self, level: str, message: str):
        """Add a log entry to the real-time feed."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level.upper(),
            'message': message
        }
        
        self.recent_logs.append(log_entry)
        
        # Keep only recent logs
        if len(self.recent_logs) > self.max_logs:
            self.recent_logs.pop(0)
        
        # Emit via WebSocket
        if self.socketio:
            self.socketio.emit('log_entry', log_entry)
    
    def get_current_stats(self) -> Dict:
        """Get current monitoring statistics."""
        return self.current_stats.copy()

def main():
    """Test the real-time monitor."""
    if not FLASK_AVAILABLE:
        print("❌ Flask not available. Install with: pip install flask flask-socketio")
        return
    
    # Test configuration
    config = {
        'monitoring': {
            'real_time_dashboard': {
                'enabled': True,
                'port': 5000,
                'host': 'localhost'
            }
        }
    }
    
    # Create monitor
    monitor = RealTimeMonitor(config)
    
    # Add some test data
    monitor.update_transaction_stats(150, 85.5)
    monitor.update_api_stats(45.2)
    monitor.update_system_status('healthy')
    monitor.add_log_entry('INFO', 'System monitoring started')
    
    print("🚀 Starting real-time monitor...")
    print("📊 Dashboard will be available at: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop")
    
    try:
        monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\n⏹️  Stopping monitor...")
        monitor.stop_monitoring()
        print("✅ Monitor stopped")

if __name__ == "__main__":
    main() 