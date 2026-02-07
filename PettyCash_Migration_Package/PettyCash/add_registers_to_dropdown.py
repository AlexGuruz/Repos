#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add REGISTERS to existing dropdown validation rules
"""

from monitor_system import GoogleSheetsManager
import logging
from gspread_formatting import get_data_validation_rule, set_data_validation_for_cell_range
from gspread_formatting import DataValidationRule, BooleanCondition

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def add_registers_to_dropdown():
    print("➕ Adding REGISTERS to dropdown validation...")
    print("=" * 60)
    
    # Initialize Google Sheets Manager
    gsm = GoogleSheetsManager()
    
    try:
        if not gsm.gc:
            print("❌ Google Sheets client not authenticated")
            return
            
        # Get the JGD Truth spreadsheet
        jgd_truth_url = "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit?gid=1349136605#gid=1349136605"
        spreadsheet = gsm.gc.open_by_url(jgd_truth_url)
        worksheet = spreadsheet.sheet1
        
        print(f"📊 Sheet Title: {worksheet.title}")
        
        # Get current validation rule for column C
        print("🔍 Reading current dropdown validation...")
        
        try:
            current_rule = get_data_validation_rule(worksheet, 'C2')
            print(f"Current validation rule: {current_rule}")
            
            if current_rule and hasattr(current_rule, 'condition') and current_rule.condition.type == 'ONE_OF_LIST':
                current_options = current_rule.condition.values[0].userEnteredValue.split(',')
                print(f"Current dropdown options: {len(current_options)} items")
                print(f"Sample options: {current_options[:5]}")
                
                # Check if REGISTERS is already in the options
                if "REGISTERS" in current_options:
                    print("✅ REGISTERS is already in the dropdown options!")
                else:
                    print("❌ REGISTERS is NOT in the dropdown options")
                    print("Adding REGISTERS to the list...")
                    
                    # Add REGISTERS to the options
                    current_options.append("REGISTERS")
                    current_options.sort()  # Keep it sorted
                    
                    # Create new validation rule
                    new_rule = DataValidationRule(
                        BooleanCondition('ONE_OF_LIST', current_options),
                        showCustomUi=True,
                        strict=True
                    )
                    
                    # Apply the updated rule
                    set_data_validation_for_cell_range(worksheet, 'C2:C988', new_rule)
                    print(f"✅ Updated dropdown with {len(current_options)} options including REGISTERS")
                    
            else:
                print("No existing dropdown validation found")
                
        except Exception as e:
            print(f"Error reading validation rule: {e}")
            print("Creating new dropdown with REGISTERS...")
            
            # Create new validation rule with REGISTERS
            options = ["REGISTERS", "Total", "ATM LOAD"]  # Basic options
            new_rule = DataValidationRule(
                BooleanCondition('ONE_OF_LIST', options),
                showCustomUi=True,
                strict=True
            )
            
            # Apply the rule
            set_data_validation_for_cell_range(worksheet, 'C2:C988', new_rule)
            print(f"✅ Created new dropdown with {len(options)} options including REGISTERS")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_registers_to_dropdown() 