#!/usr/bin/env python3
"""
Examine JGD Truth Structure
Analyze the Excel file structure to understand how rules are stored
"""

import pandas as pd
from pathlib import Path

def examine_jgd_truth_structure():
    """Examine the structure of JGD Truth Excel file."""
    print("🔍 EXAMINING JGD TRUTH STRUCTURE")
    print("=" * 50)
    
    jgd_truth_path = Path("JGDTruth.xlsx")
    
    if not jgd_truth_path.exists():
        print(f"❌ JGD Truth file not found: {jgd_truth_path}")
        return
    
    try:
        # Read the Excel file
        excel_file = pd.ExcelFile(jgd_truth_path)
        print(f"📋 Found sheets: {excel_file.sheet_names}")
        
        # Examine each sheet
        for sheet_name in excel_file.sheet_names:
            print(f"\n📊 SHEET: {sheet_name}")
            print("-" * 40)
            
            # Read the sheet
            df = pd.read_excel(jgd_truth_path, sheet_name=sheet_name)
            print(f"   Rows: {len(df)}")
            print(f"   Columns: {len(df.columns)}")
            
            # Show column names
            print(f"   Column names:")
            for i, col in enumerate(df.columns):
                print(f"     {i+1}. {col}")
            
            # Show first few rows
            print(f"\n   First 3 rows:")
            for i in range(min(3, len(df))):
                row_data = df.iloc[i]
                print(f"     Row {i+1}: {dict(row_data)}")
            
            # Look for potential rule data
            print(f"\n   Looking for rule patterns...")
            
            # Check if any column contains '/' (indicating sheet/header format)
            for col in df.columns:
                col_data = df[col].astype(str)
                slash_count = col_data.str.contains('/').sum()
                if slash_count > 0:
                    print(f"     Column '{col}' has {slash_count} entries with '/' (potential targets)")
                    
                    # Show examples
                    examples = col_data[col_data.str.contains('/')].head(3).tolist()
                    print(f"       Examples: {examples}")
            
            # Check for potential source columns (text that doesn't contain '/')
            for col in df.columns:
                col_data = df[col].astype(str)
                non_slash_count = col_data[~col_data.str.contains('/') & (col_data != 'nan')].count()
                if non_slash_count > 0:
                    print(f"     Column '{col}' has {non_slash_count} entries without '/' (potential sources)")
                    
                    # Show examples
                    examples = col_data[~col_data.str.contains('/') & (col_data != 'nan')].head(3).tolist()
                    print(f"       Examples: {examples}")
    
    except Exception as e:
        print(f"❌ Error examining file: {e}")

def main():
    """Main function."""
    examine_jgd_truth_structure()

if __name__ == "__main__":
    main() 