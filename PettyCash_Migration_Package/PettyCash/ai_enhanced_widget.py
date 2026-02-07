#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-Enhanced Desktop Widget with Ollama Integration
Combines petty cash monitoring with AI-powered analysis
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime, timedelta
from monitor_system import MonitorSystem
from petty_cash_monitor import PettyCashMonitor
from ai_observer_system import AIObserverSystem
import logging
import os
import sys
from PIL import Image, ImageTk, ImageDraw
import json

# Configuration
CONFIG_FILE = 'config/ai_widget_config.json'
DEFAULT_HEADER_INTERVAL_HOURS = 12
DEFAULT_PETTY_CASH_INTERVAL_MINUTES = 5
DEFAULT_AI_OBSERVATION_INTERVAL_SECONDS = 30

class AIEnhancedWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("AI-Enhanced JGD Systems Monitor")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)
        self.root.geometry('1400x1000')
        self.root.configure(bg='#1a1a1a')
        
        # Force window to front
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize systems
        self.header_monitor = MonitorSystem()
        self.petty_cash_monitor = PettyCashMonitor()
        self.ai_observer = AIObserverSystem()
        
        # Thread safety
        self._lock = threading.Lock()
        
        # System states
        self._header_running = False
        self._petty_cash_running = False
        self._ai_observer_running = False
        
        # Status variables
        self.header_status = tk.StringVar(value="Ready")
        self.petty_cash_status = tk.StringVar(value="Ready")
        self.ai_status = tk.StringVar(value="Ready")
        
        # Build UI
        self._build_ui()
        self._start_systems()
        self._update_ui()
        
        # Bind events
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _load_config(self):
        """Load configuration from file"""
        default_config = {
            'header_interval_hours': DEFAULT_HEADER_INTERVAL_HOURS,
            'petty_cash_interval_minutes': DEFAULT_PETTY_CASH_INTERVAL_MINUTES,
            'ai_observation_interval_seconds': DEFAULT_AI_OBSERVATION_INTERVAL_SECONDS,
            'header_enabled': True,
            'petty_cash_enabled': True,
            'ai_observer_enabled': True,
            'ollama_model': 'llama3.2'
        }
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            else:
                self._save_config(default_config)
                return default_config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _build_ui(self):
        """Build the AI-enhanced UI"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="🤖 AI-Enhanced JGD Systems Monitor", 
                              font=("Segoe UI", 24, "bold"), 
                              fg="#00ff88", bg='#1a1a1a')
        title_label.pack(pady=(0, 20))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Build tabs
        self._build_monitoring_tab()
        self._build_ai_analysis_tab()
        self._build_settings_tab()
    
    def _build_monitoring_tab(self):
        """Build the monitoring tab"""
        monitoring_frame = tk.Frame(self.notebook, bg='#1a1a1a')
        self.notebook.add(monitoring_frame, text="📊 Monitoring")
        
        # Header Monitor Section
        header_frame = tk.LabelFrame(monitoring_frame, text="Header Monitor", 
                                   font=("Segoe UI", 12, "bold"), fg="#00ff88", bg='#1a1a1a')
        header_frame.pack(fill='x', padx=10, pady=5)
        
        # Header controls
        header_controls = tk.Frame(header_frame, bg='#1a1a1a')
        header_controls.pack(fill='x', padx=10, pady=5)
        
        self.header_status_label = tk.Label(header_controls, textvariable=self.header_status,
                                          font=("Segoe UI", 10), fg="#00ff88", bg='#1a1a1a')
        self.header_status_label.pack(side='left')
        
        self.header_run_btn = tk.Button(header_controls, text="🔄 Run Now", 
                                      command=self._run_header_now,
                                      bg='#00ff88', fg='#000000', font=("Segoe UI", 10))
        self.header_run_btn.pack(side='right', padx=5)
        
        # Petty Cash Monitor Section
        petty_cash_frame = tk.LabelFrame(monitoring_frame, text="Petty Cash Monitor", 
                                       font=("Segoe UI", 12, "bold"), fg="#00ccff", bg='#1a1a1a')
        petty_cash_frame.pack(fill='x', padx=10, pady=5)
        
        # Petty cash controls
        pc_controls = tk.Frame(petty_cash_frame, bg='#1a1a1a')
        pc_controls.pack(fill='x', padx=10, pady=5)
        
        self.pc_status_label = tk.Label(pc_controls, textvariable=self.petty_cash_status,
                                      font=("Segoe UI", 10), fg="#00ccff", bg='#1a1a1a')
        self.pc_status_label.pack(side='left')
        
        self.pc_run_btn = tk.Button(pc_controls, text="🔄 Run Now", 
                                  command=self._run_petty_cash_now,
                                  bg='#00ccff', fg='#000000', font=("Segoe UI", 10))
        self.pc_run_btn.pack(side='right', padx=5)
        
        self.pc_force_btn = tk.Button(pc_controls, text="⚡ Force Process All", 
                                    command=self._force_process_all,
                                    bg='#ff8800', fg='#000000', font=("Segoe UI", 10))
        self.pc_force_btn.pack(side='right', padx=5)
    
    def _build_ai_analysis_tab(self):
        """Build the AI analysis tab"""
        ai_frame = tk.Frame(self.notebook, bg='#1a1a1a')
        self.notebook.add(ai_frame, text="🤖 AI Analysis")
        
        # AI Status Section
        ai_status_frame = tk.LabelFrame(ai_frame, text="AI Observer Status", 
                                      font=("Segoe UI", 12, "bold"), fg="#ff88ff", bg='#1a1a1a')
        ai_status_frame.pack(fill='x', padx=10, pady=5)
        
        # AI controls
        ai_controls = tk.Frame(ai_status_frame, bg='#1a1a1a')
        ai_controls.pack(fill='x', padx=10, pady=5)
        
        self.ai_status_label = tk.Label(ai_controls, textvariable=self.ai_status,
                                      font=("Segoe UI", 10), fg="#ff88ff", bg='#1a1a1a')
        self.ai_status_label.pack(side='left')
        
        self.ai_toggle_btn = tk.Button(ai_controls, text="🟢 Start AI Observer", 
                                     command=self._toggle_ai_observer,
                                     bg='#ff88ff', fg='#000000', font=("Segoe UI", 10))
        self.ai_toggle_btn.pack(side='right', padx=5)
        
        # AI Analysis Display
        analysis_frame = tk.LabelFrame(ai_frame, text="Latest AI Analysis", 
                                     font=("Segoe UI", 12, "bold"), fg="#ff88ff", bg='#1a1a1a')
        analysis_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Analysis text area
        self.analysis_text = tk.Text(analysis_frame, height=20, width=80,
                                   font=("Consolas", 10), bg="#181818", fg="#ff88ff",
                                   wrap='word', state='disabled')
        self.analysis_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Analysis controls
        analysis_controls = tk.Frame(analysis_frame, bg='#1a1a1a')
        analysis_controls.pack(fill='x', padx=10, pady=5)
        
        self.refresh_analysis_btn = tk.Button(analysis_controls, text="🔄 Refresh Analysis", 
                                            command=self._refresh_ai_analysis,
                                            bg='#ff88ff', fg='#000000', font=("Segoe UI", 10))
        self.refresh_analysis_btn.pack(side='left')
        
        self.generate_report_btn = tk.Button(analysis_controls, text="📊 Generate Report", 
                                           command=self._generate_ai_report,
                                           bg='#ff88ff', fg='#000000', font=("Segoe UI", 10))
        self.generate_report_btn.pack(side='left', padx=5)
    
    def _build_settings_tab(self):
        """Build the settings tab"""
        settings_frame = tk.Frame(self.notebook, bg='#1a1a1a')
        self.notebook.add(settings_frame, text="⚙️ Settings")
        
        # Settings content
        settings_content = tk.Frame(settings_frame, bg='#1a1a1a')
        settings_content.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Intervals section
        intervals_frame = tk.LabelFrame(settings_content, text="Monitoring Intervals", 
                                      font=("Segoe UI", 12, "bold"), fg="#ffffff", bg='#1a1a1a')
        intervals_frame.pack(fill='x', pady=10)
        
        # Header interval
        header_interval_frame = tk.Frame(intervals_frame, bg='#1a1a1a')
        header_interval_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(header_interval_frame, text="Header Monitor (hours):", 
               font=("Segoe UI", 10), fg="#ffffff", bg='#1a1a1a').pack(side='left')
        
        self.header_interval_var = tk.StringVar(value=str(self.config.get('header_interval_hours', 12)))
        header_interval_entry = tk.Entry(header_interval_frame, textvariable=self.header_interval_var,
                                       font=("Segoe UI", 10), width=10)
        header_interval_entry.pack(side='right')
        
        # Petty cash interval
        pc_interval_frame = tk.Frame(intervals_frame, bg='#1a1a1a')
        pc_interval_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(pc_interval_frame, text="Petty Cash Monitor (minutes):", 
               font=("Segoe UI", 10), fg="#ffffff", bg='#1a1a1a').pack(side='left')
        
        self.pc_interval_var = tk.StringVar(value=str(self.config.get('petty_cash_interval_minutes', 5)))
        pc_interval_entry = tk.Entry(pc_interval_frame, textvariable=self.pc_interval_var,
                                   font=("Segoe UI", 10), width=10)
        pc_interval_entry.pack(side='right')
        
        # AI interval
        ai_interval_frame = tk.Frame(intervals_frame, bg='#1a1a1a')
        ai_interval_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(ai_interval_frame, text="AI Observer (seconds):", 
               font=("Segoe UI", 10), fg="#ffffff", bg='#1a1a1a').pack(side='left')
        
        self.ai_interval_var = tk.StringVar(value=str(self.config.get('ai_observation_interval_seconds', 30)))
        ai_interval_entry = tk.Entry(ai_interval_frame, textvariable=self.ai_interval_var,
                                   font=("Segoe UI", 10), width=10)
        ai_interval_entry.pack(side='right')
        
        # Save button
        save_btn = tk.Button(settings_content, text="💾 Save Settings", 
                           command=self._save_settings,
                           bg='#00ff88', fg='#000000', font=("Segoe UI", 12, "bold"))
        save_btn.pack(pady=20)
    
    def _start_systems(self):
        """Start the monitoring systems"""
        # Start AI observer if enabled
        if self.config.get('ai_observer_enabled', True):
            self._start_ai_observer()
    
    def _start_ai_observer(self):
        """Start the AI observer"""
        try:
            self.ai_observer.start_observing()
            self._ai_observer_running = True
            self.ai_status.set("Running")
            self.ai_toggle_btn.config(text="🔴 Stop AI Observer", bg='#ff4444')
        except Exception as e:
            logging.error(f"Error starting AI observer: {e}")
            self.ai_status.set("Error")
    
    def _stop_ai_observer(self):
        """Stop the AI observer"""
        try:
            self.ai_observer.stop_observing()
            self._ai_observer_running = False
            self.ai_status.set("Stopped")
            self.ai_toggle_btn.config(text="🟢 Start AI Observer", bg='#ff88ff')
        except Exception as e:
            logging.error(f"Error stopping AI observer: {e}")
    
    def _toggle_ai_observer(self):
        """Toggle AI observer on/off"""
        if self._ai_observer_running:
            self._stop_ai_observer()
        else:
            self._start_ai_observer()
    
    def _run_header_now(self):
        """Run header monitor now"""
        if self._header_running:
            return
        
        self._header_running = True
        self.header_status.set("Running...")
        
        def run_header():
            try:
                changes = self.header_monitor.run_monitoring_cycle()
                self.header_status.set(f"Updated {changes} dropdowns")
            except Exception as e:
                self.header_status.set("Error")
                logging.error(f"Header monitor error: {e}")
            finally:
                self._header_running = False
        
        threading.Thread(target=run_header, daemon=True).start()
    
    def _run_petty_cash_now(self):
        """Run petty cash monitor now"""
        if self._petty_cash_running:
            return
        
        self._petty_cash_running = True
        self.petty_cash_status.set("Running...")
        
        def run_pc():
            try:
                result = self.petty_cash_monitor.run_single_check()
                if result['success']:
                    self.petty_cash_status.set(f"Processed {result['processed_count']} transactions")
                else:
                    self.petty_cash_status.set("Error")
            except Exception as e:
                self.petty_cash_status.set("Error")
                logging.error(f"Petty cash monitor error: {e}")
            finally:
                self._petty_cash_running = False
        
        threading.Thread(target=run_pc, daemon=True).start()
    
    def _force_process_all(self):
        """Force process all transactions"""
        if messagebox.askyesno("Force Process All", 
                              "This will process ALL transactions in the PETTY CASH sheet.\n\n"
                              "This may take several minutes and will use API quota.\n\n"
                              "Continue?"):
            self._run_petty_cash_now()
    
    def _refresh_ai_analysis(self):
        """Refresh the AI analysis display"""
        try:
            latest_analysis = self.ai_observer.get_latest_analysis()
            if latest_analysis:
                analysis = latest_analysis['analysis']
                metrics = latest_analysis['metrics']
                
                # Format the analysis for display
                display_text = f"""
🤖 AI ANALYSIS REPORT
{'='*50}

📊 SYSTEM METRICS:
• Recent Transactions: {metrics.get('recent_transactions', 0)}
• Recent Errors: {metrics.get('recent_errors', 0)}
• Cache Hit Rate: {metrics.get('cache_hit_rate', 0):.1f}%
• System Health Score: {metrics.get('system_health_score', 100)}/100
• Service Account Valid: {metrics.get('service_account_valid', False)}
• API Connectivity: {metrics.get('api_connectivity', False)}

🔍 AI ANALYSIS:
• Summary: {analysis.get('summary', 'No analysis available')}
• Alert Level: {analysis.get('alert_level', 'normal').upper()}

💡 INSIGHTS:
"""
                
                for insight in analysis.get('insights', []):
                    display_text += f"• {insight}\n"
                
                display_text += "\n📋 RECOMMENDATIONS:\n"
                for rec in analysis.get('recommendations', []):
                    display_text += f"• {rec}\n"
                
                display_text += "\n👀 WATCH ITEMS:\n"
                for item in analysis.get('watch_items', []):
                    display_text += f"• {item}\n"
                
                # Update display
                self.analysis_text.config(state='normal')
                self.analysis_text.delete(1.0, tk.END)
                self.analysis_text.insert(tk.END, display_text)
                self.analysis_text.config(state='disabled')
            else:
                self.analysis_text.config(state='normal')
                self.analysis_text.delete(1.0, tk.END)
                self.analysis_text.insert(tk.END, "No AI analysis available yet.\n\nStart the AI Observer to begin monitoring.")
                self.analysis_text.config(state='disabled')
                
        except Exception as e:
            logging.error(f"Error refreshing AI analysis: {e}")
            self.analysis_text.config(state='normal')
            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(tk.END, f"Error refreshing analysis: {e}")
            self.analysis_text.config(state='disabled')
    
    def _generate_ai_report(self):
        """Generate a comprehensive AI report"""
        try:
            report = self.ai_observer.generate_report(hours=24)
            
            if 'error' in report:
                messagebox.showerror("Report Error", f"Error generating report: {report['error']}")
                return
            
            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title("AI Analysis Report - Last 24 Hours")
            report_window.geometry("800x600")
            report_window.configure(bg='#1a1a1a')
            
            # Report text
            report_text = tk.Text(report_window, font=("Consolas", 10), 
                                bg="#181818", fg="#ffffff", wrap='word')
            report_text.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Format report
            report_display = f"""
🤖 AI ANALYSIS REPORT - LAST 24 HOURS
{'='*60}

📊 SUMMARY:
• Total Analyses: {report['total_analyses']}
• Critical Alerts: {report['critical_alerts']}
• Warning Alerts: {report['warning_alerts']}
• Normal Periods: {report['normal_periods']}

📈 TRENDS:
• Health Score Trend: {report['trends'].get('health_score_trend', 'N/A')}
• Error Rate Trend: {report['trends'].get('error_rate_trend', 'N/A')}
• Average Health Score: {report['trends'].get('average_health_score', 0):.1f}
• Average Error Rate: {report['trends'].get('average_error_rate', 0):.1f}%

💡 TOP RECOMMENDATIONS:
"""
            
            for i, rec in enumerate(report['recommendations'][:5], 1):
                report_display += f"{i}. {rec}\n"
            
            report_text.insert(tk.END, report_display)
            report_text.config(state='disabled')
            
        except Exception as e:
            logging.error(f"Error generating AI report: {e}")
            messagebox.showerror("Report Error", f"Error generating report: {e}")
    
    def _save_settings(self):
        """Save current settings"""
        try:
            # Update config with current values
            self.config['header_interval_hours'] = int(self.header_interval_var.get())
            self.config['petty_cash_interval_minutes'] = int(self.pc_interval_var.get())
            self.config['ai_observation_interval_seconds'] = int(self.ai_interval_var.get())
            
            # Save to file
            self._save_config(self.config)
            
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully!")
            
        except ValueError as e:
            messagebox.showerror("Invalid Settings", "Please enter valid numbers for intervals.")
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving settings: {e}")
    
    def _update_ui(self):
        """Update the UI periodically"""
        try:
            # Update AI analysis if observer is running
            if self._ai_observer_running:
                self._refresh_ai_analysis()
            
            # Schedule next update
            self.root.after(30000, self._update_ui)  # Update every 30 seconds
            
        except Exception as e:
            logging.error(f"Error updating UI: {e}")
    
    def _on_closing(self):
        """Handle window closing"""
        try:
            # Stop AI observer
            if self._ai_observer_running:
                self._stop_ai_observer()
            
            # Close window
            self.root.destroy()
            
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
            self.root.destroy()

def main():
    """Main function"""
    root = tk.Tk()
    app = AIEnhancedWidget(root)
    root.mainloop()

if __name__ == "__main__":
    main() 