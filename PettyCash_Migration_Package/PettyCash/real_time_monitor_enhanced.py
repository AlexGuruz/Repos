#!/usr/bin/env python3
"""
Enhanced Real-time Monitoring Dashboard for Petty Cash Sorter
Live monitoring with WebSocket updates, performance metrics, and rule suggestion management
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

# Enhanced HTML template with rule management
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Petty Cash Sorter - Enhanced Monitor</title>
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
            max-width: 1600px;
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
        .nav-tabs {
            display: flex;
            background: rgba(255,255,255,0.95);
            border-radius: 10px 10px 0 0;
            overflow: hidden;
            margin-bottom: 0;
        }
        .nav-tab {
            flex: 1;
            padding: 15px 20px;
            background: rgba(255,255,255,0.8);
            border: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        .nav-tab.active {
            background: white;
            color: #667eea;
            border-bottom: 3px solid #667eea;
        }
        .nav-tab:hover {
            background: rgba(255,255,255,0.9);
        }
        .tab-content {
            background: rgba(255,255,255,0.95);
            border-radius: 0 0 10px 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .tab-pane {
            display: none;
        }
        .tab-pane.active {
            display: block;
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
        .logs-container {
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
            margin-left: 10px;
        }
        .log-level.INFO { color: #2196F3; }
        .log-level.SUCCESS { color: #4CAF50; }
        .log-level.WARNING { color: #FF9800; }
        .log-level.ERROR { color: #F44336; }
        .rule-suggestions {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .suggestion-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            background: #f9f9f9;
        }
        .suggestion-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .suggestion-source {
            font-weight: bold;
            font-size: 1.1em;
            color: #333;
        }
        .suggestion-confidence {
            background: #e3f2fd;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .suggestion-details {
            margin-bottom: 10px;
        }
        .suggestion-target {
            color: #666;
            font-size: 0.9em;
        }
        .suggestion-reason {
            color: #888;
            font-size: 0.8em;
            font-style: italic;
        }
        .suggestion-actions {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        .btn-approve {
            background: #4CAF50;
            color: white;
        }
        .btn-approve:hover {
            background: #45a049;
        }
        .btn-reject {
            background: #f44336;
            color: white;
        }
        .btn-reject:hover {
            background: #da190b;
        }
        .btn-edit {
            background: #2196F3;
            color: white;
        }
        .btn-edit:hover {
            background: #1976D2;
        }
        .no-suggestions {
            text-align: center;
            color: #666;
            font-style: italic;
            padding: 40px;
        }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin-bottom: 20px;
        }
        .refresh-btn:hover {
            background: #5a6fd8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Petty Cash Sorter - Enhanced Monitor</h1>
        </div>
        
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showTab('dashboard')">Dashboard</button>
            <button class="nav-tab" onclick="showTab('rules')">Rule Management</button>
            <button class="nav-tab" onclick="showTab('logs')">System Logs</button>
        </div>
        
        <div class="tab-content">
            <!-- Dashboard Tab -->
            <div id="dashboard" class="tab-pane active">
                <div class="status-grid">
                    <div class="status-card" id="system-status">
                        <h3>System Status</h3>
                        <div class="value" id="status-value">Loading...</div>
                    </div>
                    <div class="status-card">
                        <h3>Total Transactions</h3>
                        <div class="value" id="total-transactions">0</div>
                    </div>
                    <div class="status-card">
                        <h3>Success Rate</h3>
                        <div class="value" id="success-rate">0%</div>
                    </div>
                    <div class="status-card">
                        <h3>API Success Rate</h3>
                        <div class="value" id="api-rate">0%</div>
                    </div>
                    <div class="status-card">
                        <h3>Pending Rules</h3>
                        <div class="value" id="pending-rules">0</div>
                    </div>
                    <div class="status-card">
                        <h3>Uptime</h3>
                        <div class="value" id="uptime">0s</div>
                    </div>
                </div>
                
                <div class="charts-container">
                    <div class="chart-card">
                        <h3>Transaction Processing</h3>
                        <canvas id="transactionChart"></canvas>
                    </div>
                    <div class="chart-card">
                        <h3>API Performance</h3>
                        <canvas id="apiChart"></canvas>
                    </div>
                </div>
            </div>
            
            <!-- Rule Management Tab -->
            <div id="rules" class="tab-pane">
                <!-- Rule Statistics Dashboard -->
                <div class="status-grid" style="margin-bottom: 20px;">
                    <div class="status-card">
                        <h3>Total Rules</h3>
                        <div class="value" id="total-rules">0</div>
                    </div>
                    <div class="status-card">
                        <h3>Pending Suggestions</h3>
                        <div class="value" id="pending-suggestions">0</div>
                    </div>
                    <div class="status-card">
                        <h3>Success Rate</h3>
                        <div class="value" id="rule-success-rate">0%</div>
                    </div>
                    <div class="status-card">
                        <h3>Companies</h3>
                        <div class="value" id="rule-companies">0</div>
                    </div>
                </div>
                
                <!-- Rule Management Controls -->
                <div style="margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="refresh-btn" onclick="refreshRuleSuggestions()">Refresh Suggestions</button>
                    <button class="refresh-btn" onclick="clearAllSuggestions()" style="background: #f44336;">Clear All Suggestions</button>
                    <button class="refresh-btn" onclick="showRuleList()" style="background: #2196F3;">View All Rules</button>
                    <button class="refresh-btn" onclick="showRulePerformance()" style="background: #FF9800;">Rule Performance</button>
                    <button class="refresh-btn" onclick="exportRules()" style="background: #4CAF50;">Export Rules</button>
                </div>
                
                <!-- Search Rules -->
                <div style="margin-bottom: 20px;">
                    <input type="text" id="rule-search" placeholder="Search rules by source, company, or target..." 
                           style="width: 60%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin-right: 10px;">
                    <button class="refresh-btn" onclick="searchRules()" style="background: #9C27B0;">Search</button>
                </div>
                
                <!-- Rule Suggestions Section -->
                <div id="rule-suggestions-container" class="rule-suggestions">
                    <div class="no-suggestions">Loading rule suggestions...</div>
                </div>
                
                <!-- Full Rule List Section (Hidden by default) -->
                <div id="rule-list-container" class="rule-suggestions" style="display: none;">
                    <h3>All Rules</h3>
                    <div id="rule-list-content">
                        <div class="no-suggestions">Loading rules...</div>
                    </div>
                </div>
                
                <!-- Rule Performance Section (Hidden by default) -->
                <div id="rule-performance-container" class="rule-suggestions" style="display: none;">
                    <h3>Rule Performance Analytics</h3>
                    <div id="rule-performance-content">
                        <div class="no-suggestions">Loading performance data...</div>
                    </div>
                </div>
            </div>
            
            <!-- Logs Tab -->
            <div id="logs" class="tab-pane">
                <div class="logs-container" id="logs-container">
                    <div class="log-entry">
                        <span class="log-time">Loading logs...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let socket = io();
        let transactionChart, apiChart;
        
        // Tab management
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-pane').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            // Load tab-specific data
            if (tabName === 'rules') {
                refreshRuleSuggestions();
                loadRuleStatistics();
            } else if (tabName === 'logs') {
                refreshLogs();
            }
        }
        
        // Socket event handlers
        socket.on('connect', function() {
            console.log('Connected to monitor');
        });
        
        socket.on('stats_update', function(data) {
            updateDashboard(data);
        });
        
        socket.on('log_update', function(data) {
            addLogEntry(data);
        });
        
        // Dashboard updates
        function updateDashboard(data) {
            document.getElementById('status-value').textContent = data.system_status || 'Unknown';
            document.getElementById('total-transactions').textContent = data.total_transactions || 0;
            document.getElementById('success-rate').textContent = (data.success_rate || 0) + '%';
            document.getElementById('api-rate').textContent = (data.api_success_rate || 0) + '%';
            document.getElementById('pending-rules').textContent = data.pending_rules || 0;
            document.getElementById('uptime').textContent = formatUptime(data.uptime || 0);
            
            updateCharts(data);
        }
        
        function updateCharts(data) {
            // Update transaction chart
            if (transactionChart) {
                transactionChart.data.labels.push(new Date().toLocaleTimeString());
                transactionChart.data.datasets[0].data.push(data.total_transactions || 0);
                if (transactionChart.data.labels.length > 20) {
                    transactionChart.data.labels.shift();
                    transactionChart.data.datasets[0].data.shift();
                }
                transactionChart.update();
            }
            
            // Update API chart
            if (apiChart) {
                apiChart.data.labels.push(new Date().toLocaleTimeString());
                apiChart.data.datasets[0].data.push(data.api_success_rate || 0);
                if (apiChart.data.labels.length > 20) {
                    apiChart.data.labels.shift();
                    apiChart.data.datasets[0].data.shift();
                }
                apiChart.update();
            }
        }
        
        function addLogEntry(data) {
            const logsContainer = document.getElementById('logs-container');
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry';
            logEntry.innerHTML = `
                <span class="log-time">${data.timestamp}</span>
                <span class="log-level ${data.level}">${data.level}</span>
                <span class="log-message">${data.message}</span>
            `;
            logsContainer.appendChild(logEntry);
            logsContainer.scrollTop = logsContainer.scrollHeight;
            
            // Keep only last 100 entries
            while (logsContainer.children.length > 100) {
                logsContainer.removeChild(logsContainer.firstChild);
            }
        }
        
        // Rule management
        function refreshRuleSuggestions() {
            fetch('/api/rule-suggestions')
                .then(response => response.json())
                .then(data => {
                    displayRuleSuggestions(data.suggestions);
                })
                .catch(error => {
                    console.error('Error fetching rule suggestions:', error);
                });
        }
        
        function displayRuleSuggestions(suggestions) {
            const container = document.getElementById('rule-suggestions-container');
            
            if (!suggestions || suggestions.length === 0) {
                container.innerHTML = '<div class="no-suggestions">No pending rule suggestions</div>';
                return;
            }
            
            let html = '';
            suggestions.forEach((suggestion, index) => {
                html += `
                    <div class="suggestion-card">
                        <div class="suggestion-header">
                            <div class="suggestion-source">${suggestion.source}</div>
                            <div class="suggestion-confidence">${(suggestion.confidence * 100).toFixed(1)}% confidence</div>
                        </div>
                        <div class="suggestion-details">
                            <div class="suggestion-target">Target: ${suggestion.target_sheet} → ${suggestion.target_header}</div>
                            <div class="suggestion-reason">${suggestion.reason || 'AI-generated suggestion'}</div>
                        </div>
                        <div class="suggestion-actions">
                            <button class="btn btn-approve" onclick="approveRule('${suggestion.id}')">Approve</button>
                            <button class="btn btn-reject" onclick="rejectRule('${suggestion.id}')">Reject</button>
                            <button class="btn btn-edit" onclick="editRule('${suggestion.id}')">Edit</button>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        }
        
        function approveRule(suggestionId) {
            fetch('/api/approve-rule', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({suggestion_id: suggestionId})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    refreshRuleSuggestions();
                    alert('Rule approved successfully!');
                } else {
                    alert('Error approving rule: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error approving rule');
            });
        }
        
        function rejectRule(suggestionId) {
            const reason = prompt('Enter rejection reason (optional):');
            fetch('/api/reject-rule', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    suggestion_id: suggestionId,
                    reason: reason || ''
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    refreshRuleSuggestions();
                    alert('Rule rejected successfully!');
                } else {
                    alert('Error rejecting rule: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error rejecting rule');
            });
        }
        
        function editRule(suggestionId) {
            // Find the rule data first
            fetch('/api/rules')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const rule = data.rules.find(r => r.source === suggestionId);
                        if (rule) {
                            showEditRuleDialog(rule);
                        } else {
                            alert('Rule not found: ' + suggestionId);
                        }
                    } else {
                        alert('Error loading rules: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error loading rule data');
                });
        }
        
        function showEditRuleDialog(rule) {
            // Create modal dialog for editing
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            `;
            
            modal.innerHTML = `
                <div style="background: white; padding: 30px; border-radius: 10px; min-width: 500px; max-width: 700px;">
                    <h3 style="margin-top: 0;">Edit Rule</h3>
                    <form id="editRuleForm">
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Source:</label>
                            <input type="text" id="editSource" value="${rule.source || ''}" 
                                   style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Target Sheet:</label>
                            <select id="editTargetSheet" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required onchange="updateHeaderOptions()">
                                <option value="">Loading sheets...</option>
                            </select>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Target Header:</label>
                            <select id="editTargetHeader" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                                <option value="">Select a sheet first...</option>
                            </select>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Confidence Threshold:</label>
                            <input type="number" id="editConfidence" value="${(rule.confidence_threshold || 0.7) * 100}" 
                                   min="0" max="100" step="1"
                                   style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                            <small style="color: #666;">Enter as percentage (0-100)</small>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Company:</label>
                            <select id="editCompany" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="NUGZ" ${rule.company === 'NUGZ' ? 'selected' : ''}>NUGZ</option>
                                <option value="JGD" ${rule.company === 'JGD' ? 'selected' : ''}>JGD</option>
                                <option value="PUFFIN" ${rule.company === 'PUFFIN' ? 'selected' : ''}>PUFFIN</option>
                                <option value="UNKNOWN" ${rule.company === 'UNKNOWN' ? 'selected' : ''}>UNKNOWN</option>
                            </select>
                        </div>
                        <div style="display: flex; gap: 10px; justify-content: flex-end;">
                            <button type="button" onclick="closeEditDialog()" 
                                    style="padding: 10px 20px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer;">
                                Cancel
                            </button>
                            <button type="submit" 
                                    style="padding: 10px 20px; border: none; background: #4CAF50; color: white; border-radius: 4px; cursor: pointer;">
                                Save Changes
                            </button>
                        </div>
                    </form>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Load available sheets
            loadAvailableSheets(rule.target_sheet);
            
            // Handle form submission
            document.getElementById('editRuleForm').addEventListener('submit', function(e) {
                e.preventDefault();
                saveRuleChanges(rule.source);
            });
        }
        
        function closeEditDialog() {
            const modal = document.querySelector('div[style*="position: fixed"]');
            if (modal) {
                modal.remove();
            }
        }
        
        function saveRuleChanges(originalSource) {
            const updatedRule = {
                source: document.getElementById('editSource').value,
                target_sheet: document.getElementById('editTargetSheet').value,
                target_header: document.getElementById('editTargetHeader').value,
                confidence_threshold: parseFloat(document.getElementById('editConfidence').value) / 100,
                company: document.getElementById('editCompany').value
            };
            
            fetch(`/api/rules/${encodeURIComponent(originalSource)}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updatedRule)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Rule updated successfully!');
                    closeEditDialog();
                    // Refresh the current view
                    if (document.getElementById('rule-list-container').style.display !== 'none') {
                        showRuleList();
                    }
                    // Refresh statistics
                    loadRuleStatistics();
                } else {
                    alert('Error updating rule: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error updating rule');
            });
        }
        
        // Enhanced Rule Management Functions
        function clearAllSuggestions() {
            if (confirm('Are you sure you want to clear all pending rule suggestions?')) {
                fetch('/api/clear-suggestions', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        refreshRuleSuggestions();
                        alert('All suggestions cleared successfully!');
                    } else {
                        alert('Error clearing suggestions: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error clearing suggestions');
                });
            }
        }
        
        function showRuleList() {
            // Hide other sections
            document.getElementById('rule-suggestions-container').style.display = 'none';
            document.getElementById('rule-performance-container').style.display = 'none';
            document.getElementById('rule-list-container').style.display = 'block';
            
            // Load all rules
            fetch('/api/rules')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displayAllRules(data.rules);
                    } else {
                        document.getElementById('rule-list-content').innerHTML = 
                            '<div class="no-suggestions">Error loading rules: ' + data.error + '</div>';
                    }
                })
                .catch(error => {
                    console.error('Error fetching rules:', error);
                    document.getElementById('rule-list-content').innerHTML = 
                        '<div class="no-suggestions">Error loading rules</div>';
                });
        }
        
        function displayAllRules(rules) {
            const container = document.getElementById('rule-list-content');
            
            if (!rules || rules.length === 0) {
                container.innerHTML = '<div class="no-suggestions">No rules found</div>';
                return;
            }
            
            let html = '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse;">';
            html += '<thead><tr style="background: #f5f5f5;">';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Source</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Company</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Target Sheet</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Target Header</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Confidence</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Performance</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Actions</th>';
            html += '</tr></thead><tbody>';
            
            rules.forEach(rule => {
                const performance = rule.performance || {};
                const successRate = performance.rate ? performance.rate.toFixed(1) + '%' : 'N/A';
                const totalMatches = performance.total || 0;
                
                html += '<tr>';
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${rule.source || ''}</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${rule.company || 'Unknown'}</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${rule.target_sheet || ''}</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${rule.target_header || ''}</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${(rule.confidence_threshold * 100).toFixed(1)}%</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${successRate} (${totalMatches} matches)</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">
                    <button class="btn btn-edit" onclick="editExistingRule('${rule.source}')" style="margin-right: 5px;">Edit</button>
                    <button class="btn btn-reject" onclick="deleteExistingRule('${rule.source}')">Delete</button>
                </td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table></div>';
            container.innerHTML = html;
        }
        
        function showRulePerformance() {
            // Hide other sections
            document.getElementById('rule-suggestions-container').style.display = 'none';
            document.getElementById('rule-list-container').style.display = 'none';
            document.getElementById('rule-performance-container').style.display = 'block';
            
            // Load performance data
            fetch('/api/rule-performance')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displayRulePerformance(data.performance);
                    } else {
                        document.getElementById('rule-performance-content').innerHTML = 
                            '<div class="no-suggestions">Error loading performance data: ' + data.error + '</div>';
                    }
                })
                .catch(error => {
                    console.error('Error fetching performance:', error);
                    document.getElementById('rule-performance-content').innerHTML = 
                        '<div class="no-suggestions">Error loading performance data</div>';
                });
        }
        
        function displayRulePerformance(performance) {
            const container = document.getElementById('rule-performance-content');
            
            if (!performance) {
                container.innerHTML = '<div class="no-suggestions">No performance data available</div>';
                return;
            }
            
            let html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">';
            
            // Company breakdown
            html += '<div class="chart-card"><h4>Rules by Company</h4>';
            if (performance.rules_by_company) {
                Object.entries(performance.rules_by_company).forEach(([company, count]) => {
                    html += `<div style="margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 5px;">
                        <strong>${company}:</strong> ${count} rules
                    </div>`;
                });
            }
            html += '</div>';
            
            // Success rates
            html += '<div class="chart-card"><h4>Success Rates by Company</h4>';
            if (performance.success_rates) {
                Object.entries(performance.success_rates).forEach(([company, stats]) => {
                    const rate = stats.rate || 0;
                    const color = rate > 80 ? '#4CAF50' : rate > 60 ? '#FF9800' : '#F44336';
                    html += `<div style="margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 5px;">
                        <strong>${company}:</strong> 
                        <span style="color: ${color}; font-weight: bold;">${rate.toFixed(1)}%</span>
                        (${stats.success}/${stats.total} matches)
                    </div>`;
                });
            }
            html += '</div>';
            
            // Recent matches
            html += '<div class="chart-card" style="grid-column: 1 / -1;"><h4>Recent Matches</h4>';
            if (performance.recent_matches && performance.recent_matches.length > 0) {
                html += '<div style="max-height: 300px; overflow-y: auto;">';
                performance.recent_matches.slice(0, 20).forEach(match => {
                    const color = match.success ? '#4CAF50' : '#F44336';
                    const status = match.success ? '✓ Success' : '✗ Failed';
                    html += `<div style="margin: 5px 0; padding: 8px; background: #f9f9f9; border-radius: 3px; border-left: 3px solid ${color};">
                        <span style="color: ${color}; font-weight: bold;">${status}</span> - 
                        ${match.source} (${match.company}) - 
                        <span style="color: #666; font-size: 0.9em;">${match.timestamp}</span>
                    </div>`;
                });
                html += '</div>';
            } else {
                html += '<div class="no-suggestions">No recent matches</div>';
            }
            html += '</div>';
            
            html += '</div>';
            container.innerHTML = html;
        }
        
        function searchRules() {
            const query = document.getElementById('rule-search').value.trim();
            if (!query) {
                alert('Please enter a search term');
                return;
            }
            
            fetch(`/api/search-rules?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displaySearchResults(data.results, query);
                    } else {
                        alert('Error searching rules: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error searching rules');
                });
        }
        
        function displaySearchResults(results, query) {
            // Show results in rule list container
            document.getElementById('rule-suggestions-container').style.display = 'none';
            document.getElementById('rule-performance-container').style.display = 'none';
            document.getElementById('rule-list-container').style.display = 'block';
            
            const container = document.getElementById('rule-list-content');
            
            if (!results || results.length === 0) {
                container.innerHTML = `<div class="no-suggestions">No rules found for "${query}"</div>`;
                return;
            }
            
            let html = `<h4>Search Results for "${query}" (${results.length} found)</h4>`;
            html += '<div style="overflow-x: auto;"><table style="width: 100%; border-collapse: collapse;">';
            html += '<thead><tr style="background: #f5f5f5;">';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Source</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Target Sheet</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Target Header</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Confidence</th>';
            html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Actions</th>';
            html += '</tr></thead><tbody>';
            
            results.forEach(rule => {
                html += '<tr>';
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${rule.source || ''}</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${rule.target_sheet || ''}</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${rule.target_header || ''}</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">${(rule.confidence_threshold * 100).toFixed(1)}%</td>`;
                html += `<td style="padding: 10px; border: 1px solid #ddd;">
                    <button class="btn btn-edit" onclick="editExistingRule('${rule.source}')" style="margin-right: 5px;">Edit</button>
                    <button class="btn btn-reject" onclick="deleteExistingRule('${rule.source}')">Delete</button>
                </td>`;
                html += '</tr>';
            });
            
            html += '</tbody></table></div>';
            container.innerHTML = html;
        }
        
        function exportRules() {
            fetch('/api/export-rules')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Create and download file
                        const blob = new Blob([JSON.stringify(data.rules, null, 2)], {type: 'application/json'});
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `petty_cash_rules_${new Date().toISOString().split('T')[0]}.json`;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                        alert(`Exported ${data.rules.length} rules successfully!`);
                    } else {
                        alert('Error exporting rules: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error exporting rules');
                });
        }
        
        function deleteExistingRule(ruleId) {
            if (confirm(`Are you sure you want to delete the rule "${ruleId}"?`)) {
                fetch(`/api/rules/${encodeURIComponent(ruleId)}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Rule deleted successfully!');
                        // Refresh the current view
                        if (document.getElementById('rule-list-container').style.display !== 'none') {
                            showRuleList();
                        }
                    } else {
                        alert('Error deleting rule: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error deleting rule');
                });
            }
        }
        
        function editExistingRule(ruleId) {
            // Find the rule data first
            fetch('/api/rules')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const rule = data.rules.find(r => r.source === ruleId);
                        if (rule) {
                            showEditRuleDialog(rule);
                        } else {
                            alert('Rule not found: ' + ruleId);
                        }
                    } else {
                        alert('Error loading rules: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error loading rule data');
                });
        }
        
        function showEditRuleDialog(rule) {
            // Create modal dialog for editing
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            `;
            
            modal.innerHTML = `
                <div style="background: white; padding: 30px; border-radius: 10px; min-width: 500px; max-width: 700px;">
                    <h3 style="margin-top: 0;">Edit Rule</h3>
                    <form id="editRuleForm">
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Source:</label>
                            <input type="text" id="editSource" value="${rule.source || ''}" 
                                   style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Target Sheet:</label>
                            <select id="editTargetSheet" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required onchange="updateHeaderOptions()">
                                <option value="">Loading sheets...</option>
                            </select>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Target Header:</label>
                            <select id="editTargetHeader" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                                <option value="">Select a sheet first...</option>
                            </select>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Confidence Threshold:</label>
                            <input type="number" id="editConfidence" value="${(rule.confidence_threshold || 0.7) * 100}" 
                                   min="0" max="100" step="1"
                                   style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required>
                            <small style="color: #666;">Enter as percentage (0-100)</small>
                        </div>
                        <div style="margin-bottom: 15px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">Company:</label>
                            <select id="editCompany" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="NUGZ" ${rule.company === 'NUGZ' ? 'selected' : ''}>NUGZ</option>
                                <option value="JGD" ${rule.company === 'JGD' ? 'selected' : ''}>JGD</option>
                                <option value="PUFFIN" ${rule.company === 'PUFFIN' ? 'selected' : ''}>PUFFIN</option>
                                <option value="UNKNOWN" ${rule.company === 'UNKNOWN' ? 'selected' : ''}>UNKNOWN</option>
                            </select>
                        </div>
                        <div style="display: flex; gap: 10px; justify-content: flex-end;">
                            <button type="button" onclick="closeEditDialog()" 
                                    style="padding: 10px 20px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer;">
                                Cancel
                            </button>
                            <button type="submit" 
                                    style="padding: 10px 20px; border: none; background: #4CAF50; color: white; border-radius: 4px; cursor: pointer;">
                                Save Changes
                            </button>
                        </div>
                    </form>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Load available sheets
            loadAvailableSheets(rule.target_sheet);
            
            // Handle form submission
            document.getElementById('editRuleForm').addEventListener('submit', function(e) {
                e.preventDefault();
                saveRuleChanges(rule.source);
            });
        }
        
        function closeEditDialog() {
            const modal = document.querySelector('div[style*="position: fixed"]');
            if (modal) {
                modal.remove();
            }
        }
        
        function saveRuleChanges(originalSource) {
            const updatedRule = {
                source: document.getElementById('editSource').value,
                target_sheet: document.getElementById('editTargetSheet').value,
                target_header: document.getElementById('editTargetHeader').value,
                confidence_threshold: parseFloat(document.getElementById('editConfidence').value) / 100,
                company: document.getElementById('editCompany').value
            };
            
            fetch(`/api/rules/${encodeURIComponent(originalSource)}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updatedRule)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Rule updated successfully!');
                    closeEditDialog();
                    // Refresh the current view
                    if (document.getElementById('rule-list-container').style.display !== 'none') {
                        showRuleList();
                    }
                    // Refresh statistics
                    loadRuleStatistics();
                } else {
                    alert('Error updating rule: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error updating rule');
            });
        }
        
        function loadAvailableSheets(selectedSheet) {
            fetch('/api/available-sheets')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const sheetSelect = document.getElementById('editTargetSheet');
                        sheetSelect.innerHTML = '<option value="">Select a sheet...</option>';
                        
                        data.sheets.forEach(sheet => {
                            const option = document.createElement('option');
                            option.value = sheet;
                            option.textContent = sheet;
                            if (sheet === selectedSheet) {
                                option.selected = true;
                            }
                            sheetSelect.appendChild(option);
                        });
                        
                        // Load headers for the selected sheet
                        if (selectedSheet) {
                            updateHeaderOptions();
                        }
                    } else {
                        console.error('Error loading sheets:', data.error);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        }
        
        function updateHeaderOptions() {
            const sheetSelect = document.getElementById('editTargetSheet');
            const headerSelect = document.getElementById('editTargetHeader');
            const selectedSheet = sheetSelect.value;
            
            if (!selectedSheet) {
                headerSelect.innerHTML = '<option value="">Select a sheet first...</option>';
                return;
            }
            
            headerSelect.innerHTML = '<option value="">Loading headers...</option>';
            
            fetch(`/api/available-headers/${encodeURIComponent(selectedSheet)}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        headerSelect.innerHTML = '<option value="">Select a header...</option>';
                        
                        data.headers.forEach(header => {
                            const option = document.createElement('option');
                            option.value = header;
                            option.textContent = header;
                            headerSelect.appendChild(option);
                        });
                    } else {
                        console.error('Error loading headers:', data.error);
                        headerSelect.innerHTML = '<option value="">Error loading headers</option>';
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    headerSelect.innerHTML = '<option value="">Error loading headers</option>';
                });
        }
        
        // Load rule statistics on page load
        function loadRuleStatistics() {
            fetch('/api/rule-stats')
                .then(response => response.json())
                .then(data => {
                    if (data.total_rules !== undefined) {
                        document.getElementById('total-rules').textContent = data.total_rules || 0;
                        document.getElementById('pending-suggestions').textContent = data.pending_suggestions || 0;
                        document.getElementById('rule-success-rate').textContent = (data.overall_success_rate || 0).toFixed(1) + '%';
                        document.getElementById('rule-companies').textContent = data.companies_count || 0;
                    }
                })
                .catch(error => {
                    console.error('Error loading rule statistics:', error);
                });
        }
        
        function refreshLogs() {
            fetch('/api/logs')
                .then(response => response.json())
                .then(data => {
                    const logsContainer = document.getElementById('logs-container');
                    logsContainer.innerHTML = '';
                    data.logs.forEach(log => {
                        addLogEntry(log);
                    });
                })
                .catch(error => {
                    console.error('Error fetching logs:', error);
                });
        }
        
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            return `${hours}h ${minutes}m ${secs}s`;
        }
        
        // Initialize charts
        document.addEventListener('DOMContentLoaded', function() {
            // Transaction chart
            const transactionCtx = document.getElementById('transactionChart').getContext('2d');
            transactionChart = new Chart(transactionCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Transactions',
                        data: [],
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
            
            // API chart
            const apiCtx = document.getElementById('apiChart').getContext('2d');
            apiChart = new Chart(apiCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'API Success Rate (%)',
                        data: [],
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100
                        }
                    }
                }
            });

            // Load rule statistics on page load
            loadRuleStatistics();
        });
    </script>
</body>
</html>
"""

class EnhancedRealTimeMonitor:
    """Enhanced real-time monitor with rule suggestion management."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.app = None
        self.socketio = None
        self.monitoring_thread = None
        self.is_monitoring = False
        
        # System stats
        self.system_stats = {
            'system_status': 'unknown',
            'total_transactions': 0,
            'new_transactions': 0,
            'success_rate': 0.0,
            'api_success_rate': 0.0,
            'pending_rules': 0,
            'uptime': 0,
            'start_time': time.time()
        }
        
        # Logs
        self.logs = []
        self.max_logs = 1000
        
        # AI rule matcher reference (will be set later)
        self.ai_matcher = None
        
        if FLASK_AVAILABLE:
            self._initialize_flask()
        else:
            logging.error("Flask not available - enhanced monitoring disabled")
    
    def _initialize_flask(self):
        """Initialize Flask application."""
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self._register_routes()
    
    def _register_routes(self):
        """Register Flask routes."""
        
        @self.app.route('/')
        def dashboard():
            return render_template_string(DASHBOARD_HTML)
        
        @self.app.route('/api/stats')
        def get_stats():
            return jsonify(self.system_stats)
        
        @self.app.route('/api/logs')
        def get_logs():
            return jsonify({'logs': self.logs[-100:]})  # Last 100 logs
        
        @self.app.route('/api/rule-suggestions')
        def get_rule_suggestions():
            if self.ai_matcher:
                suggestions = self.ai_matcher.get_pending_rule_suggestions()
                return jsonify({'suggestions': suggestions})
            return jsonify({'suggestions': []})
        
        @self.app.route('/api/approve-rule', methods=['POST'])
        def approve_rule():
            try:
                data = request.get_json()
                suggestion_id = data.get('suggestion_id')
                
                if self.ai_matcher and suggestion_id:
                    success = self.ai_matcher.approve_rule_suggestion(suggestion_id)
                    if success:
                        self.add_log_entry('SUCCESS', f'Rule suggestion approved: {suggestion_id}')
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to approve rule'})
                else:
                    return jsonify({'success': False, 'error': 'Invalid request'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/reject-rule', methods=['POST'])
        def reject_rule():
            try:
                data = request.get_json()
                suggestion_id = data.get('suggestion_id')
                reason = data.get('reason', '')
                
                if self.ai_matcher and suggestion_id:
                    success = self.ai_matcher.reject_rule_suggestion(suggestion_id, reason)
                    if success:
                        self.add_log_entry('INFO', f'Rule suggestion rejected: {suggestion_id} (reason: {reason})')
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to reject rule'})
                else:
                    return jsonify({'success': False, 'error': 'Invalid request'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/rule-stats')
        def get_rule_stats():
            """Get comprehensive rule statistics."""
            try:
                if self.ai_matcher:
                    stats = self.ai_matcher.get_match_statistics()
                    return jsonify(stats)
                return jsonify({'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'error': str(e)})
        
        @self.app.route('/api/clear-suggestions', methods=['POST'])
        def clear_suggestions():
            """Clear all pending rule suggestions."""
            try:
                if self.ai_matcher:
                    success = self.ai_matcher.clear_pending_suggestions()
                    if success:
                        self.add_log_entry('INFO', 'All pending rule suggestions cleared')
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to clear suggestions'})
                else:
                    return jsonify({'success': False, 'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/export-rules')
        def export_rules():
            """Export all rules to JSON format."""
            try:
                if self.ai_matcher:
                    rules = self.ai_matcher.export_all_rules()
                    return jsonify({'success': True, 'rules': rules})
                return jsonify({'success': False, 'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/import-rules', methods=['POST'])
        def import_rules():
            """Import rules from JSON format."""
            try:
                data = request.get_json()
                rules = data.get('rules', [])
                
                if self.ai_matcher and rules:
                    success = self.ai_matcher.import_rules(rules)
                    if success:
                        self.add_log_entry('SUCCESS', f'Imported {len(rules)} rules')
                        return jsonify({'success': True, 'imported_count': len(rules)})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to import rules'})
                else:
                    return jsonify({'success': False, 'error': 'Invalid request'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/search-rules')
        def search_rules():
            """Search rules by source, company, or target."""
            try:
                query = request.args.get('q', '').strip()
                company = request.args.get('company', '').strip()
                
                if self.ai_matcher and query:
                    results = self.ai_matcher.search_rules(query, company)
                    return jsonify({'success': True, 'results': results})
                else:
                    return jsonify({'success': False, 'error': 'Query required'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/rule-performance')
        def get_rule_performance():
            """Get performance metrics for rules."""
            try:
                if self.ai_matcher:
                    performance = self.ai_matcher.get_rule_performance_metrics()
                    return jsonify({'success': True, 'performance': performance})
                return jsonify({'success': False, 'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/regenerate-suggestions', methods=['POST'])
        def regenerate_suggestions():
            """Regenerate rule suggestions from unmatched transactions."""
            try:
                if self.ai_matcher:
                    # This would need access to unmatched transactions
                    # For now, we'll just trigger a suggestion refresh
                    success = self.ai_matcher.refresh_suggestions()
                    if success:
                        self.add_log_entry('INFO', 'Rule suggestions regenerated')
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to regenerate suggestions'})
                else:
                    return jsonify({'success': False, 'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/rules', methods=['GET'])
        def get_rules():
            """Get the full list of rules with performance data."""
            try:
                if self.ai_matcher:
                    rules = self.ai_matcher.get_all_rules_with_performance()
                    return jsonify({'success': True, 'rules': rules})
                return jsonify({'success': False, 'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/rules/<rule_id>', methods=['PUT'])
        def edit_rule(rule_id):
            """Edit a rule by ID (user only)."""
            try:
                data = request.get_json()
                if self.ai_matcher:
                    success = self.ai_matcher.edit_rule(rule_id, data)
                    if success:
                        self.add_log_entry('SUCCESS', f'Rule {rule_id} edited by user')
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to edit rule'})
                return jsonify({'success': False, 'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/rules/<rule_id>', methods=['DELETE'])
        def delete_rule(rule_id):
            """Delete a rule by ID (user only)."""
            try:
                if self.ai_matcher:
                    success = self.ai_matcher.delete_rule(rule_id)
                    if success:
                        self.add_log_entry('INFO', f'Rule {rule_id} deleted by user')
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False, 'error': 'Failed to delete rule'})
                return jsonify({'success': False, 'error': 'AI matcher not available'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/rules', methods=['POST'])
        def add_rule():
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'success': False, 'error': 'No data provided'})
                
                success = self.ai_matcher.add_rule(data)
                return jsonify({'success': success})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/available-sheets')
        def get_available_sheets():
            try:
                sheets = self.ai_matcher.get_available_sheets_for_editing()
                return jsonify({'success': True, 'sheets': sheets})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/available-headers/<sheet_name>')
        def get_available_headers(sheet_name):
            try:
                headers = self.ai_matcher.get_available_headers_for_sheet_editing(sheet_name)
                return jsonify({'success': True, 'headers': headers})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
    
    def set_ai_matcher(self, ai_matcher):
        """Set the AI rule matcher reference."""
        self.ai_matcher = ai_matcher
    
    def start_monitoring(self, port: int = 5000, host: str = 'localhost'):
        """Start the monitoring server."""
        if not FLASK_AVAILABLE:
            logging.error("Cannot start monitoring - Flask not available")
            return False
        
        try:
            self.is_monitoring = True
            
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitoring_thread.start()
            
            # Start Flask server
            self.socketio.run(self.app, host=host, port=port, debug=False)
            
            return True
        except Exception as e:
            logging.error(f"Failed to start monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop the monitoring server."""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                self._update_system_stats()
                
                # Emit updates via WebSocket
                if self.socketio:
                    self.socketio.emit('stats_update', self.system_stats)
                
                time.sleep(2)  # Update every 2 seconds
            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def _update_system_stats(self):
        """Update system statistics."""
        try:
            # Update uptime
            self.system_stats['uptime'] = int(time.time() - self.system_stats['start_time'])
            
            # Update pending rules count
            if self.ai_matcher:
                suggestions = self.ai_matcher.get_pending_rule_suggestions()
                self.system_stats['pending_rules'] = len(suggestions)
            
        except Exception as e:
            logging.error(f"Error updating system stats: {e}")
    
    def update_transaction_stats(self, total_transactions: int, success_rate: float):
        """Update transaction statistics."""
        self.system_stats['total_transactions'] = total_transactions
        self.system_stats['success_rate'] = success_rate
    
    def update_transaction_count(self, count: int):
        """Update transaction count."""
        self.system_stats['total_transactions'] = count
    
    def update_new_transaction_count(self, count: int):
        """Update new transaction count."""
        self.system_stats['new_transactions'] = count
    
    def update_api_stats(self, api_rate: float):
        """Update API statistics."""
        self.system_stats['api_success_rate'] = api_rate
    
    def update_system_status(self, status: str):
        """Update system status."""
        self.system_stats['system_status'] = status
    
    def add_log_entry(self, level: str, message: str):
        """Add a log entry."""
        log_entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'level': level,
            'message': message
        }
        
        self.logs.append(log_entry)
        
        # Keep only the last max_logs entries
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        # Emit log update via WebSocket
        if self.socketio:
            self.socketio.emit('log_update', log_entry)
    
    def get_current_stats(self) -> Dict:
        """Get current system statistics."""
        return self.system_stats.copy()

def main():
    """Main function for testing."""
    config = {
        'monitoring': {
            'enabled': True,
            'port': 5000,
            'host': 'localhost'
        }
    }
    
    monitor = EnhancedRealTimeMonitor(config)
    monitor.start_monitoring()

if __name__ == "__main__":
    main() 