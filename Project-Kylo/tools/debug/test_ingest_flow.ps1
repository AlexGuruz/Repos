# PowerShell script to test the ingest flow
param(
    [string]$N8nUrl = "http://localhost:5678"
)

Write-Host "Testing ingest flow..." -ForegroundColor Green
Write-Host "n8n URL: $N8nUrl" -ForegroundColor Yellow
Write-Host ""

# Sample transaction data
$testData = @{
    transactions = @(
        @{id="t1"; company_id="710"; date="2025-08-26"; amount=-12.34; description="STARBUCKS"},
        @{id="t2"; company_id="711"; date="2025-08-26"; amount=45.67; description="WALMART"},
        @{id="t3"; company_id="710"; date="2025-08-26"; amount=10.00; description="UNKNOWN"},
        @{id="t4"; company_id="711"; date="2025-08-26"; amount=-25.50; description="AMAZON"},
        @{id="t5"; company_id="710"; date="2025-08-27"; amount=100.00; description="DEPOSIT"}
    )
    batch_id = "test-batch-$(Get-Date -UFormat %s)"
    ingest_batch_id = [int](Get-Date -UFormat %s)
} | ConvertTo-Json -Depth 10

Write-Host "Sending test transactions..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "$N8nUrl/webhook/txns.ingest" -Method POST -Body $testData -ContentType "application/json"
    Write-Host "Response: $response" -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Test completed. Check consumer logs for processing." -ForegroundColor Green
Write-Host ""
