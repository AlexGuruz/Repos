#!/usr/bin/env python3
import json
import os
import sys
sys.path.append('/app')

from kafka import KafkaConsumer

BROKERS = os.getenv("KAFKA_BROKERS","localhost:9092").split(',')
TOPIC = os.getenv("KAFKA_TOPIC_TXNS","txns.company.batches")
GROUP = os.getenv("KAFKA_GROUP_TXNS","kylo-workers-txns")
CLIENT_ID = os.getenv("KAFKA_CLIENT_ID","kylo-consumer")

def main():
    consumer = KafkaConsumer(
        TOPIC, 
        bootstrap_servers=BROKERS, 
        group_id=GROUP, 
        client_id=CLIENT_ID,
        enable_auto_commit=False, 
        auto_offset_reset="earliest",
        # Redpanda specific configuration
        security_protocol="PLAINTEXT",
        api_version="auto"
    )
    
    print(f"✅ Starting Kafka consumer for topic: {TOPIC}")
    print(f"✅ Connected to brokers: {BROKERS}")
    print("✅ Consumer is ready to receive messages!")
    print("Press Ctrl+C to stop...")
    
    try:
        for message in consumer:
            try:
                data = json.loads(message.value.decode("utf-8"))
                print(f"✅ Received message: {data}")
                consumer.commit()
            except Exception as e:
                print(f"❌ Error processing message: {e}")
                consumer.commit()
    except KeyboardInterrupt:
        print("Shutting down consumer...")
    finally:
        consumer.close()
        print("✅ Consumer stopped successfully")

if __name__ == "__main__":
    main()
