#!/usr/bin/env python3
"""
Manual test script to simulate the n8n Promote Rules → Publish (Kafka) workflow
"""

import psycopg2
import json
import os
from datetime import datetime
from aiokafka import AIOKafkaProducer
import asyncio

def get_company_config():
    """Get company configuration from database"""
    db_url = "postgresql://postgres:kylo@localhost:5432/kylo_global"
    
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT company_id, db_dsn_rw, db_schema, spreadsheet_id, tab_pending, tab_active 
            FROM control.company_config 
            ORDER BY company_id
        """)
        
        rows = cur.fetchall()
        companies = []
        
        for row in rows:
            companies.append({
                'company_id': row[0],
                'db_dsn_rw': row[1],
                'db_schema': row[2],
                'spreadsheet_id': row[3],
                'tab_pending': row[4],
                'tab_active': row[5]
            })
        
        cur.close()
        conn.close()
        
        return companies
        
    except Exception as e:
        print(f"Error getting company config: {e}")
        return []

async def send_promote_messages(companies):
    """Send promote messages to Kafka"""
    producer = AIOKafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None
    )
    
    try:
        await producer.start()
        print("Connected to Kafka producer")
        
        now = datetime.utcnow().isoformat()
        
        for company in companies:
            message = {
                'event_type': 'PROMOTE_RULES',
                'version': 1,
                'company_id': company['company_id'],
                'routing': {
                    'db_dsn_rw': company['db_dsn_rw'],
                    'db_schema': company['db_schema'],
                    'spreadsheet_id': company['spreadsheet_id'],
                    'tab_pending': company['tab_pending'],
                    'tab_active': company['tab_active']
                },
                'created_at': now,
                'meta': {
                    'producer': 'manual_test@promote'
                }
            }
            
            # Send message with company_id as key for partitioning
            await producer.send_and_wait(
                topic='rules.promote.requests',
                key=company['company_id'],
                value=message
            )
            
            print(f"Sent promote message for company: {company['company_id']}")
        
        print(f"Sent {len(companies)} promote messages to Kafka")
        
    except Exception as e:
        print(f"Error sending messages to Kafka: {e}")
    finally:
        await producer.stop()

def main():
    print("=== Manual Promote Workflow Test ===")
    
    # Get company configuration
    companies = get_company_config()
    if not companies:
        print("No companies found in config")
        return
    
    print(f"Found {len(companies)} companies:")
    for company in companies:
        print(f"  - {company['company_id']}: {company['spreadsheet_id']}")
    
    # Send promote messages
    print("\nSending promote messages to Kafka...")
    asyncio.run(send_promote_messages(companies))
    
    print("\nManual promote workflow test completed!")

if __name__ == "__main__":
    main()
