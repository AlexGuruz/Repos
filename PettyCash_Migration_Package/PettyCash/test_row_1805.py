#!/usr/bin/env python3
"""
Test Row 1805
Test why row 1805 is being marked as empty when it has all data
"""

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

def test_row_1805():
    """Test the data from row 1805."""
    print("🧪 TESTING ROW 1805")
    print("=" * 30)
    
    # Data from row 1805
    initials = 'AMW'
    date_val = '6/27/25'
    company = ' NUGZ '
    source = ' REG 3 DEPOSIT '
    amount_val = ' $ 407.00 '
    
    print(f"📊 ROW 1805 DATA:")
    print(f"  Initials: '{initials}'")
    print(f"  Date: '{date_val}'")
    print(f"  Company: '{company}'")
    print(f"  Source: '{source}'")
    print(f"  Amount: '{amount_val}'")
    
    # Test required fields check
    required_fields = [date_val, company, source, amount_val]
    print(f"\n🔍 REQUIRED FIELDS CHECK:")
    print(f"  Required fields: {required_fields}")
    print(f"  All present: {all(required_fields)}")
    
    # Test amount parsing
    print(f"\n💰 AMOUNT PARSING TEST:")
    parsed_amount = parse_amount_test(amount_val)
    print(f"  Raw amount: '{amount_val}'")
    print(f"  Parsed amount: {parsed_amount}")
    print(f"  Is zero: {is_zero_amount(amount_val)}")
    
    # Test date parsing
    print(f"\n📅 DATE PARSING TEST:")
    try:
        from datetime import datetime
        if date_val:
            if '/' in date_val:
                parts = date_val.split('/')
                if len(parts) == 3:
                    month, day, year = parts
                    if len(year) == 2:
                        year = '20' + year
                    parsed_date = datetime(int(year), int(month), int(day))
                    print(f"  Raw date: '{date_val}'")
                    print(f"  Parsed date: {parsed_date}")
                    print(f"  Valid date: ✅")
                else:
                    print(f"  Invalid date format: ❌")
            else:
                print(f"  No date separator found: ❌")
        else:
            print(f"  Empty date: ❌")
    except Exception as e:
        print(f"  Date parsing error: {e} ❌")
    
    print(f"\n💡 CONCLUSION:")
    if all(required_fields) and parsed_amount is not None:
        print(f"  ✅ Row 1805 should be processed as a valid transaction!")
    else:
        print(f"  ❌ Row 1805 has issues that prevent processing")

if __name__ == "__main__":
    test_row_1805() 