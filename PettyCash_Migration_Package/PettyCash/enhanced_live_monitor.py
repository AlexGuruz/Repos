#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Live Monitor with Real-Time Script Logging
Provides detailed live monitoring of all Petty Cash operations
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import logging
import queue
import sys
from datetime import datetime
from pathlib import Path
import json

# Import monitoring systems
from petty_cash_monitor import PettyCashMonitor
from monitor_system import MonitorSystem
from petty_cash_sorter_optimized import PettyCashSorter

class EnhancedLiveMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Live Monitor - Petty Cash Operations")
        self.root.geometry('1200x800')
        self.root.configure(bg='#1a1a1a')
        
        # Initialize systems
        self.petty_cash_monitor = PettyCashMonitor()
        self.header_monitor = MonitorSystem()
        self.sorter = PettyCashSorter()
        
        # Threading
        self.log_queue = queue.Queue()
        self.monitoring = False
        self.monitor_thread = None
        
        # Build UI
        self._build_ui()
        
        # Start log processing
        self._process_log_queue()
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _build_ui(self):
        """Build the enhanced monitoring UI"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="🔍 Enhanced Live Monitor", 
                              font=("Segoe UI", 20, "bold"), 
                              fg="#00ff88", bg='#1a1a1a')
        title_label.pack(pady=(0, 10))
        
        # Control panel
        control_frame = tk.LabelFrame(main_frame, text="Controls", 
                                    font=("Segoe UI", 12, "bold"), 
                                    fg="#ffffff", bg='#1a1a1a')
        control_frame.pack(fill='x', pady=(0, 10))
        
        # Control buttons
        button_frame = tk.Frame(control_frame, bg='#1a1a1a')
        button_frame.pack(fill='x', padx=10, pady=10)
        
        self.start_btn = tk.Button(button_frame, text="🟢 Start Live Monitoring", 
                                 command=self._start_monitoring,
                                 bg='#00ff88', fg='#000000', font=("Segoe UI", 12, "bold"))
        self.start_btn.pack(side='left', padx=5)
        
        self.stop_btn = tk.Button(button_frame, text="🔴 Stop Monitoring", 
                                command=self._stop_monitoring,
                                bg='#ff4444', fg='#ffffff', font=("Segoe UI", 12, "bold"),
                                state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        self.clear_btn = tk.Button(button_frame, text="🗑️ Clear Log", 
                                 command=self._clear_log,
                                 bg='#ff8800', fg='#000000', font=("Segoe UI", 12))
        self.clear_btn.pack(side='left', padx=5)
        
        self.run_now_btn = tk.Button(button_frame, text="⚡ Run Petty Cash Now", 
                                   command=self._run_petty_cash_now,
                                   bg='#0088ff', fg='#ffffff', font=("Segoe UI", 12))
        self.run_now_btn.pack(side='left', padx=5)
        
        self.run_headers_btn = tk.Button(button_frame, text="📊 Run Headers Now", 
                                       command=self._run_headers_now,
                                       bg='#8800ff', fg='#ffffff', font=("Segoe UI", 12))
        self.run_headers_btn.pack(side='left', padx=5)
        
        # Status panel
        status_frame = tk.LabelFrame(main_frame, text="System Status", 
                                   font=("Segoe UI", 12, "bold"), 
                                   fg="#ffffff", bg='#1a1a1a')
        status_frame.pack(fill='x', pady=(0, 10))
        
        status_content = tk.Frame(status_frame, bg='#1a1a1a')
        status_content.pack(fill='x', padx=10, pady=10)
        
        # Status labels
        self.monitor_status = tk.StringVar(value="🟡 Ready")
        self.petty_cash_status = tk.StringVar(value="🟡 Ready")
        self.header_status = tk.StringVar(value="🟡 Ready")
        self.last_update = tk.StringVar(value="Never")
        
        tk.Label(status_content, text="Monitor:", font=("Segoe UI", 10), 
               fg="#ffffff", bg='#1a1a1a').grid(row=0, column=0, sticky='w', padx=(0, 10))
        tk.Label(status_content, textvariable=self.monitor_status, font=("Segoe UI", 10), 
               fg="#00ff88", bg='#1a1a1a').grid(row=0, column=1, sticky='w', padx=(0, 20))
        
        tk.Label(status_content, text="Petty Cash:", font=("Segoe UI", 10), 
               fg="#ffffff", bg='#1a1a1a').grid(row=0, column=2, sticky='w', padx=(0, 10))
        tk.Label(status_content, textvariable=self.petty_cash_status, font=("Segoe UI", 10), 
               fg="#00ccff", bg='#1a1a1a').grid(row=0, column=3, sticky='w', padx=(0, 20))
        
        tk.Label(status_content, text="Headers:", font=("Segoe UI", 10), 
               fg="#ffffff", bg='#1a1a1a').grid(row=0, column=4, sticky='w', padx=(0, 10))
        tk.Label(status_content, textvariable=self.header_status, font=("Segoe UI", 10), 
               fg="#ff88ff", bg='#1a1a1a').grid(row=0, column=5, sticky='w', padx=(0, 20))
        
        tk.Label(status_content, text="Last Update:", font=("Segoe UI", 10), 
               fg="#ffffff", bg='#1a1a1a').grid(row=0, column=6, sticky='w', padx=(0, 10))
        tk.Label(status_content, textvariable=self.last_update, font=("Segoe UI", 10), 
               fg="#ffff88", bg='#1a1a1a').grid(row=0, column=7, sticky='w')
        
        # Live log display
        log_frame = tk.LabelFrame(main_frame, text="Live Operation Log", 
                                font=("Segoe UI", 12, "bold"), 
                                fg="#ffffff", bg='#1a1a1a')
        log_frame.pack(fill='both', expand=True)
        
        # Log text area with scrollbar
        log_container = tk.Frame(log_frame, bg='#1a1a1a')
        log_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(
            log_container,
            font=("Consolas", 10),
            bg="#181818",
            fg="#00ff88",
            wrap='word',
            height=20
        )
        self.log_text.pack(fill='both', expand=True)
        
        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_cb = tk.Checkbutton(log_container, text="Auto-scroll to bottom", 
                                      variable=self.auto_scroll_var,
                                      font=("Segoe UI", 9), fg="#ffffff", bg='#1a1a1a',
                                      selectcolor='#1a1a1a')
        auto_scroll_cb.pack(anchor='w', pady=(5, 0))
    
    def _log_message(self, message, level="INFO"):
        """Add message to log queue"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}\n"
        self.log_queue.put(formatted_message)
    
    def _process_log_queue(self):
        """Process messages from log queue"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message)
                
                if self.auto_scroll_var.get():
                    self.log_text.see(tk.END)
                
                # Limit log size
                lines = self.log_text.get(1.0, tk.END).split('\n')
                if len(lines) > 1000:
                    self.log_text.delete(1.0, f"{len(lines) - 500}.0")
                    
        except queue.Empty:
            pass
        
        # Schedule next processing
        self.root.after(100, self._process_log_queue)
    
    def _start_monitoring(self):
        """Start live monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_status.set("🟢 Running")
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        self._log_message("🚀 Starting Enhanced Live Monitor...", "SYSTEM")
        self._log_message("📊 Monitoring Petty Cash transactions and header changes", "SYSTEM")
        self._log_message("⏱️ Check interval: 5 minutes", "SYSTEM")
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def _stop_monitoring(self):
        """Stop live monitoring"""
        self.monitoring = False
        self.monitor_status.set("🔴 Stopped")
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        
        self._log_message("🛑 Live monitoring stopped", "SYSTEM")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        cycle_count = 0
        
        while self.monitoring:
            cycle_count += 1
            cycle_start = datetime.now()
            
            self._log_message(f"🔄 Monitoring Cycle #{cycle_count}", "CYCLE")
            
            try:
                # Check petty cash
                self._log_message("🔍 Checking for new petty cash transactions...", "PETTY_CASH")
                result = self.petty_cash_monitor.run_single_check()
                
                if result['success']:
                    if result['processed_count'] > 0:
                        self.petty_cash_status.set(f"✅ {result['processed_count']} processed")
                        self._log_message(f"✅ Processed {result['processed_count']} transactions", "SUCCESS")
                    else:
                        self.petty_cash_status.set("✅ No new transactions")
                        self._log_message("✅ No new transactions found", "INFO")
                else:
                    self.petty_cash_status.set("❌ Error")
                    self._log_message(f"❌ Petty cash error: {result['message']}", "ERROR")
                
                # Check headers (less frequently)
                if cycle_count % 12 == 0:  # Every hour
                    self._log_message("📊 Checking for header changes...", "HEADERS")
                    try:
                        changes = self.header_monitor.run_monitoring_cycle()
                        if changes > 0:
                            self.header_status.set(f"✅ {changes} updates")
                            self._log_message(f"✅ Updated {changes} header dropdowns", "SUCCESS")
                        else:
                            self.header_status.set("✅ No changes")
                            self._log_message("✅ No header changes detected", "INFO")
                    except Exception as e:
                        self.header_status.set("❌ Error")
                        self._log_message(f"❌ Header error: {e}", "ERROR")
                
                # Update last update time
                self.last_update.set(datetime.now().strftime("%H:%M:%S"))
                
                # Calculate cycle time
                cycle_time = (datetime.now() - cycle_start).total_seconds()
                self._log_message(f"⏱️ Cycle completed in {cycle_time:.1f} seconds", "CYCLE")
                
                # Wait for next cycle (5 minutes)
                if self.monitoring:
                    self._log_message("⏳ Waiting 5 minutes until next check...", "CYCLE")
                    for i in range(300):  # 5 minutes in seconds
                        if not self.monitoring:
                            break
                        time.sleep(1)
                
            except Exception as e:
                self._log_message(f"❌ Fatal error in monitoring cycle: {e}", "ERROR")
                time.sleep(60)  # Wait 1 minute before retry
    
    def _run_petty_cash_now(self):
        """Run petty cash processing immediately"""
        self._log_message("⚡ Running petty cash processing now...", "MANUAL")
        
        def run_pc():
            try:
                result = self.petty_cash_monitor.run_single_check()
                if result['success']:
                    if result['processed_count'] > 0:
                        self._log_message(f"✅ Manual run completed: {result['processed_count']} transactions processed", "SUCCESS")
                    else:
                        self._log_message("✅ Manual run completed: No new transactions", "SUCCESS")
                else:
                    self._log_message(f"❌ Manual run failed: {result['message']}", "ERROR")
            except Exception as e:
                self._log_message(f"❌ Manual run error: {e}", "ERROR")
        
        threading.Thread(target=run_pc, daemon=True).start()
    
    def _run_headers_now(self):
        """Run header processing immediately"""
        self._log_message("📊 Running header processing now...", "MANUAL")
        
        def run_headers():
            try:
                changes = self.header_monitor.run_monitoring_cycle()
                if changes > 0:
                    self._log_message(f"✅ Manual header run: Updated {changes} dropdowns", "SUCCESS")
                else:
                    self._log_message("✅ Manual header run: No changes detected", "SUCCESS")
            except Exception as e:
                self._log_message(f"❌ Manual header run error: {e}", "ERROR")
        
        threading.Thread(target=run_headers, daemon=True).start()
    
    def _clear_log(self):
        """Clear the log display"""
        self.log_text.delete(1.0, tk.END)
        self._log_message("🗑️ Log cleared", "SYSTEM")
    
    def _on_closing(self):
        """Handle window closing"""
        self._stop_monitoring()
        self.root.destroy()

def main():
    """Main function"""
    root = tk.Tk()
    app = EnhancedLiveMonitor(root)
    root.mainloop()

if __name__ == "__main__":
    main() 