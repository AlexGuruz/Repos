#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Desktop Widget for JGD Systems
- Header Monitor + Petty Cash Monitor
- Separate tracking and configurable timing
- Modern GUI with dark theme
- System tray integration
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime, timedelta
from monitor_system import MonitorSystem
from petty_cash_monitor import PettyCashMonitor
import logging
import os
import sys
from PIL import Image, ImageTk, ImageDraw
import base64
import json

# Default intervals
DEFAULT_HEADER_INTERVAL_HOURS = 12
DEFAULT_PETTY_CASH_INTERVAL_MINUTES = 5

# Configuration file
CONFIG_FILE = 'config/widget_config.json'

class EnhancedMonitorWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("JGD Systems Monitor")
        self.root.attributes('-topmost', True)
        self.root.resizable(True, True)  # Allow resizing
        self.root.geometry('1200x900')  # Much larger default size
        self.root.configure(bg='#1a1a1a')
        
        # Force window to front and make it visible
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)
        
        # Set window icon
        self._create_icon()
        
        # Center window on screen
        self._center_window()
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize systems
        self.header_monitor = MonitorSystem()
        self.petty_cash_monitor = PettyCashMonitor()
        
        # Thread safety
        self._lock = threading.Lock()
        
        # System states (thread-safe access)
        self._header_running = False
        self._petty_cash_running = False
        self._header_last_run = None
        self._petty_cash_last_run = None
        self._header_next_run = None
        self._petty_cash_next_run = None
        
        # Status variables
        self.header_status = tk.StringVar(value="Ready")
        self.petty_cash_status = tk.StringVar(value="Ready")
        self.header_status_color = "#00ff88"
        self.petty_cash_status_color = "#00ff88"
        
        # Log lines for each monitor (thread-safe access)
        self._header_log_lines = []
        self._petty_cash_log_lines = []
        self.minimized_to_tray = False
        
        # Create system tray icon
        self._setup_system_tray()
        
        # Build UI
        self._build_ui()
        self._schedule_runs()
        self._update_ui()
        
        # Bind window events
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.bind('<Escape>', self._minimize_to_tray)
    
    # Thread-safe property getters and setters
    @property
    def header_running(self):
        with self._lock:
            return self._header_running
    
    @header_running.setter
    def header_running(self, value):
        with self._lock:
            self._header_running = value
    
    @property
    def petty_cash_running(self):
        with self._lock:
            return self._petty_cash_running
    
    @petty_cash_running.setter
    def petty_cash_running(self, value):
        with self._lock:
            self._petty_cash_running = value
    
    @property
    def header_last_run(self):
        with self._lock:
            return self._header_last_run
    
    @header_last_run.setter
    def header_last_run(self, value):
        with self._lock:
            self._header_last_run = value
    
    @property
    def petty_cash_last_run(self):
        with self._lock:
            return self._petty_cash_last_run
    
    @petty_cash_last_run.setter
    def petty_cash_last_run(self, value):
        with self._lock:
            self._petty_cash_last_run = value
    
    @property
    def header_next_run(self):
        with self._lock:
            return self._header_next_run
    
    @header_next_run.setter
    def header_next_run(self, value):
        with self._lock:
            self._header_next_run = value
    
    @property
    def petty_cash_next_run(self):
        with self._lock:
            return self._petty_cash_next_run
    
    @petty_cash_next_run.setter
    def petty_cash_next_run(self, value):
        with self._lock:
            self._petty_cash_next_run = value
    
    def _load_config(self):
        """Load configuration from file"""
        default_config = {
            'header_interval_hours': DEFAULT_HEADER_INTERVAL_HOURS,
            'petty_cash_interval_minutes': DEFAULT_PETTY_CASH_INTERVAL_MINUTES,
            'header_enabled': True,
            'petty_cash_enabled': True
        }
        
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    
                    # Validate configuration
                    self._validate_config(config)
                    return config
            else:
                # Create default config file
                self._save_config(default_config)
                return default_config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    
    def _validate_config(self, config):
        """Validate configuration values."""
        try:
            # Validate intervals
            if not isinstance(config.get('header_interval_hours'), (int, float)) or config['header_interval_hours'] <= 0:
                config['header_interval_hours'] = DEFAULT_HEADER_INTERVAL_HOURS
                print(f"Invalid header_interval_hours, using default: {DEFAULT_HEADER_INTERVAL_HOURS}")
            
            if not isinstance(config.get('petty_cash_interval_minutes'), (int, float)) or config['petty_cash_interval_minutes'] <= 0:
                config['petty_cash_interval_minutes'] = DEFAULT_PETTY_CASH_INTERVAL_MINUTES
                print(f"Invalid petty_cash_interval_minutes, using default: {DEFAULT_PETTY_CASH_INTERVAL_MINUTES}")
            
            # Validate boolean flags
            if not isinstance(config.get('header_enabled'), bool):
                config['header_enabled'] = True
                print("Invalid header_enabled, using default: True")
            
            if not isinstance(config.get('petty_cash_enabled'), bool):
                config['petty_cash_enabled'] = True
                print("Invalid petty_cash_enabled, using default: True")
            
            # Save corrected config
            self._save_config(config)
            
        except Exception as e:
            print(f"Error validating config: {e}")
            # Return to defaults if validation fails
            return self._load_config()
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _create_icon(self):
        """Create a simple icon for the application"""
        try:
            icon_size = 32
            img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw a dual monitor icon
            draw.rectangle([4, 4, 14, 20], fill='#00ff88', outline='#ffffff', width=2)
            draw.rectangle([18, 4, 28, 20], fill='#00ccff', outline='#ffffff', width=2)
            draw.rectangle([12, 20, 20, 24], fill='#00ff88', outline='#ffffff', width=1)
            draw.ellipse([8, 8, 12, 12], fill='#ffffff')
            draw.ellipse([22, 8, 26, 12], fill='#ffffff')
            
            self.icon_image = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, self.icon_image)
        except Exception as e:
            print(f"Could not create icon: {e}")
    
    def _center_window(self):
        """Center the window on the screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _setup_system_tray(self):
        """Setup system tray icon (placeholder for now)"""
        pass
    
    def _build_ui(self):
        """Build the enhanced UI with both monitors"""
        # Main container with grid layout
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Configure grid weights
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=0)  # Title
        main_frame.grid_rowconfigure(1, weight=0)  # Controls
        main_frame.grid_rowconfigure(2, weight=1)  # Logs
        
        # Title (spans both columns)
        title_label = tk.Label(main_frame, text="JGD Systems Monitor", 
                              font=("Segoe UI", 20, "bold"), 
                              fg="#00ff88", bg='#1a1a1a')
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Controls frame (spans both columns)
        controls_frame = tk.Frame(main_frame, bg='#1a1a1a')
        controls_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 20))
        
        # Header Monitor Section (left side)
        self._build_header_section(controls_frame)
        
        # Petty Cash Monitor Section (right side)
        self._build_petty_cash_section(controls_frame)
        
        # Settings Section (centered)
        self._build_settings_section(controls_frame)
        
        # Logs frame (spans both columns, takes remaining space)
        logs_frame = tk.Frame(main_frame, bg='#1a1a2a')
        logs_frame.grid(row=2, column=0, columnspan=2, sticky='nsew', pady=(10, 0))
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_columnconfigure(1, weight=1)
        logs_frame.grid_rowconfigure(0, weight=1)
        
        # Build the log section
        self._build_log_section(logs_frame)
    
    def _build_header_section(self, parent):
        """Build header monitor section"""
        # Header Monitor Frame
        header_frame = tk.LabelFrame(parent, text="📊 Header Monitor", 
                                   font=("Segoe UI", 12, "bold"),
                                   fg="#00ff88", bg='#2a2a2a', relief='raised', bd=1)
        header_frame.grid(row=0, column=0, sticky='ew', padx=(0, 10), pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        
        # Status
        self.header_status_label = tk.Label(header_frame, textvariable=self.header_status, 
                                           font=("Segoe UI", 12, "bold"), 
                                           fg=self.header_status_color, bg='#2a2a2a', pady=5)
        self.header_status_label.pack()
        
        # Info
        self.header_last_run_label = tk.Label(header_frame, text="Last Run: Never", 
                                             font=("Segoe UI", 9), fg="#cccccc", 
                                             bg='#2a2a2a', anchor='w', padx=10)
        self.header_last_run_label.pack(fill='x')
        
        self.header_next_run_label = tk.Label(header_frame, text="Next Run: -", 
                                             font=("Segoe UI", 9), fg="#cccccc", 
                                             bg='#2a2a2a', anchor='w', padx=10)
        self.header_next_run_label.pack(fill='x')
        
        # Buttons
        header_btn_frame = tk.Frame(header_frame, bg='#2a2a2a')
        header_btn_frame.pack(fill='x', padx=10, pady=10)
        
        self.header_run_btn = tk.Button(header_btn_frame, text="🔄 Run Header Monitor", 
                                       command=self.run_header_now,
                                       font=("Segoe UI", 10, "bold"),
                                       bg='#00ff88', fg='#000000',
                                       activebackground='#00cc66',
                                       activeforeground='#000000',
                                       relief='flat', padx=15, pady=5,
                                       cursor='hand2')
        self.header_run_btn.pack(side='left', padx=(0, 10))
        
        self.header_toggle_btn = tk.Button(header_btn_frame, text="⏸️ Pause", 
                                          command=self.toggle_header_monitor,
                                          font=("Segoe UI", 10, "bold"),
                                          bg='#ff8800', fg='#000000',
                                          activebackground='#cc6600',
                                          activeforeground='#000000',
                                          relief='flat', padx=15, pady=5,
                                          cursor='hand2')
        self.header_toggle_btn.pack(side='left')
    
    def _build_petty_cash_section(self, parent):
        """Build petty cash monitor section"""
        # Petty Cash Monitor Frame
        petty_cash_frame = tk.LabelFrame(parent, text="💰 Petty Cash Monitor", 
                                        font=("Segoe UI", 12, "bold"),
                                        fg="#00ccff", bg='#2a2a2a', relief='raised', bd=1)
        petty_cash_frame.grid(row=0, column=1, sticky='ew', padx=(10, 0), pady=(0, 10))
        petty_cash_frame.grid_columnconfigure(0, weight=1)
        
        # Status
        self.petty_cash_status_label = tk.Label(petty_cash_frame, textvariable=self.petty_cash_status, 
                                               font=("Segoe UI", 12, "bold"), 
                                               fg=self.petty_cash_status_color, bg='#2a2a2a', pady=5)
        self.petty_cash_status_label.pack()
        
        # Info
        self.petty_cash_last_run_label = tk.Label(petty_cash_frame, text="Last Run: Never", 
                                                 font=("Segoe UI", 9), fg="#cccccc", 
                                                 bg='#2a2a2a', anchor='w', padx=10)
        self.petty_cash_last_run_label.pack(fill='x')
        
        self.petty_cash_next_run_label = tk.Label(petty_cash_frame, text="Next Run: -", 
                                                 font=("Segoe UI", 9), fg="#cccccc", 
                                                 bg='#2a2a2a', anchor='w', padx=10)
        self.petty_cash_next_run_label.pack(fill='x')
        
        # Buttons
        petty_cash_btn_frame = tk.Frame(petty_cash_frame, bg='#2a2a2a')
        petty_cash_btn_frame.pack(fill='x', padx=10, pady=10)
        
        self.petty_cash_run_btn = tk.Button(petty_cash_btn_frame, text="💰 Run Petty Cash Monitor", 
                                           command=self.run_petty_cash_now,
                                           font=("Segoe UI", 10, "bold"),
                                           bg='#00ccff', fg='#000000',
                                           activebackground='#0099cc',
                                           activeforeground='#000000',
                                           relief='flat', padx=15, pady=5,
                                           cursor='hand2')
        self.petty_cash_run_btn.pack(side='left', padx=(0, 10))
        
        self.petty_cash_toggle_btn = tk.Button(petty_cash_btn_frame, text="⏸️ Pause", 
                                              command=self.toggle_petty_cash_monitor,
                                              font=("Segoe UI", 10, "bold"),
                                              bg='#ff8800', fg='#000000',
                                              activebackground='#cc6600',
                                              activeforeground='#000000',
                                              relief='flat', padx=15, pady=5,
                                              cursor='hand2')
        self.petty_cash_toggle_btn.pack(side='left', padx=(0, 10))
        
        self.petty_cash_force_btn = tk.Button(petty_cash_btn_frame, text="🚀 Force Process All", 
                                             command=self.force_process_all_transactions,
                                             font=("Segoe UI", 10, "bold"),
                                             bg='#ff4444', fg='#ffffff',
                                             activebackground='#cc3333',
                                             activeforeground='#ffffff',
                                             relief='flat', padx=15, pady=5,
                                             cursor='hand2')
        self.petty_cash_force_btn.pack(side='left')
    
    def _build_settings_section(self, parent):
        """Build settings section"""
        # Settings Frame
        settings_frame = tk.LabelFrame(parent, text="⚙️ Settings", 
                                      font=("Segoe UI", 12, "bold"),
                                      fg="#ffffff", bg='#2a2a2a', relief='raised', bd=1)
        settings_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        settings_frame.grid_columnconfigure(0, weight=1)
        settings_frame.grid_columnconfigure(1, weight=1)
        
        # Header Monitor Settings (left)
        header_settings_frame = tk.Frame(settings_frame, bg='#2a2a2a')
        header_settings_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        
        header_interval_label = tk.Label(header_settings_frame, text="Header Monitor Interval (hours):", 
                                        font=("Segoe UI", 10), fg="#cccccc", bg='#2a2a2a')
        header_interval_label.pack(anchor='w')
        
        self.header_interval_var = tk.StringVar(value=str(self.config['header_interval_hours']))
        header_interval_entry = tk.Entry(header_settings_frame, textvariable=self.header_interval_var, 
                                        font=("Segoe UI", 10), bg='#444444', fg='#ffffff', 
                                        relief='flat', width=10)
        header_interval_entry.pack(anchor='w', pady=(5, 0))
        
        # Petty Cash Monitor Settings (right)
        petty_cash_settings_frame = tk.Frame(settings_frame, bg='#2a2a2a')
        petty_cash_settings_frame.grid(row=0, column=1, sticky='ew', padx=10, pady=10)
        
        petty_cash_interval_label = tk.Label(petty_cash_settings_frame, text="Petty Cash Monitor Interval (minutes):", 
                                            font=("Segoe UI", 10), fg="#cccccc", bg='#2a2a2a')
        petty_cash_interval_label.pack(anchor='w')
        
        self.petty_cash_interval_var = tk.StringVar(value=str(self.config['petty_cash_interval_minutes']))
        petty_cash_interval_entry = tk.Entry(petty_cash_settings_frame, textvariable=self.petty_cash_interval_var, 
                                            font=("Segoe UI", 10), bg='#444444', fg='#ffffff', 
                                            relief='flat', width=10)
        petty_cash_interval_entry.pack(anchor='w', pady=(5, 0))
        
        # Save Settings Button (centered)
        save_btn = tk.Button(settings_frame, text="💾 Save Settings", 
                            command=self.save_settings,
                            font=("Segoe UI", 10, "bold"),
                            bg='#666666', fg='#ffffff',
                            activebackground='#888888',
                            activeforeground='#ffffff',
                            relief='flat', padx=20, pady=5,
                            cursor='hand2')
        save_btn.grid(row=1, column=0, columnspan=2, pady=(0, 10))
    
    def _build_log_section(self, parent):
        """Build log section with side-by-side monitors"""
        # Left side - Header Monitor Log
        header_log_frame = tk.LabelFrame(parent, text="📊 Header Monitor Activity", 
                                        font=("Segoe UI", 12, "bold"),
                                        fg="#00ff88", bg='#2a2a2a', relief='raised', bd=1)
        header_log_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        header_log_frame.grid_columnconfigure(0, weight=1)
        header_log_frame.grid_rowconfigure(0, weight=1)
        
        self.header_log_box = tk.Text(header_log_frame, 
                                     font=("Consolas", 10), bg="#181818", fg="#00ff88", 
                                     state='disabled', wrap='word', relief='flat',
                                     insertbackground='#00ff88')
        self.header_log_box.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        header_scrollbar = tk.Scrollbar(header_log_frame, orient='vertical', command=self.header_log_box.yview)
        header_scrollbar.grid(row=0, column=1, sticky='ns')
        self.header_log_box.config(yscrollcommand=header_scrollbar.set)
        
        # Right side - Petty Cash Monitor Log
        petty_cash_log_frame = tk.LabelFrame(parent, text="💰 Petty Cash Monitor Activity", 
                                            font=("Segoe UI", 12, "bold"),
                                            fg="#00ccff", bg='#2a2a2a', relief='raised', bd=1)
        petty_cash_log_frame.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        petty_cash_log_frame.grid_columnconfigure(0, weight=1)
        petty_cash_log_frame.grid_rowconfigure(0, weight=1)
        
        self.petty_cash_log_box = tk.Text(petty_cash_log_frame, 
                                         font=("Consolas", 10), bg="#181818", fg="#00ccff", 
                                         state='disabled', wrap='word', relief='flat',
                                         insertbackground='#00ccff')
        self.petty_cash_log_box.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        petty_cash_scrollbar = tk.Scrollbar(petty_cash_log_frame, orient='vertical', command=self.petty_cash_log_box.yview)
        petty_cash_scrollbar.grid(row=0, column=1, sticky='ns')
        self.petty_cash_log_box.config(yscrollcommand=petty_cash_scrollbar.set)
        
        # Button frame at bottom
        log_btn_frame = tk.Frame(parent, bg='#2a2a2a')
        log_btn_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        
        # Clear buttons
        clear_header_btn = tk.Button(log_btn_frame, text="🗑️ Clear Header Log", 
                                    command=self.clear_header_log,
                                    font=("Segoe UI", 9),
                                    bg='#666666', fg='#ffffff',
                                    activebackground='#888888',
                                    activeforeground='#ffffff',
                                    relief='flat', padx=10, pady=2,
                                    cursor='hand2')
        clear_header_btn.pack(side='left', padx=(0, 5))
        
        clear_petty_cash_btn = tk.Button(log_btn_frame, text="🗑️ Clear Petty Cash Log", 
                                        command=self.clear_petty_cash_log,
                                        font=("Segoe UI", 9),
                                        bg='#666666', fg='#ffffff',
                                        activebackground='#888888',
                                        activeforeground='#ffffff',
                                        relief='flat', padx=10, pady=2,
                                        cursor='hand2')
        clear_petty_cash_btn.pack(side='left')
        
        # Footer info
        footer_label = tk.Label(log_btn_frame, text="Press ESC to minimize • Both systems independently tracked", 
                               font=("Segoe UI", 8), fg="#666666", bg='#2a2a2a')
        footer_label.pack(side='right')
    
    def save_settings(self):
        """Save current settings"""
        try:
            # Update config with current values
            self.config['header_interval_hours'] = int(self.header_interval_var.get())
            self.config['petty_cash_interval_minutes'] = int(self.petty_cash_interval_var.get())
            
            # Save to file
            self._save_config(self.config)
            
            # Reschedule runs with new intervals immediately
            if self.header_running:
                self._schedule_header_run()
            if self.petty_cash_running:
                self._schedule_petty_cash_run()
            
            self._log_header(f"Header monitor interval: {self.config['header_interval_hours']} hours")
            self._log_petty_cash(f"Petty cash monitor interval: {self.config['petty_cash_interval_minutes']} minutes")
            messagebox.showinfo("Settings", "Settings saved successfully!")
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for intervals!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def clear_header_log(self):
        """Clear the header monitor log"""
        with self._lock:
            self._header_log_lines = []
        self.header_log_box.config(state='normal')
        self.header_log_box.delete(1.0, tk.END)
        self.header_log_box.config(state='disabled')
        self._log_header("Header log cleared")
    
    def clear_petty_cash_log(self):
        """Clear the petty cash monitor log"""
        with self._lock:
            self._petty_cash_log_lines = []
        self.petty_cash_log_box.config(state='normal')
        self.petty_cash_log_box.delete(1.0, tk.END)
        self.petty_cash_log_box.config(state='disabled')
        self._log_petty_cash("Petty cash log cleared")
    
    def toggle_header_monitor(self):
        """Toggle header monitor on/off"""
        if self.header_running:
            self.header_running = False
            self.header_toggle_btn.config(text="▶️ Start", bg='#00ff88', fg='#000000')
            self.header_status.set("Paused")
            self.header_status_color = "#ff8800"
            self._log_header("Header monitor paused")
        else:
            self.header_running = True
            self.header_toggle_btn.config(text="⏸️ Pause", bg='#ff8800', fg='#000000')
            self.header_status.set("Running")
            self.header_status_color = "#00ff88"
            self._schedule_header_run()
            self._log_header("Header monitor started")
        
        self._update_header_status()
    
    def toggle_petty_cash_monitor(self):
        """Toggle petty cash monitor on/off"""
        if self.petty_cash_running:
            self.petty_cash_running = False
            self.petty_cash_toggle_btn.config(text="▶️ Start", bg='#00ccff', fg='#000000')
            self.petty_cash_status.set("Paused")
            self.petty_cash_status_color = "#ff8800"
            self._log_petty_cash("Petty cash monitor paused")
        else:
            self.petty_cash_running = True
            self.petty_cash_toggle_btn.config(text="⏸️ Pause", bg='#ff8800', fg='#000000')
            self.petty_cash_status.set("Running")
            self.petty_cash_status_color = "#00ccff"
            self._schedule_petty_cash_run()
            self._log_petty_cash("Petty cash monitor started")
        
        self._update_petty_cash_status()
    
    def run_header_now(self):
        """Run header monitor immediately"""
        if not self.header_running:
            self._log_header("Header monitor is paused. Please start it first.")
            return
        
        self._log_header("🔄 Running header monitor...")
        threading.Thread(target=self._run_header_monitor, daemon=True).start()
    
    def run_petty_cash_now(self):
        """Run petty cash monitor immediately"""
        if not self.petty_cash_running:
            self._log_petty_cash("Petty cash monitor is paused. Please start it first.")
            return
        
        self._log_petty_cash("💰 Running petty cash monitor...")
        threading.Thread(target=self._run_petty_cash_monitor, daemon=True).start()
    
    def force_process_all_transactions(self):
        """Force process all unprocessed transactions"""
        if not self.petty_cash_running:
            self._log_petty_cash("Petty cash monitor is paused. Please start it first.")
            return
        
        # Confirm with user
        if not messagebox.askyesno("Force Process All", 
                                  "This will process ALL unprocessed transactions (including the 1,900 backlog).\n\n"
                                  "This may take several minutes and will use API quota.\n\n"
                                  "Do you want to continue?"):
            return
        
        self._log_petty_cash("🚀 Force processing ALL transactions...")
        threading.Thread(target=self._run_force_process_all, daemon=True).start()
    
    def _run_header_monitor(self):
        """Run header monitor in thread"""
        try:
            self.header_monitor.run_monitoring_cycle()
            self.header_last_run = datetime.now()
            self._schedule_header_run()
            self._log_header("✅ Header monitor completed successfully")
        except Exception as e:
            self._log_header(f"❌ Header monitor failed: {e}")
    
    def _run_petty_cash_monitor(self):
        """Run petty cash monitor in thread"""
        try:
            result = self.petty_cash_monitor.run_single_check()
            self.petty_cash_last_run = datetime.now()
            self._schedule_petty_cash_run()
            
            if result['success']:
                if result['new_transactions_found'] > 0:
                    self._log_petty_cash(f"✅ Found {result['new_transactions_found']} new transactions")
                    self._log_petty_cash(f"📊 Processed: {result['processed_count']} transactions")
                    if result['new_sources_added'] > 0:
                        self._log_petty_cash(f"🆕 Added {result['new_sources_added']} new sources")
                    self._log_petty_cash(f"💬 {result['message']}")
                else:
                    self._log_petty_cash("✅ No new transactions found")
            else:
                self._log_petty_cash(f"❌ Petty cash monitor failed: {result['message']}")
        except Exception as e:
            self._log_petty_cash(f"❌ Petty cash monitor failed: {e}")
    
    def _run_force_process_all(self):
        """Run force process all transactions in thread"""
        try:
            self._log_petty_cash("🔄 Starting force process of all transactions...")
            
            # Import the optimized sorter for bulk processing
            from petty_cash_sorter_optimized import PettyCashSorter
            
            # Initialize the sorter
            sorter = PettyCashSorter()
            
            # Process all transactions
            success = sorter.process_transactions()
            
            if success:
                self._log_petty_cash("✅ Force process completed successfully!")
                self._log_petty_cash("📊 All unprocessed transactions have been sorted")
                self._log_petty_cash("💡 Regular monitoring will now only process new transactions")
            else:
                self._log_petty_cash("❌ Force process failed - check logs for details")
            
            # Update last run time
            self.petty_cash_last_run = datetime.now()
            
        except Exception as e:
            self._log_petty_cash(f"❌ Force process failed: {e}")
    
    def _schedule_runs(self):
        """Schedule both monitors"""
        self._schedule_header_run()
        self._schedule_petty_cash_run()
    
    def _schedule_header_run(self):
        """Schedule next header monitor run"""
        if self.header_running:
            interval_hours = self.config['header_interval_hours']
            self.header_next_run = datetime.now() + timedelta(hours=interval_hours)
            self._log_header(f"📅 Header monitor scheduled for {self.header_next_run.strftime('%H:%M:%S')}")
    
    def _schedule_petty_cash_run(self):
        """Schedule next petty cash monitor run"""
        if self.petty_cash_running:
            interval_minutes = self.config['petty_cash_interval_minutes']
            self.petty_cash_next_run = datetime.now() + timedelta(minutes=interval_minutes)
            self._log_petty_cash(f"📅 Petty cash monitor scheduled for {self.petty_cash_next_run.strftime('%H:%M:%S')}")
    
    def _update_ui(self):
        """Update UI elements"""
        self._update_header_status()
        self._update_petty_cash_status()
        
        # Check if it's time to run monitors
        now = datetime.now()
        
        if (self.header_running and self.header_next_run and 
            now >= self.header_next_run):
            self.run_header_now()
        
        if (self.petty_cash_running and self.petty_cash_next_run and 
            now >= self.petty_cash_next_run):
            self.run_petty_cash_now()
        
        # Schedule next update
        self.root.after(1000, self._update_ui)  # Update every second
    
    def _update_header_status(self):
        """Update header monitor status display"""
        self.header_status_label.config(fg=self.header_status_color)
        
        if self.header_last_run:
            self.header_last_run_label.config(
                text=f"Last Run: {self.header_last_run.strftime('%m/%d %H:%M:%S')}"
            )
        
        if self.header_next_run:
            self.header_next_run_label.config(
                text=f"Next Run: {self.header_next_run.strftime('%m/%d %H:%M:%S')}"
            )
    
    def _update_petty_cash_status(self):
        """Update petty cash monitor status display"""
        self.petty_cash_status_label.config(fg=self.petty_cash_status_color)
        
        if self.petty_cash_last_run:
            self.petty_cash_last_run_label.config(
                text=f"Last Run: {self.petty_cash_last_run.strftime('%m/%d %H:%M:%S')}"
            )
        
        if self.petty_cash_next_run:
            self.petty_cash_next_run_label.config(
                text=f"Next Run: {self.petty_cash_next_run.strftime('%m/%d %H:%M:%S')}"
            )
    
    def _log(self, msg):
        """Add message to combined log (legacy support)"""
        self._log_header(msg)
    
    def _log_header(self, msg):
        """Add message to header monitor log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {msg}"
        with self._lock:
            self._header_log_lines.append(log_entry)
        
        # Keep only last 100 lines
        with self._lock:
            if len(self._header_log_lines) > 100:
                self._header_log_lines = self._header_log_lines[-100:]
        
        # Update header log display
        self.header_log_box.config(state='normal')
        self.header_log_box.delete(1.0, tk.END)
        self.header_log_box.insert(tk.END, '\n'.join(self._header_log_lines))
        self.header_log_box.config(state='disabled')
        self.header_log_box.see(tk.END)
    
    def _log_petty_cash(self, msg):
        """Add message to petty cash monitor log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {msg}"
        with self._lock:
            self._petty_cash_log_lines.append(log_entry)
        
        # Keep only last 100 lines
        with self._lock:
            if len(self._petty_cash_log_lines) > 100:
                self._petty_cash_log_lines = self._petty_cash_log_lines[-100:]
        
        # Update petty cash log display
        self.petty_cash_log_box.config(state='normal')
        self.petty_cash_log_box.delete(1.0, tk.END)
        self.petty_cash_log_box.insert(tk.END, '\n'.join(self._petty_cash_log_lines))
        self.petty_cash_log_box.config(state='disabled')
        self.petty_cash_log_box.see(tk.END)
    
    def _minimize_to_tray(self, event=None):
        """Minimize to system tray"""
        self.root.withdraw()
        self.minimized_to_tray = True
        self._log("Window minimized to tray")
    
    def _restore_from_tray(self):
        """Restore from system tray"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.minimized_to_tray = False
        self._log("Window restored from tray")
    
    def _on_closing(self):
        """Handle window closing"""
        if messagebox.askokcancel("Quit", "Do you want to quit the monitor?"):
            self._log("Application shutting down")
            self.root.quit()

def main():
    """Main function"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    os.makedirs('config', exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/enhanced_widget.log'),
            logging.StreamHandler()
        ]
    )
    
    # Create and run widget
    root = tk.Tk()
    app = EnhancedMonitorWidget(root)
    
    # Start both monitors by default
    app.header_running = True
    app.petty_cash_running = True
    app._schedule_runs()
    app._log_header(f"Header monitor interval: {app.config['header_interval_hours']} hours")
    app._log_petty_cash(f"Petty cash monitor interval: {app.config['petty_cash_interval_minutes']} minutes")
    
    root.mainloop()

if __name__ == "__main__":
    main() 