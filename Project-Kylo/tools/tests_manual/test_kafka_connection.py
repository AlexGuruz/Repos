#!/usr/bin/env python3
import os
import asyncio
from aiokafka import AIOKafkaConsumer

async def test_kafka_connection():
    brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    print(f"Connecting to Kafka brokers: {brokers}")
    
    # Convert to list if it's a string
    if isinstance(brokers, str):
        brokers = brokers.split(',')
    
    try:
        consumer = AIOKafkaConsumer(
            "test-topic",
            bootstrap_servers=brokers,
            group_id="test-group",
            client_id="test-client",
            enable_auto_commit=False,
            auto_offset_reset="earliest"
        )
        
        print("Starting consumer...")
        await consumer.start()
        print("✅ Kafka connection successful!")
        
        await consumer.stop()
        print("✅ Consumer stopped successfully")
        
    except Exception as e:
        print(f"❌ Kafka connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_kafka_connection())
