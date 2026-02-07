#!/usr/bin/env python3
"""
Sheets UX Polish
================
Utilities for improving Google Sheets user experience:
- Freeze header rows
- Apply data validation dropdowns
- Ensure consistent formatting across tabs
- Set up conditional formatting for status columns
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def generate_sheet_formatting_requests(spreadsheet_id: str, company_id: str) -> List[Dict]:
    """
    Generate Google Sheets API requests for UX polish
    
    Returns a list of batchUpdate requests that can be applied to a spreadsheet
    """
    requests = []
    
    # 1. Freeze header rows for both Active and Pending tabs
    for tab_name in [f"{company_id} Active", f"{company_id} Pending"]:
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "title": tab_name,
                    "gridProperties": {
                        "frozenRowCount": 1
                    }
                },
                "fields": "gridProperties.frozenRowCount"
            }
        })
    
    # 2. Data validation for Approved column in Pending tab
    requests.append({
        "setDataValidation": {
            "range": {
                "sheetId": f"{company_id} Pending",  # This will need to be resolved to actual sheet ID
                "startRowIndex": 1,  # Skip header row
                "startColumnIndex": 7,  # Assuming Approved column is at index 7
                "endColumnIndex": 8
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [
                        {"userEnteredValue": "TRUE"},
                        {"userEnteredValue": "FALSE"}
                    ]
                },
                "showCustomUi": True,
                "strict": True
            }
        }
    })
    
    # 3. Conditional formatting for status columns
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": f"{company_id} Pending",
                    "startRowIndex": 1,
                    "startColumnIndex": 7,  # Status column
                    "endColumnIndex": 8
                }],
                "booleanRule": {
                    "condition": {
                        "type": "TEXT_EQ",
                        "values": [{"userEnteredValue": "resolved"}]
                    },
                    "format": {
                        "backgroundColor": {"red": 0.8, "green": 1.0, "blue": 0.8},  # Light green
                        "textFormat": {"bold": True}
                    }
                }
            }
        }
    })
    
    # 4. Number formatting for amount columns
    for tab_name in [f"{company_id} Active", f"{company_id} Pending"]:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": tab_name,
                    "startRowIndex": 1,
                    "startColumnIndex": 4,  # Amount column
                    "endColumnIndex": 5
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "CURRENCY",
                            "pattern": "$#,##0.00"
                        }
                    }
                },
                "fields": "userEnteredFormat.numberFormat"
            }
        })
    
    # 5. Date formatting for occurred_at columns
    for tab_name in [f"{company_id} Active", f"{company_id} Pending"]:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": tab_name,
                    "startRowIndex": 1,
                    "startColumnIndex": 2,  # Date column
                    "endColumnIndex": 3
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {
                            "type": "DATE_TIME",
                            "pattern": "MM/dd/yyyy HH:mm"
                        }
                    }
                },
                "fields": "userEnteredFormat.numberFormat"
            }
        })
    
    # 6. Auto-resize columns
    for tab_name in [f"{company_id} Active", f"{company_id} Pending"]:
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": tab_name,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 10  # Adjust based on number of columns
                }
            }
        })
    
    return requests

def generate_header_row_formatting(company_id: str) -> Dict:
    """Generate header row formatting for consistent styling"""
    return {
        "userEnteredFormat": {
            "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},  # Blue header
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}  # White text
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE"
        }
    }

def generate_column_definitions() -> List[Dict]:
    """Generate column definitions for Active and Pending tabs"""
    return {
        "active": [
            {"name": "Transaction ID", "width": 120},
            {"name": "Date", "width": 140},
            {"name": "Description", "width": 300},
            {"name": "Amount", "width": 100},
            {"name": "Category", "width": 150},
            {"name": "Sheet", "width": 100}
        ],
        "pending": [
            {"name": "Transaction ID", "width": 120},
            {"name": "Date", "width": 140},
            {"name": "Description", "width": 300},
            {"name": "Amount", "width": 100},
            {"name": "First Seen", "width": 120},
            {"name": "Last Seen", "width": 120},
            {"name": "Status", "width": 100},
            {"name": "Approved", "width": 100}
        ]
    }

def create_sheet_template_requests(spreadsheet_id: str, company_id: str) -> List[Dict]:
    """Create complete sheet template with all formatting applied"""
    requests = []
    
    # Get column definitions
    columns = generate_column_definitions()
    
    # Create Active tab
    requests.append({
        "addSheet": {
            "properties": {
                "title": f"{company_id} Active",
                "gridProperties": {
                    "rowCount": 1000,
                    "columnCount": len(columns["active"])
                }
            }
        }
    })
    
    # Create Pending tab
    requests.append({
        "addSheet": {
            "properties": {
                "title": f"{company_id} Pending",
                "gridProperties": {
                    "rowCount": 1000,
                    "columnCount": len(columns["pending"])
                }
            }
        }
    })
    
    # Add header rows
    for tab_type, cols in columns.items():
        tab_name = f"{company_id} {tab_type.capitalize()}"
        header_values = [col["name"] for col in cols]
        
        requests.append({
            "updateCells": {
                "range": {
                    "sheetId": tab_name,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(header_values)
                },
                "rows": [{
                    "values": [{"userEnteredValue": val} for val in header_values]
                }],
                "fields": "userEnteredValue"
            }
        })
        
        # Apply header formatting
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": tab_name,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(header_values)
                },
                "cell": generate_header_row_formatting(company_id),
                "fields": "userEnteredFormat"
            }
        })
    
    return requests

def generate_conditional_formatting_rules() -> List[Dict]:
    """Generate conditional formatting rules for better UX"""
    return [
        # Highlight high amounts in red
        {
            "booleanRule": {
                "condition": {
                    "type": "NUMBER_GREATER_THAN",
                    "values": [{"userEnteredValue": "10000"}]  # $100.00
                },
                "format": {
                    "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8},  # Light red
                    "textFormat": {"bold": True}
                }
            }
        },
        # Highlight negative amounts
        {
            "booleanRule": {
                "condition": {
                    "type": "NUMBER_LESS_THAN",
                    "values": [{"userEnteredValue": "0"}]
                },
                "format": {
                    "backgroundColor": {"red": 1.0, "green": 0.9, "blue": 0.9},  # Very light red
                    "textFormat": {"foregroundColor": {"red": 0.8, "green": 0.0, "blue": 0.0}}
                }
            }
        }
    ]

def main():
    """Main function to demonstrate sheet formatting"""
    if len(sys.argv) < 2:
        print("Usage: python sheets_ux_polish.py <company_id> [spreadsheet_id]")
        print("\nExamples:")
        print("  python sheets_ux_polish.py nugz")
        print("  python sheets_ux_polish.py jgd 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
        sys.exit(1)
    
    company_id = sys.argv[1]
    spreadsheet_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"🎨 Generating Sheets UX polish for company: {company_id}")
    print("=" * 60)
    
    # Generate formatting requests
    if spreadsheet_id:
        requests = generate_sheet_formatting_requests(spreadsheet_id, company_id)
        print(f"📋 Generated {len(requests)} formatting requests for existing spreadsheet")
    else:
        requests = create_sheet_template_requests("TEMPLATE", company_id)
        print(f"📋 Generated {len(requests)} template creation requests")
    
    # Save to file for reference
    output_file = f"sheets_ux_{company_id}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "company_id": company_id,
            "spreadsheet_id": spreadsheet_id,
            "requests": requests,
            "column_definitions": generate_column_definitions(),
            "conditional_formatting": generate_conditional_formatting_rules()
        }, f, indent=2)
    
    print(f"💾 Saved formatting configuration to: {output_file}")
    print("\n📝 Next steps:")
    print("1. Apply these requests using Google Sheets API")
    print("2. Test data validation dropdowns in Pending tab")
    print("3. Verify conditional formatting works correctly")
    print("4. Check that header rows are frozen")
    print("5. Ensure consistent formatting across tabs")

if __name__ == "__main__":
    main()
