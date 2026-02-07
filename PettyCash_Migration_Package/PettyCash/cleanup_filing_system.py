#!/usr/bin/env python3
"""Clean up filing system to remove historical data"""

import sqlite3
from pathlib import Path
import shutil

def cleanup_filing_system():
    """Clean up filing system to match current database."""
    
    print("🧹 CLEANING UP FILING SYSTEM")
    print("=" * 50)
    
    try:
        # Check current database
        conn = sqlite3.connect("petty_cash.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM transactions")
        db_total = cursor.fetchone()[0]
        
        print(f"📊 CURRENT DATABASE: {db_total} transactions")
        
        # Clean up CSV files
        csv_dir = Path("data/processed_transactions/csv_files")
        if csv_dir.exists():
            print(f"🗑️ Removing old CSV files...")
            shutil.rmtree(csv_dir)
            print(f"✅ Removed {csv_dir}")
        
        # Clean up filing database
        filing_db = Path("data/processed_transactions/filing_system.db")
        if filing_db.exists():
            print(f"🗑️ Removing old filing database...")
            filing_db.unlink()
            print(f"✅ Removed {filing_db}")
        
        # Clean up processed_data directory
        processed_dir = Path("data/processed_data")
        if processed_dir.exists():
            print(f"🗑️ Removing processed data directory...")
            shutil.rmtree(processed_dir)
            print(f"✅ Removed {processed_dir}")
        
        # Clean up downloaded CSV files
        downloaded_dir = Path("data/downloaded_csv")
        if downloaded_dir.exists():
            print(f"🗑️ Removing downloaded CSV files...")
            shutil.rmtree(downloaded_dir)
            print(f"✅ Removed {downloaded_dir}")
        
        # Clean up zero amount transactions
        zero_dir = Path("data/zero_amount_transactions")
        if zero_dir.exists():
            print(f"🗑️ Removing zero amount transactions...")
            shutil.rmtree(zero_dir)
            print(f"✅ Removed {zero_dir}")
        
        conn.close()
        
        print(f"\n✅ FILING SYSTEM CLEANUP COMPLETE!")
        print(f"  • Removed all historical CSV files")
        print(f"  • Removed old filing database")
        print(f"  • Current database remains intact ({db_total} transactions)")
        print(f"  • Next run will have accurate statistics")
        
        return True
        
    except Exception as e:
        print(f"❌ Error cleaning up filing system: {e}")
        return False

if __name__ == "__main__":
    cleanup_filing_system() 