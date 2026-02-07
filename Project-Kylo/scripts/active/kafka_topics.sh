#!/usr/bin/env bash
set -euo pipefail
MAIN="${KAFKA_TOPIC_TXNS:-txns.company.batches}"
PROM="${KAFKA_TOPIC_PROMOTE:-rules.promote.requests}"
docker exec -it kylo-redpanda rpk topic create "$MAIN" --partitions 16 --replicas 1 || true
docker exec -it kylo-redpanda rpk topic create "$PROM" --partitions 8  --replicas 1 || true
docker exec -it kylo-redpanda rpk topic list || true
