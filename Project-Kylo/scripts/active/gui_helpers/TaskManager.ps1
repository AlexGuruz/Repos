# Scheduled Task Management Functions
# Provides functions to manage Windows Scheduled Tasks

function Get-ScheduledTaskInfo {
    param([string]$TaskName)
    
    $info = @{
        LastRunTime = $null
        NextRunTime = $null
        State = "Unknown"
    }
    
    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $info.State = $task.State.ToString()
        
        # Get task XML for detailed info
        $xmlPath = "$env:TEMP\task_$($TaskName -replace '[^\w]', '_').xml"
        schtasks /Query /TN $TaskName /XML 2>&1 | Out-File $xmlPath -Encoding UTF8
        
        if (Test-Path $xmlPath) {
            try {
                $xml = [xml](Get-Content $xmlPath)
                
                # Parse last run time from execution history
                $lastRun = $xml.Task.Triggers.Trigger | Where-Object { $_.ExecutionTime } | 
                    Select-Object -First 1 -ExpandProperty ExecutionTime
                if ($lastRun) {
                    try {
                        $info.LastRunTime = [DateTime]::Parse($lastRun)
                    } catch {}
                }
                
                # Parse next run time (from schedule)
                # This requires parsing the trigger schedule - simplified for now
                Remove-Item $xmlPath -ErrorAction SilentlyContinue
            } catch {
                Remove-Item $xmlPath -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Warning "Error getting task info: $_"
    }
    
    return $info
}

function Get-TaskLastResult {
    param([string]$TaskName)
    
    try {
        # Check task history (requires admin rights and event log access)
        $events = Get-WinEvent -FilterHashtable @{
            LogName = 'Microsoft-Windows-TaskScheduler/Operational'
            ID = 200, 201, 202
        } -MaxEvents 100 -ErrorAction SilentlyContinue | 
            Where-Object { $_.Message -like "*$TaskName*" } | 
            Select-Object -First 1
        
        if ($events) {
            if ($events.Id -eq 200) { return "Success" }
            if ($events.Id -eq 201 -or $events.Id -eq 202) { return "Failed" }
        }
    } catch {
        # History not available, try alternative method
    }
    
    return "Unknown"
}

function Load-TaskHistory {
    param(
        [string]$TaskName, 
        [System.Windows.Forms.DataGridView]$DataGridView
    )
    
    $DataGridView.Rows.Clear()
    
    try {
        $events = Get-WinEvent -FilterHashtable @{
            LogName = 'Microsoft-Windows-TaskScheduler/Operational'
            ID = 200, 201, 202
        } -MaxEvents 100 -ErrorAction SilentlyContinue | 
            Where-Object { $_.Message -like "*$TaskName*" } | 
            Select-Object -First 10
        
        foreach ($event in $events) {
            $result = if ($event.Id -eq 200) { "Success" } else { "Failed" }
            $time = $event.TimeCreated
            $row = $DataGridView.Rows.Add($time, $result, "N/A")
        }
    } catch {
        # History not available
        $DataGridView.Rows.Add("History not available", "", "")
    }
}

# Functions are available after dot-sourcing this file

