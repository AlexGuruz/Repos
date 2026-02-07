#!/usr/bin/env python3
"""
Simple Kafka test without database connections
"""

import json
import asyncio
from datetime import datetime
from aiokafka import AIOKafkaConsumer

async def test_kafka_consumer():
    """Test Kafka consumer without database operations"""
    
    consumer = AIOKafkaConsumer(
        'rules.promote.requests',
        bootstrap_servers='localhost:9092',
        group_id='test-consumer',
        client_id='test-client',
        enable_auto_commit=False,
        auto_offset_reset="earliest"
    )
    
    try:
        await consumer.start()
        print("✅ Kafka consumer started successfully")
        
        # Try to get messages
        results = await consumer.getmany(timeout_ms=5000, max_records=5)
        
        if results:
            print(f"✅ Found {len(results)} partitions with messages")
            for partition, batch in results.items():
                print(f"  Partition {partition}: {len(batch)} messages")
                for rec in batch:
                    try:
                        data = json.loads(rec.value.decode("utf-8"))
                        print(f"    Message: {data.get('company_id', 'unknown')} - {data.get('event_type', 'unknown')}")
                    except Exception as e:
                        print(f"    Error parsing message: {e}")
        else:
            print("ℹ️  No messages found in topic")
            
    except Exception as e:
        print(f"❌ Error with Kafka consumer: {e}")
    finally:
        await consumer.stop()

def main():
    print("=== Kafka-Only Test ===")
    asyncio.run(test_kafka_consumer())
    print("Test completed!")

if __name__ == "__main__":
    main()
