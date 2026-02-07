#!/usr/bin/env python3
import os
from kafka import KafkaConsumer

def test_kafka_connection():
    brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
    print(f"Connecting to Kafka brokers: {brokers}")
    
    # Convert to list if it's a string
    if isinstance(brokers, str):
        brokers = brokers.split(',')
    
    print(f"Brokers list: {brokers}")
    
    try:
        consumer = KafkaConsumer(
            "test-topic",
            bootstrap_servers=brokers,
            group_id="test-group",
            client_id="test-client",
            enable_auto_commit=False,
            auto_offset_reset="earliest"
        )
        
        print("✅ Kafka connection successful!")
        consumer.close()
        print("✅ Consumer closed successfully")
        
    except Exception as e:
        print(f"❌ Kafka connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_kafka_connection()
