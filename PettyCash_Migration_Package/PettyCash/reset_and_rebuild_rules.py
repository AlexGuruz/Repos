#!/usr/bin/env python3
"""
Reset and Rebuild Rules from JGD Truth
Completely wipes rules and rebuilds from original JGD Truth structure
"""

import sqlite3
import logging
import pandas as pd
from pathlib import Path
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def reset_rules_database():
    """Completely reset the rules table."""
    print("🗑️ RESETTING RULES DATABASE")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Drop and recreate rules table
        cursor.execute("DROP TABLE IF EXISTS rules")
        
        # Create fresh rules table with company field
        cursor.execute('''
            CREATE TABLE rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target_sheet TEXT NOT NULL,
                target_header TEXT NOT NULL,
                company TEXT NOT NULL,
                confidence_threshold REAL DEFAULT 0.7,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes
        cursor.execute("CREATE UNIQUE INDEX idx_rules_source_company ON rules(source, company)")
        cursor.execute("CREATE INDEX idx_rules_company ON rules(company)")
        cursor.execute("CREATE INDEX idx_rules_source ON rules(source)")
        
        conn.commit()
        conn.close()
        
        print("✅ Rules table reset successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to reset rules table: {e}")
        return False

def extract_rules_from_jgd_truth():
    """Extract rules from JGD Truth Excel file with proper company separation."""
    print("\n📖 EXTRACTING RULES FROM JGD TRUTH")
    print("=" * 50)
    
    jgd_truth_path = Path("JGDTruth.xlsx")
    
    if not jgd_truth_path.exists():
        print(f"❌ JGD Truth file not found: {jgd_truth_path}")
        return []
    
    try:
        # Read the Excel file
        excel_file = pd.ExcelFile(jgd_truth_path)
        print(f"📋 Found sheets: {excel_file.sheet_names}")
        
        all_rules = []
        
        # Process each sheet (each sheet represents a company)
        for sheet_name in excel_file.sheet_names:
            print(f"\n📊 Processing sheet: {sheet_name}")
            
            # Determine company from sheet name
            company = determine_company_from_sheet(sheet_name)
            print(f"   Company: {company}")
            
            # Read the sheet
            df = pd.read_excel(jgd_truth_path, sheet_name=sheet_name)
            print(f"   Rows: {len(df)}")
            
            # Extract rules from this sheet
            sheet_rules = extract_rules_from_sheet(df, sheet_name, company)
            all_rules.extend(sheet_rules)
            
            print(f"   Rules extracted: {len(sheet_rules)}")
        
        print(f"\n📊 Total rules extracted: {len(all_rules)}")
        return all_rules
        
    except Exception as e:
        print(f"❌ Error extracting rules: {e}")
        return []

def determine_company_from_sheet(sheet_name: str) -> str:
    """Determine company name from sheet name."""
    sheet_upper = sheet_name.upper()
    
    if 'NUGZ' in sheet_upper:
        return 'NUGZ'
    elif 'JGD' in sheet_upper:
        return 'JGD'
    elif 'PUFFIN' in sheet_upper:
        return 'PUFFIN'
    elif '710' in sheet_upper or 'EMPIRE' in sheet_upper:
        return '710 EMPIRE'
    elif 'PAYROLL' in sheet_upper:
        return 'GENERAL'
    elif 'COMMISSION' in sheet_upper:
        return 'GENERAL'
    elif 'BALANCE' in sheet_upper:
        return 'GENERAL'
    elif 'INCOME' in sheet_upper:
        return 'GENERAL'
    elif 'NON CANNABIS' in sheet_upper:
        return 'GENERAL'
    else:
        return 'GENERAL'

def extract_rules_from_sheet(df: pd.DataFrame, sheet_name: str, company: str) -> list:
    """Extract rules from a specific sheet."""
    rules = []
    
    # Based on JGD Truth structure:
    # Column 1: "Unique Source" (source names)
    # Column 2: "Last Updated: 2025-07-10 19:34:40" (target sheet names)
    # Column 3: "Total Options: 317" (target header names)
    
    source_col = df.columns[0]  # "Unique Source"
    sheet_col = df.columns[1]   # "Last Updated: 2025-07-10 19:34:40"
    header_col = df.columns[2]  # "Total Options: 317"
    
    print(f"   Source column: {source_col}")
    print(f"   Sheet column: {sheet_col}")
    print(f"   Header column: {header_col}")
    
    # Extract rules from each row
    for index, row in df.iterrows():
        source = str(row[source_col]).strip()
        target_sheet = str(row[sheet_col]).strip()
        target_header = str(row[header_col]).strip()
        
        # Skip empty or invalid entries
        if not source or source.lower() in ['nan', 'none', '']:
            continue
        
        if not target_sheet or target_sheet.lower() in ['nan', 'none', '']:
            continue
        
        if not target_header or target_header.lower() in ['nan', 'none', '']:
            continue
        
        # Clean up the values
        source = source.strip()
        target_sheet = target_sheet.strip()
        target_header = target_header.strip()
        
        # Create rule
        rule = {
            'source': source,
            'target_sheet': target_sheet,
            'target_header': target_header,
            'company': company
        }
        
        rules.append(rule)
    
    return rules

def save_rules_to_database(rules: list):
    """Save extracted rules to database."""
    print(f"\n💾 SAVING {len(rules)} RULES TO DATABASE")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Group rules by company for display
        company_stats = {}
        
        for rule in rules:
            company = rule['company']
            if company not in company_stats:
                company_stats[company] = 0
            company_stats[company] += 1
            
            # Insert rule
            cursor.execute('''
                INSERT INTO rules (source, target_sheet, target_header, company)
                VALUES (?, ?, ?, ?)
            ''', (rule['source'], rule['target_sheet'], rule['target_header'], rule['company']))
        
        conn.commit()
        
        print("✅ Rules saved successfully!")
        print(f"\n📊 Rules by company:")
        for company, count in sorted(company_stats.items()):
            print(f"   {company}: {count} rules")
        
        # Verify no duplicates
        cursor.execute("SELECT COUNT(*) FROM rules")
        total_rules = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source, company) FROM rules")
        unique_combinations = cursor.fetchone()[0]
        
        if total_rules == unique_combinations:
            print(f"\n✅ Perfect! {total_rules} rules, no duplicates")
        else:
            print(f"\n⚠️ Issue: {total_rules} rules, {unique_combinations} unique combinations")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to save rules: {e}")
        return False

def verify_rules_structure():
    """Verify the rules structure is correct."""
    print("\n🔍 VERIFYING RULES STRUCTURE")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect("config/petty_cash.db")
        cursor = conn.cursor()
        
        # Get total rules
        cursor.execute("SELECT COUNT(*) FROM rules")
        total_rules = cursor.fetchone()[0]
        print(f"📊 Total rules: {total_rules}")
        
        # Get rules by company
        cursor.execute("SELECT company, COUNT(*) FROM rules GROUP BY company ORDER BY COUNT(*) DESC")
        company_stats = cursor.fetchall()
        
        print(f"\n📋 Rules by company:")
        for company, count in company_stats:
            print(f"   {company}: {count} rules")
        
        # Check for duplicates
        cursor.execute("""
            SELECT source, company, COUNT(*) 
            FROM rules 
            GROUP BY source, company 
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"\n⚠️ Found {len(duplicates)} duplicate source+company combinations:")
            for source, company, count in duplicates[:5]:
                print(f"   '{source}' for {company}: {count} times")
        else:
            print("\n✅ No duplicate source+company combinations found")
        
        # Show sample rules
        cursor.execute("SELECT source, target_sheet, target_header, company FROM rules LIMIT 10")
        sample_rules = cursor.fetchall()
        
        print(f"\n📝 Sample rules:")
        for i, (source, sheet, header, company) in enumerate(sample_rules, 1):
            print(f"   {i}. '{source}' -> {sheet}/{header} ({company})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")

def main():
    """Main function to reset and rebuild rules."""
    print("🔄 RESET AND REBUILD RULES FROM JGD TRUTH")
    print("=" * 80)
    
    # Step 1: Reset database
    if not reset_rules_database():
        print("❌ Failed to reset database")
        return
    
    # Step 2: Extract rules from JGD Truth
    rules = extract_rules_from_jgd_truth()
    if not rules:
        print("❌ No rules extracted")
        return
    
    # Step 3: Save rules to database
    if not save_rules_to_database(rules):
        print("❌ Failed to save rules")
        return
    
    # Step 4: Verify structure
    verify_rules_structure()
    
    print("\n🎉 RULES REBUILD COMPLETED!")
    print("   Rules are now exactly as they were in JGD Truth")
    print("   Company separation maintained")
    print("   No duplicates")

if __name__ == "__main__":
    main() 