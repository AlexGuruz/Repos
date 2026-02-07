#!/usr/bin/env python3
"""Update configuration to use practice spreadsheet"""

import json
from pathlib import Path

def update_to_practice_spreadsheet():
    """Update configuration to use practice spreadsheet."""
    
    print("🔄 UPDATING TO PRACTICE SPREADSHEET")
    print("=" * 45)
    print()
    print("This will update the configuration to use a practice")
    print("spreadsheet instead of your original one.")
    print()
    print("⚠️  IMPORTANT: Make sure you have created a copy of")
    print("   your original spreadsheet first!")
    print()
    
    # Get the practice spreadsheet URL
    practice_url = input("Enter the URL of your practice spreadsheet: ").strip()
    
    if not practice_url:
        print("❌ No URL provided. Cancelling.")
        return False
    
    if "docs.google.com/spreadsheets" not in practice_url:
        print("❌ That doesn't look like a valid Google Sheets URL.")
        print("   Please make sure it's a Google Sheets URL.")
        return False
    
    print()
    print("✅ Valid Google Sheets URL detected")
    print()
    
    # Confirm the change
    print("This will update the following files:")
    print("  • config/system_config.json")
    print("  • google_sheets_integration.py")
    print("  • google_sheets_integration_safe.py")
    print()
    
    confirm = input("Do you want to proceed? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Update cancelled.")
        return False
    
    try:
        # Update system_config.json
        config_file = Path("config/system_config.json")
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Update the spreadsheet URL
            if 'google_sheets' not in config:
                config['google_sheets'] = {}
            
            config['google_sheets']['practice_spreadsheet_url'] = practice_url
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Updated config/system_config.json")
        
        # Create a backup of the original integration files
        print("📁 Creating backups of original files...")
        
        # Backup original google_sheets_integration.py
        original_file = Path("google_sheets_integration.py")
        backup_file = Path("google_sheets_integration_original.py")
        if original_file.exists():
            import shutil
            shutil.copy2(original_file, backup_file)
            print("✅ Created backup: google_sheets_integration_original.py")
        
        # Update google_sheets_integration.py
        print("📝 Updating google_sheets_integration.py...")
        update_integration_file("google_sheets_integration.py", practice_url)
        
        # Update google_sheets_integration_safe.py
        print("📝 Updating google_sheets_integration_safe.py...")
        update_integration_file("google_sheets_integration_safe.py", practice_url)
        
        print()
        print("🎉 SUCCESSFULLY UPDATED TO PRACTICE SPREADSHEET!")
        print("=" * 50)
        print("✅ Configuration updated")
        print("✅ Integration files updated")
        print("✅ Original files backed up")
        print()
        print("📋 Next steps:")
        print("  1. Test the program with the practice spreadsheet")
        print("  2. Debug any issues")
        print("  3. Perfect the process")
        print("  4. When ready, run the program to switch back to original")
        print()
        print("🔗 Practice spreadsheet URL:")
        print(f"   {practice_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False

def update_integration_file(filename: str, practice_url: str):
    """Update the spreadsheet URL in an integration file."""
    try:
        file_path = Path(filename)
        if not file_path.exists():
            print(f"⚠️  File {filename} not found, skipping...")
            return
        
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Replace the spreadsheet URL
        # Look for the line with financials_spreadsheet_url
        lines = content.split('\n')
        updated_lines = []
        
        for line in lines:
            if 'financials_spreadsheet_url' in line and '=' in line:
                # Update the URL
                updated_line = f'        self.financials_spreadsheet_url = "{practice_url}"'
                updated_lines.append(updated_line)
            else:
                updated_lines.append(line)
        
        # Write back to file
        with open(file_path, 'w') as f:
            f.write('\n'.join(updated_lines))
        
        print(f"✅ Updated {filename}")
        
    except Exception as e:
        print(f"❌ Error updating {filename}: {e}")

def switch_back_to_original():
    """Switch back to the original spreadsheet."""
    
    print("🔄 SWITCHING BACK TO ORIGINAL SPREADSHEET")
    print("=" * 45)
    print()
    print("This will restore the original spreadsheet configuration.")
    print()
    
    # Get the original spreadsheet URL
    original_url = input("Enter the URL of your original spreadsheet: ").strip()
    
    if not original_url:
        print("❌ No URL provided. Cancelling.")
        return False
    
    if "docs.google.com/spreadsheets" not in original_url:
        print("❌ That doesn't look like a valid Google Sheets URL.")
        return False
    
    confirm = input("Do you want to switch back to the original? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Switch cancelled.")
        return False
    
    try:
        # Update the integration files back to original
        update_integration_file("google_sheets_integration.py", original_url)
        update_integration_file("google_sheets_integration_safe.py", original_url)
        
        print()
        print("🎉 SUCCESSFULLY SWITCHED BACK TO ORIGINAL!")
        print("✅ Configuration restored to original spreadsheet")
        
        return True
        
    except Exception as e:
        print(f"❌ Error switching back: {e}")
        return False

def main():
    """Main function."""
    print("🎯 PRACTICE SPREADSHEET CONFIGURATION")
    print("=" * 50)
    print()
    print("Choose an option:")
    print("1. Update to practice spreadsheet")
    print("2. Switch back to original spreadsheet")
    print("3. Exit")
    print()
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice == '1':
        update_to_practice_spreadsheet()
    elif choice == '2':
        switch_back_to_original()
    elif choice == '3':
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice.")

if __name__ == "__main__":
    main() 