#!/usr/bin/env python3
"""
Diagnose Row Counting
Shows exactly what's happening with row counting and filtering in Petty Cash
"""

import gspread
import logging
from google.oauth2.service_account import Credentials
from pathlib import Path

def diagnose_row_counting():
    """Diagnose the row counting and filtering process."""
    print("🔍 DIAGNOSING ROW COUNTING AND FILTERING")
    print("=" * 60)
    
    try:
        # Google Sheets setup
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file('config/service_account.json', scopes=scope)
        gc = gspread.authorize(creds)
        
        # Sheet configuration
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/1DLYt2r34zASzALv6crQ9GOysdr8sLHL0Bor-5nW5QCU"
        worksheet_name = "PETTY CASH"
        
        # Column mapping (0-based index)
        columns = {
            'initials': 0,    # Column A
            'date': 1,        # Column B
            'company': 2,     # Column C
            'source': 3,      # Column D
            'amount': 18      # Column S
        }
        
        print(f"📊 Opening spreadsheet: {spreadsheet_url}")
        print(f"📋 Worksheet: {worksheet_name}")
        
        # Open the spreadsheet
        spreadsheet = gc.open_by_url(spreadsheet_url)
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        # Get ALL data from the worksheet
        all_data = worksheet.get_all_values(value_render_option='FORMATTED_VALUE')
        total_rows_in_sheet = len(all_data)
        
        print(f"\n📈 TOTAL ROWS IN SHEET: {total_rows_in_sheet}")
        print(f"📋 HEADER ROWS (1-4): 4 rows")
        print(f"📊 DATA ROWS AVAILABLE: {total_rows_in_sheet - 4} rows")
        
        # Find the last meaningful data row
        last_meaningful_row = 4  # Default to just headers
        for row_idx in range(len(all_data) - 1, 3, -1):  # Start from end, skip first 4 rows
            row_data = all_data[row_idx]
            
            # Check if this row has meaningful data
            meaningful_data_count = 0
            key_columns = [columns['initials'], columns['date'], columns['company'], columns['source'], columns['amount']]
            
            for col_idx in key_columns:
                if col_idx < len(row_data):
                    cell_value = row_data[col_idx].strip()
                    if cell_value and cell_value not in ['', '0', '0.00', '0.0']:
                        meaningful_data_count += 1
            
            if meaningful_data_count >= 3:  # At least 3 key columns have data
                last_meaningful_row = row_idx
                break
        
        print(f"\n🔍 LAST MEANINGFUL DATA ROW: {last_meaningful_row + 1}")
        print(f"📊 ROWS TO PROCESS: {last_meaningful_row - 3} rows (excluding headers)")
        
        # Analyze the data rows (starting from row 5, index 4)
        start_row = 4
        end_row = last_meaningful_row + 1
        
        print(f"\n📋 ANALYZING ROWS {start_row + 1} TO {end_row}:")
        print("-" * 60)
        
        total_analyzed = 0
        skipped_empty = 0
        skipped_invalid_date = 0
        skipped_invalid_amount = 0
        zero_amount = 0
        valid_transactions = 0
        
        # Create lists to store problematic rows for user review
        empty_rows = []
        invalid_date_rows = []
        invalid_amount_rows = []
        
        for i, row_data in enumerate(all_data[start_row:end_row], start=start_row + 1):
            row_number = i + 1  # 1-based row number
            total_analyzed += 1
            
            # Extract data
            initials = row_data[columns['initials']] if len(row_data) > columns['initials'] else ''
            date_val = row_data[columns['date']] if len(row_data) > columns['date'] else ''
            company = row_data[columns['company']] if len(row_data) > columns['company'] else ''
            source = row_data[columns['source']] if len(row_data) > columns['source'] else ''
            amount_val = row_data[columns['amount']] if len(row_data) > columns['amount'] else ''
            
            # Check for empty rows
            if not all([initials, date_val, company, source, amount_val]):
                skipped_empty += 1
                empty_rows.append(row_number)
                print(f"  Row {row_number:4d}: ❌ EMPTY/MISSING DATA")
                continue
            
            # Check for invalid date
            try:
                from datetime import datetime
                if date_val:
                    # Try to parse the date
                    if '/' in date_val:
                        parts = date_val.split('/')
                        if len(parts) == 3:
                            month, day, year = parts
                            if len(year) == 2:
                                year = '20' + year
                            datetime(int(year), int(month), int(day))
                        else:
                            raise ValueError("Invalid date format")
                    else:
                        raise ValueError("No date separator found")
                else:
                    raise ValueError("Empty date")
            except Exception:
                skipped_invalid_date += 1
                invalid_date_rows.append(row_number)
                print(f"  Row {row_number:4d}: ❌ INVALID DATE: {date_val}")
                continue
            
            # Check for invalid amount using the same logic as CSV downloader
            try:
                parsed_amount = parse_amount_test(amount_val)
                if parsed_amount is None:
                    raise ValueError("Could not parse amount")
            except Exception:
                skipped_invalid_amount += 1
                invalid_amount_rows.append(row_number)
                print(f"  Row {row_number:4d}: ❌ INVALID AMOUNT: {amount_val}")
                continue
            
            # Check for zero amount
            if parsed_amount == 0:
                zero_amount += 1
                print(f"  Row {row_number:4d}: ⚪ ZERO AMOUNT: {source} - ${parsed_amount}")
            else:
                valid_transactions += 1
                print(f"  Row {row_number:4d}: ✅ VALID: {source} - ${parsed_amount}")
        
        print("-" * 60)
        print(f"\n📊 SUMMARY:")
        print(f"  Total rows in sheet: {total_rows_in_sheet}")
        print(f"  Header rows: 4")
        print(f"  Data rows available: {total_rows_in_sheet - 4}")
        print(f"  Last meaningful data row: {last_meaningful_row + 1}")
        print(f"  Rows analyzed: {total_analyzed}")
        print(f"  └─ Skipped (empty): {skipped_empty}")
        print(f"  └─ Skipped (invalid date): {skipped_invalid_date}")
        print(f"  └─ Skipped (invalid amount): {skipped_invalid_amount}")
        print(f"  └─ Zero amount transactions: {zero_amount}")
        print(f"  └─ Valid transactions: {valid_transactions}")
        print(f"\n🎯 FINAL RESULT: {valid_transactions} transactions processed")
        
        # Show problematic rows for user review
        if empty_rows:
            print(f"\n📝 EMPTY ROWS TO REVIEW: {empty_rows}")
        if invalid_date_rows:
            print(f"📝 INVALID DATE ROWS TO REVIEW: {invalid_date_rows}")
        if invalid_amount_rows:
            print(f"📝 INVALID AMOUNT ROWS TO REVIEW: {invalid_amount_rows[:20]}...")  # Show first 20
            if len(invalid_amount_rows) > 20:
                print(f"   ... and {len(invalid_amount_rows) - 20} more rows")
        
        # Show what's beyond the last meaningful row
        if last_meaningful_row + 1 < total_rows_in_sheet:
            remaining_rows = total_rows_in_sheet - (last_meaningful_row + 1)
            print(f"\n⚠️  REMAINING ROWS ({remaining_rows} rows) beyond last meaningful data:")
            print("   These are likely empty or contain only formatting/formulas")
            
            # Show a few examples
            for i in range(last_meaningful_row + 1, min(last_meaningful_row + 6, total_rows_in_sheet)):
                row_data = all_data[i]
                row_number = i + 1
                sample_data = ' | '.join([cell.strip() for cell in row_data[:5] if cell.strip()])
                if not sample_data:
                    sample_data = "EMPTY"
                print(f"   Row {row_number:4d}: {sample_data}")
            
            if remaining_rows > 5:
                print(f"   ... and {remaining_rows - 5} more rows")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def is_zero_amount(amount_str: str) -> bool:
    """Check if amount is zero or empty."""
    if not amount_str:
        return True
    
    amount_str = str(amount_str).strip()
    zero_patterns = [
        '$ -', '$ - ', '-', '0', '$0', '$ 0',
        '$0.00', '$ 0.00', '($0.00)', '($ 0.00)',
        '-$0.00', '-$ 0.00', '0.00', '0.0',
        '($0)', '($ 0)', '-$0', '-$ 0',
        '$0.0', '$ 0.0', '($0.0)', '($ 0.0)',
        '-$0.0', '-$ 0.0', '0', '0.0', '0.00',
        '$ (0.00)', '$ (0)', '$ (0.0)',  # Add missing patterns
        '(0.00)', '(0)', '(0.0)'  # Add missing patterns
    ]
    
    return amount_str in zero_patterns

def parse_amount_test(amount_str: str):
    """Parse amount string to float using the same logic as CSV downloader."""
    try:
        if not amount_str:
            return None
        
        amount_str = str(amount_str).strip()
        
        # Handle zero/empty amounts first
        if is_zero_amount(amount_str):
            return 0.0
        
        # Handle negative format: $ (60.00) - parentheses with dollar sign
        if '$ (' in amount_str and ')' in amount_str:
            number_str = amount_str.replace('$ (', '').replace(')', '').replace(',', '')
            parsed_amount = float(number_str)
            return -parsed_amount  # Make it negative
        
        # Handle negative format: (25.50) - parentheses without dollar sign
        elif amount_str.startswith('(') and amount_str.endswith(')'):
            number_str = amount_str[1:-1].replace(',', '')
            parsed_amount = float(number_str)
            return -parsed_amount  # Make it negative
        
        # Handle positive format: $1,500.00
        elif '$' in amount_str:
            number_str = amount_str.replace('$', '').replace(',', '').strip()
            return float(number_str)
        
        # Handle plain numbers
        else:
            return float(amount_str)
        
    except Exception as e:
        return None

if __name__ == "__main__":
    diagnose_row_counting() 