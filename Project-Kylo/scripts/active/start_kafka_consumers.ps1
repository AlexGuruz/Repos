# Start Kafka consumer Python processes (runs on host, connects to localhost)
param([string]$SheetsPost = "0")
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$env:PYTHONPATH = $RepoRoot
$env:KYLO_SHEETS_POST = $SheetsPost
$env:KAFKA_BROKERS = "localhost:9092"
$env:KAFKA_TOPIC_TXNS = "txns.company.batches"
$env:KAFKA_GROUP_TXNS = "kylo-workers-txns"
$env:KAFKA_CLIENT_ID = "kylo-consumer-txns"
Start-Process powershell -ArgumentList "-NoProfile -NoExit -Command", "cd '$RepoRoot'; `$env:PYTHONPATH='$RepoRoot'; `$env:KYLO_SHEETS_POST='$SheetsPost'; `$env:KAFKA_BROKERS='localhost:9092'; python -u -m services.bus.kafka_consumer_txns_sync" -WindowStyle Normal
