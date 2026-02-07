from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rules_promoter.service import _sheets_writeback


def test_banner_row_creation():
    """Test banner row creation for NUGZ"""
    
    print("=== Testing Banner Row Creation for NUGZ ===\n")
    
    # Get the count of active rules for NUGZ
    import subprocess
    result = subprocess.run([
        "docker", "exec", "-i", "kylo-pg", "psql", "-U", "postgres", "-d", "kylo_nugz",
        "-c", "SELECT COUNT(*) FROM app.rules_active;", "-t"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        promoted_count = int(result.stdout.strip())
        print(f"📊 Active rules count: {promoted_count}")
        
        # Call the sheets writeback function
        print(f"🎯 Calling _sheets_writeback for NUGZ...")
        result = _sheets_writeback("NUGZ", promoted_count)
        print(f"📋 Result: {result}")
        
        if result == "ok":
            print("✅ Banner row creation successful!")
        else:
            print(f"❌ Banner row creation failed: {result}")
    else:
        print(f"❌ Error getting active rule count: {result.stderr}")


if __name__ == "__main__":
    test_banner_row_creation()
