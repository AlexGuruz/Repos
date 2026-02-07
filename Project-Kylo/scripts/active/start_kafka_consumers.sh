#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
KAFKA_BROKERS=${KAFKA_BROKERS:-localhost:9092}
KAFKA_TOPIC_TXNS=${KAFKA_TOPIC_TXNS:-txns.company.batches}
KAFKA_TOPIC_PROMOTE=${KAFKA_TOPIC_PROMOTE:-rules.promote.requests}
KAFKA_GROUP_TXNS=${KAFKA_GROUP_TXNS:-kylo-workers-txns}
KAFKA_GROUP_PROMOTE=${KAFKA_GROUP_PROMOTE:-kylo-workers-promote}
KAFKA_CLIENT_ID=${KAFKA_CLIENT_ID:-kylo-consumer}
KYLO_SHEETS_POST=${KYLO_SHEETS_POST:-0}

echo "Starting Kafka consumers..."
echo "Brokers: $KAFKA_BROKERS"
echo "Sheets Posting: $KYLO_SHEETS_POST"
echo ""

# Start transaction consumer
echo "Starting transaction consumer..."
python -m services.bus.kafka_consumer_txns &
TXNS_PID=$!

# Start promote consumer
echo "Starting promote consumer..."
python -m services.bus.kafka_consumer_promote &
PROMOTE_PID=$!

echo "Consumers started with PIDs: $TXNS_PID, $PROMOTE_PID"
echo "Press Ctrl+C to stop all consumers"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping consumers..."
    kill $TXNS_PID $PROMOTE_PID 2>/dev/null || true
    wait $TXNS_PID $PROMOTE_PID 2>/dev/null || true
    echo "Consumers stopped"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Wait for both processes
wait $TXNS_PID $PROMOTE_PID
