# Create Kafka topics in Redpanda
$ErrorActionPreference = "Continue"
$MAIN = if ($env:KAFKA_TOPIC_TXNS) { $env:KAFKA_TOPIC_TXNS } else { "txns.company.batches" }
$PROM = if ($env:KAFKA_TOPIC_PROMOTE) { $env:KAFKA_TOPIC_PROMOTE } else { "rules.promote.requests" }
docker exec kylo-redpanda rpk topic create $MAIN --partitions 16 --replicas 1 2>$null
docker exec kylo-redpanda rpk topic create $PROM --partitions 8 --replicas 1 2>$null
docker exec kylo-redpanda rpk topic list
