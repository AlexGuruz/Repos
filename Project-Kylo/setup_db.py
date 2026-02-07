#!/usr/bin/env python3
"""
Setup script to create company_config table for n8n workflows
"""

import psycopg2
import json
import os

def setup_company_config():
    """Create company_config table and populate with test data"""
    
    # Database connection details from the project
    db_url = "postgresql://postgres:kylo@localhost:5433/kylo_global"
    
    try:
        # Connect to database
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Connected to database successfully")
        
        # Create company_config table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS control.company_config (
          company_id TEXT PRIMARY KEY,
          db_dsn_rw TEXT NOT NULL,
          db_schema TEXT NOT NULL DEFAULT 'app',
          spreadsheet_id TEXT NOT NULL,
          tab_pending TEXT NOT NULL DEFAULT 'Pending',
          tab_active TEXT NOT NULL DEFAULT 'Active'
        );
        """
        
        cur.execute(create_table_sql)
        print("Created control.company_config table")
        
        # Insert test data
        insert_data_sql = """
        INSERT INTO control.company_config (company_id, db_dsn_rw, spreadsheet_id) VALUES
        ('EMPIRE', 'postgresql://postgres:kylo@localhost:5433/kylo_710', '1A1J_u4PDExvi_TujgHNBvBSW9xuGFSKJYQr0xoO73b4'),
        ('EMPIRE', 'postgresql://postgres:kylo@localhost:5433/kylo_jgd', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE'),
        ('NUGZ', 'postgresql://postgres:kylo@localhost:5433/kylo_nugz', '1hXG_doc4R2ODSDpjElsNgSel54kP1q2qb2RmNBOMeco'),
        ('PUFFIN', 'postgresql://postgres:kylo@localhost:5433/kylo_puffin', '1SeMGqClTe_osvDM2sH5d-M55drsqzRIgxWgKjDUA0rU'),
        ('JGD', 'postgresql://postgres:kylo@localhost:5433/kylo_jgd', '1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE')
        ON CONFLICT (company_id) DO NOTHING;
        """
        
        cur.execute(insert_data_sql)
        print("Inserted test company data")
        
        # Verify the data
        cur.execute("SELECT company_id, spreadsheet_id FROM control.company_config ORDER BY company_id")
        rows = cur.fetchall()
        print(f"Company config table contains {len(rows)} companies:")
        for row in rows:
            print(f"  - {row[0]}: {row[1]}")
        
        cur.close()
        conn.close()
        print("Database setup completed successfully!")
        
    except Exception as e:
        print(f"Error setting up database: {e}")
        return False
    
    return True

if __name__ == "__main__":
    setup_company_config()
