#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Completely clear and recreate dropdowns with properly filtered data
"""

from monitor_system import GoogleSheetsManager
import logging
from gspread_formatting import set_data_validation_for_cell_range, DataValidationRule, BooleanCondition
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_recreate_dropdowns():
    print("🧹 Cleaning and Recreating Dropdowns...")
    print("=" * 60)
    
    # Initialize Google Sheets Manager
    gsm = GoogleSheetsManager()
    
    try:
        if not gsm.gc:
            print("❌ Google Sheets client not authenticated")
            return
            
        # Get the 2025 JGD Financials spreadsheet (source)
        petty_cash_url = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU/edit"
        source_spreadsheet = gsm.gc.open_by_url(petty_cash_url)
        
        # Get the JGD Truth spreadsheet (target)
        jgd_truth_url = "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit?gid=1349136605#gid=1349136605"
        target_spreadsheet = gsm.gc.open_by_url(jgd_truth_url)
        
        print(f"📊 Source Spreadsheet: {source_spreadsheet.title}")
        print(f"📊 Target Spreadsheet: {target_spreadsheet.title}")
        
        # Sheets to ignore
        IGNORED_SHEETS = {
            'EXPANSION CHECKLIST', 'Balance and Misc', 'Petty Cash KEY', 'TIM', 
            'SHIFT LOG', 'Copy of TIM', 'EQUIPMENT UPGRADES', 'Info', 'C-Store', 
            'All Time Resale', 'Monthly Burn', 'Trimming', '2022 1099s', 
            'Bills Need Moved to Alt Acct', 'Nydam Credit Card Debt Excluded', 
            'TIMELESS 4 SUNDAY', 'ORG CHART', 'PREROLLS', 'Paystub', 'Sheet1', 
            'Colorado Cures', '2023 1099s'
        }
        
        # Patterns for non-header values
        NON_HEADER_PATTERNS = [
            r'^\s*\$\s*[\d,]+\.?\d*\s*$',  # Dollar amounts
            r'^\s*\$\s*\([\d,]+\.?\d*\)\s*$',  # Negative dollar amounts
            r'^\s*[\d,]+\.?\d*\s*%?\s*$',  # Percentages or numbers
            r'^\s*[\d,]+\.?\d*\s*PER\s+\d+\s*$',  # Like "20 PER 1000"
            r'^\s*[\d,]+\.?\d*\s*$',  # Plain numbers
            r'^\s*[A-Z\s]+\s*ID#.*$',  # Long descriptive text with ID
            r'^\s*[A-Z\s]+\s*DL#.*$',  # Long descriptive text with DL
            r'^\s*[A-Z\s]+\s*Vehicle:.*$',  # Long descriptive text with Vehicle
            r'^\s*[A-Z\s]+\s*Plate#.*$',  # Long descriptive text with Plate
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+$',  # Timestamps
            r'^New source from.*$',  # "New source from..." entries
        ]
        
        # Collect valid sheets and headers
        valid_sheets = []
        all_valid_headers = []
        
        print(f"\n🔍 Collecting data from source spreadsheet...")
        
        for worksheet in source_spreadsheet.worksheets():
            sheet_name = worksheet.title
            
            # Skip ignored sheets
            if sheet_name in IGNORED_SHEETS:
                print(f"  Skipping ignored sheet: {sheet_name}")
                continue
            
            try:
                # Get headers from row 19
                headers = worksheet.row_values(19)
                filtered_headers = []
                
                for header in headers:
                    if not header or not header.strip():
                        continue
                        
                    # Check if it matches non-header patterns
                    is_non_header = False
                    for pattern in NON_HEADER_PATTERNS:
                        if re.match(pattern, header, re.IGNORECASE):
                            is_non_header = True
                            break
                    
                    if not is_non_header:
                        filtered_headers.append(header.strip())
                
                if filtered_headers:
                    valid_sheets.append(sheet_name)
                    all_valid_headers.extend(filtered_headers)
                    print(f"  ✅ {sheet_name}: {len(filtered_headers)} valid headers")
                else:
                    print(f"  ⚠️  {sheet_name}: No valid headers found")
                    
            except Exception as e:
                print(f"  ❌ Error reading {sheet_name}: {e}")
        
        # Remove duplicates and sort
        valid_sheets = sorted(list(set(valid_sheets)))
        all_valid_headers = sorted(list(set(all_valid_headers)))
        
        print(f"\n📊 Summary:")
        print(f"  Valid sheets: {len(valid_sheets)}")
        print(f"  Valid headers: {len(all_valid_headers)}")
        
        # Check for REGISTERS
        if "REGISTERS" in all_valid_headers:
            position = all_valid_headers.index("REGISTERS") + 1
            print(f"  ✅ REGISTERS found at position {position}")
        else:
            print(f"  ❌ REGISTERS NOT found")
        
        # Update target sheets
        target_sheets = ['NUGZ', 'JGD', 'PUFFIN']
        
        for sheet_name in target_sheets:
            try:
                worksheet = target_spreadsheet.worksheet(sheet_name)
                print(f"\n🔄 Updating {sheet_name} sheet...")
                
                # Create validation rules
                sheet_rule = DataValidationRule(
                    BooleanCondition('ONE_OF_LIST', valid_sheets),
                    showCustomUi=True,
                    strict=True
                )
                
                header_rule = DataValidationRule(
                    BooleanCondition('ONE_OF_LIST', all_valid_headers),
                    showCustomUi=True,
                    strict=True
                )
                
                # Apply to columns B and C (rows 2-988)
                set_data_validation_for_cell_range(worksheet, 'B2:B988', sheet_rule)
                set_data_validation_for_cell_range(worksheet, 'C2:C988', header_rule)
                
                print(f"  ✅ Updated {sheet_name} dropdowns")
                print(f"    Column B: {len(valid_sheets)} sheet options")
                print(f"    Column C: {len(all_valid_headers)} header options")
                
            except Exception as e:
                print(f"  ❌ Error updating {sheet_name}: {e}")
        
        print(f"\n🎉 Dropdown recreation completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    clean_recreate_dropdowns() 