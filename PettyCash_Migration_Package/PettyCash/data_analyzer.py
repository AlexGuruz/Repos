#!/usr/bin/env python3
"""
DATA ANALYZER - EXAMPLE SCRIPT
==============================
This script demonstrates how to read and analyze data from the locked-down system.
You can create scripts like this to work with the data without modifying the core system.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

class DataAnalyzer:
    """Analyze data from the locked-down Petty Cash Sorter"""
    
    def __init__(self):
        self.base_dir = Path.cwd()
        self.db_path = self.base_dir / "petty_cash.db"
        self.config_path = self.base_dir / "config" / "system_config.json"
        
    def read_database(self):
        """Read all transaction data from the database"""
        if not self.db_path.exists():
            print("❌ Database not found!")
            return None
            
        conn = sqlite3.connect(self.db_path)
        
        # Read transactions
        transactions_df = pd.read_sql_query("""
            SELECT * FROM transactions 
            ORDER BY date, created_date
        """, conn)
        
        # Read rules
        rules_df = pd.read_sql_query("""
            SELECT * FROM rules 
            ORDER BY source
        """, conn)
        
        # Read audit log
        audit_df = pd.read_sql_query("""
            SELECT * FROM audit_log 
            ORDER BY timestamp DESC
        """, conn)
        
        conn.close()
        
        return {
            'transactions': transactions_df,
            'rules': rules_df,
            'audit': audit_df
        }
        
    def analyze_transactions(self, data):
        """Analyze transaction data"""
        if not data or data['transactions'].empty:
            print("❌ No transaction data found!")
            return
            
        transactions = data['transactions']
        
        print("📊 TRANSACTION ANALYSIS")
        print("=" * 50)
        
        # Basic statistics
        print(f"📈 Total Transactions: {len(transactions)}")
        print(f"💰 Total Amount: ${transactions['amount'].sum():,.2f}")
        print(f"📅 Date Range: {transactions['date'].min()} to {transactions['date'].max()}")
        
        # Company breakdown
        print(f"\n🏢 COMPANY BREAKDOWN:")
        company_stats = transactions.groupby('company').agg({
            'amount': ['count', 'sum'],
            'status': 'count'
        }).round(2)
        print(company_stats)
        
        # Status breakdown
        print(f"\n📋 STATUS BREAKDOWN:")
        status_counts = transactions['status'].value_counts()
        for status, count in status_counts.items():
            print(f"  {status}: {count} transactions")
            
        # Top sources
        print(f"\n🔝 TOP 10 TRANSACTION SOURCES:")
        top_sources = transactions['source'].value_counts().head(10)
        for source, count in top_sources.items():
            print(f"  {source}: {count} transactions")
            
        # Amount analysis
        print(f"\n💰 AMOUNT ANALYSIS:")
        print(f"  Average: ${transactions['amount'].mean():,.2f}")
        print(f"  Median: ${transactions['amount'].median():,.2f}")
        print(f"  Min: ${transactions['amount'].min():,.2f}")
        print(f"  Max: ${transactions['amount'].max():,.2f}")
        
    def analyze_rules(self, data):
        """Analyze rule matching data"""
        if not data or data['rules'].empty:
            print("❌ No rules data found!")
            return
            
        rules = data['rules']
        
        print(f"\n🎯 RULE ANALYSIS")
        print("=" * 50)
        print(f"📋 Total Rules: {len(rules)}")
        
        # Rule sources
        print(f"\n📝 RULE SOURCES:")
        source_counts = rules['source'].value_counts()
        for source, count in source_counts.items():
            print(f"  {source}: {count} rules")
            
        # Target sheets
        print(f"\n📊 TARGET SHEETS:")
        sheet_counts = rules['target_sheet'].value_counts()
        for sheet, count in sheet_counts.items():
            print(f"  {sheet}: {count} rules")
            
    def generate_report(self, data):
        """Generate a comprehensive report"""
        if not data:
            return
            
        print(f"\n📄 COMPREHENSIVE REPORT")
        print("=" * 50)
        
        transactions = data['transactions']
        rules = data['rules']
        
        # High confidence transactions
        high_conf = transactions[transactions['status'] == 'high_confidence']
        print(f"✅ High Confidence: {len(high_conf)} transactions")
        
        # Low confidence transactions
        low_conf = transactions[transactions['status'] == 'low_confidence']
        print(f"⚠️ Low Confidence: {len(low_conf)} transactions")
        
        # Unmatched transactions
        unmatched = transactions[transactions['status'] == 'unmatched']
        print(f"❌ Unmatched: {len(unmatched)} transactions")
        
        # Success rate
        total_processed = len(transactions[transactions['status'] != 'pending'])
        if total_processed > 0:
            success_rate = (len(high_conf) / total_processed) * 100
            print(f"📈 Success Rate: {success_rate:.1f}%")
            
        # Recent activity
        print(f"\n🕒 RECENT ACTIVITY:")
        recent = transactions.sort_values('created_date', ascending=False).head(5)
        for _, row in recent.iterrows():
            print(f"  {row['date']}: {row['source']} ({row['company']}) ${row['amount']:,.2f} - {row['status']}")
            
    def export_data(self, data, format='csv'):
        """Export data to different formats"""
        if not data:
            return
            
        export_dir = self.base_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == 'csv':
            # Export transactions
            transactions_file = export_dir / f"transactions_{timestamp}.csv"
            data['transactions'].to_csv(transactions_file, index=False)
            print(f"📤 Exported transactions to: {transactions_file}")
            
            # Export rules
            rules_file = export_dir / f"rules_{timestamp}.csv"
            data['rules'].to_csv(rules_file, index=False)
            print(f"📤 Exported rules to: {rules_file}")
            
        elif format == 'json':
            # Export as JSON
            json_file = export_dir / f"data_export_{timestamp}.json"
            
            export_data = {
                'transactions': data['transactions'].to_dict('records'),
                'rules': data['rules'].to_dict('records'),
                'summary': {
                    'total_transactions': len(data['transactions']),
                    'total_rules': len(data['rules']),
                    'export_date': datetime.now().isoformat()
                }
            }
            
            with open(json_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            print(f"📤 Exported data to: {json_file}")
            
    def run_analysis(self):
        """Run complete analysis"""
        print("🔍 PETTY CASH DATA ANALYZER")
        print("=" * 50)
        print("📊 Reading data from locked-down system...")
        
        # Read data
        data = self.read_database()
        if not data:
            return
            
        # Run analyses
        self.analyze_transactions(data)
        self.analyze_rules(data)
        self.generate_report(data)
        
        # Export data
        print(f"\n📤 EXPORTING DATA...")
        self.export_data(data, 'csv')
        self.export_data(data, 'json')
        
        print(f"\n✅ ANALYSIS COMPLETE!")
        print("📁 Check the 'exports' folder for exported data files")

def main():
    """Main function"""
    analyzer = DataAnalyzer()
    analyzer.run_analysis()

if __name__ == "__main__":
    main() 