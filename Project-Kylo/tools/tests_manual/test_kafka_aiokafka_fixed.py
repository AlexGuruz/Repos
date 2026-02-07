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
    
    print(f"Brokers list: {brokers}")
    
    try:
        consumer = AIOKafkaConsumer(
            "test-topic",
            bootstrap_servers=brokers,
            group_id="test-group",
            client_id="test-client",
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            # Redpanda specific configuration
            security_protocol="PLAINTEXT",
            api_version="auto",
            # Additional configuration to fix connection issues
            request_timeout_ms=30000,
            session_timeout_ms=30000,
            heartbeat_interval_ms=3000,
            # Disable SSL
            ssl_context=None,
            sasl_mechanism=None,
            sasl_plain_username=None,
            sasl_plain_password=None
        )
        
        print("Starting consumer...")
        await consumer.start()
        print("✅ Kafka connection successful!")
        
        await consumer.stop()
        print("✅ Consumer stopped successfully")
        
    except Exception as e:
        print(f"❌ Kafka connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_kafka_connection())
