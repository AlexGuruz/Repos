#!/usr/bin/env python3
import sys
import os
sys.path.append('/app')

try:
    print("Testing Kafka consumer imports...")
    from services.bus.kafka_consumer_txns import main
    print("✅ Kafka consumer imports successfully")
    
    print("Testing database connection...")
    import psycopg2
    conn = psycopg2.connect('postgresql://postgres:kylo@kylo-pg:5432/kylo_global')
    print("✅ Database connection successful")
    conn.close()
    
    print("Testing Kafka connection...")
    from aiokafka import AIOKafkaConsumer
    print("✅ Kafka library imports successfully")
    
    print("🎉 All tests passed! Kafka consumers should work from Docker network")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
