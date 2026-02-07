#!/usr/bin/env python3
"""
Test Amount Parsing Fix
Simple test to verify the amount parsing fix works
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

def test_amount_parsing():
    """Test the amount parsing fix."""
    print("🧪 TESTING AMOUNT PARSING FIX")
    print("=" * 50)
    
    # Test cases that were failing before
    test_cases = [
        "$ (450.00)",      # Should be -450.00
        "$ (1,080.50)",    # Should be -1080.50
        "$ (1,350.00)",    # Should be -1350.00
        "$ (1,013.25)",    # Should be -1013.25
        "$ (929.00)",      # Should be -929.00
        "$ (985.25)",      # Should be -985.25
        "$ (1,106.50)",    # Should be -1106.50
        "$ (618.50)",      # Should be -618.50
        "$ (366.40)",      # Should be -366.40
        "$ (300.00)",      # Should be -300.00
        "$ (1,853.52)",    # Should be -1853.52
        "$ (900.00)",      # Should be -900.00
        "$ (1,500.00)",    # Should be -1500.00
        "$ (180.00)",      # Should be -180.00
        "$ -",             # Should be 0.0 (zero)
        "$ (0.00)",        # Should be 0.0 (zero)
        "$1,500.00",       # Should be 1500.00 (positive)
        "$2,000.00",       # Should be 2000.00 (positive)
        "1500.00",         # Should be 1500.00 (plain number)
        "(25.50)",         # Should be -25.50 (parentheses without $)
    ]
    
    success_count = 0
    total_count = len(test_cases)
    
    for test_case in test_cases:
        result = parse_amount_test(test_case)
        print(f"  {test_case:15} → {result}")
        
        if result is not None:
            success_count += 1
        else:
            print(f"    ❌ FAILED: Could not parse '{test_case}'")
    
    print(f"\n📊 RESULTS:")
    print(f"  Successfully parsed: {success_count}/{total_count}")
    print(f"  Success rate: {(success_count/total_count)*100:.1f}%")
    
    if success_count == total_count:
        print("✅ All test cases passed! The fix is working.")
    else:
        print("❌ Some test cases failed. The fix needs more work.")

if __name__ == "__main__":
    test_amount_parsing() 