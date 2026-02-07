#!/usr/bin/env python3
"""Fix Unicode encoding issues in logging"""

import sys
import os

def fix_logging_encoding():
    """Fix Unicode encoding for Windows console."""
    
    # Set UTF-8 encoding for stdout and stderr
    if sys.platform.startswith('win'):
        # Force UTF-8 encoding for Windows
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        
        # Set environment variable
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        print("✅ Fixed Unicode encoding for Windows console")

if __name__ == "__main__":
    fix_logging_encoding() 