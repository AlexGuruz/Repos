# Kylo System Monitor GUI
# Comprehensive PowerShell Windows Forms GUI for monitoring and managing all Kylo systems
# Based on complete PDR specification

# Load required assemblies
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Set working directory
Set-Location "D:\Project-Kylo"

# Load helper modules
$helpersPath = Join-Path $PSScriptRoot "gui_helpers"
. (Join-Path $helpersPath "Theme.ps1")
. (Join-Path $helpersPath "SystemMonitor.ps1")
. (Join-Path $helpersPath "TaskManager.ps1")
. (Join-Path $helpersPath "LogViewer.ps1")
. (Join-Path $helpersPath "ServiceControls.ps1")

# Global variables
$script:refreshTimer = $null
$script:logWatchers = @{}
$script:logPositions = @{}
$script:dockerLogJobs = @{}
$script:dockerLogTimers = @{}
$script:autoScrollEnabled = $true
$script:theme = Get-Theme

# ============================================================================
# MAIN FORM CREATION
# ============================================================================

$form = New-Object System.Windows.Forms.Form
$form.Text = "Kylo System Monitor"
$form.Size = New-Object System.Drawing.Size(1400, 900)
$form.MinimumSize = New-Object System.Drawing.Size(1200, 700)
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.WindowState = [System.Windows.Forms.FormWindowState]::Normal
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9)

# Apply dark theme to form
Apply-DarkTheme -Control $form

# ============================================================================
# MENU BAR
# ============================================================================

$menuStrip = New-Object System.Windows.Forms.MenuStrip
$menuStrip.BackColor = $script:theme.PanelBg
$menuStrip.ForeColor = $script:theme.Text

$fileMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$fileMenu.Text = "File"
$fileMenuExit = New-Object System.Windows.Forms.ToolStripMenuItem
$fileMenuExit.Text = "Exit"
$fileMenuExit.Add_Click({ $form.Close() })
$fileMenu.DropDownItems.Add($fileMenuExit)

$helpMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$helpMenu.Text = "Help"
$helpMenuAbout = New-Object System.Windows.Forms.ToolStripMenuItem
$helpMenuAbout.Text = "About"
$helpMenuAbout.Add_Click({
    [System.Windows.Forms.MessageBox]::Show(
        "Kylo System Monitor`nVersion 1.0`n`nComprehensive monitoring and management for all Kylo systems.",
        "About",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    )
})
$helpMenu.DropDownItems.Add($helpMenuAbout)

$menuStrip.Items.AddRange(@($fileMenu, $helpMenu))
$form.MainMenuStrip = $menuStrip
$form.Controls.Add($menuStrip)

# ============================================================================
# TAB CONTROL
# ============================================================================

$tabControl = New-Object System.Windows.Forms.TabControl
$tabControl.Dock = [System.Windows.Forms.DockStyle]::Fill
$tabControl.BackColor = $script:theme.Background
$tabControl.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
$tabControl.Padding = New-Object System.Drawing.Point(20, 5)
$form.Controls.Add($tabControl)

# ============================================================================
# STATUS BAR
# ============================================================================

$statusBar = New-Object System.Windows.Forms.StatusStrip
$statusBar.BackColor = $script:theme.PanelBg
$statusBar.ForeColor = $script:theme.Text

$statusLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusLabel.Text = "Ready"
$statusBar.Items.Add($statusLabel)

$lastUpdateLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$lastUpdateLabel.Text = "Last Update: Never"
$lastUpdateLabel.Alignment = [System.Windows.Forms.ToolStripItemAlignment]::Right
$statusBar.Items.Add($lastUpdateLabel)

$form.Controls.Add($statusBar)

# ============================================================================
# SYSTEM MONITORING TAB
# ============================================================================

$tabSystemMonitor = New-Object System.Windows.Forms.TabPage
$tabSystemMonitor.Text = "System Monitor"
$tabSystemMonitor.BackColor = $script:theme.Background
$tabSystemMonitor.UseVisualStyleBackColor = $false

# Controls Panel (Top)
$panelSystemMonitorControls = New-Object System.Windows.Forms.Panel
$panelSystemMonitorControls.Dock = [System.Windows.Forms.DockStyle]::Top
$panelSystemMonitorControls.Height = 70
$panelSystemMonitorControls.BackColor = $script:theme.PanelBg
$panelSystemMonitorControls.Padding = New-Object System.Windows.Forms.Padding(15, 15, 15, 10)

# Refresh Button
$btnRefreshAll = New-Object System.Windows.Forms.Button
$btnRefreshAll.Text = "Refresh All"
$btnRefreshAll.Size = New-Object System.Drawing.Size(120, 38)
$btnRefreshAll.Location = New-Object System.Drawing.Point(1260, 16)
$btnRefreshAll.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$btnRefreshAll.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRefreshAll.ForeColor = $script:theme.TextBright
$btnRefreshAll.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRefreshAll.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
$btnRefreshAll.FlatAppearance.BorderSize = 1
$btnRefreshAll.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
$btnRefreshAll.Cursor = [System.Windows.Forms.Cursors]::Hand

# Auto-Refresh CheckBox
$chkAutoRefresh = New-Object System.Windows.Forms.CheckBox
$chkAutoRefresh.Text = "⏱️ Auto-refresh"
$chkAutoRefresh.Location = New-Object System.Drawing.Point(15, 22)
$chkAutoRefresh.BackColor = $script:theme.PanelBg
$chkAutoRefresh.ForeColor = $script:theme.Text
$chkAutoRefresh.Checked = $true
$chkAutoRefresh.Font = New-Object System.Drawing.Font("Segoe UI", 9)

# Refresh Interval ComboBox
$cmbRefreshInterval = New-Object System.Windows.Forms.ComboBox
$cmbRefreshInterval.Items.AddRange(@("5 seconds", "10 seconds", "30 seconds", "60 seconds"))
$cmbRefreshInterval.SelectedIndex = 1
$cmbRefreshInterval.Location = New-Object System.Drawing.Point(140, 20)
$cmbRefreshInterval.Size = New-Object System.Drawing.Size(110, 28)
$cmbRefreshInterval.BackColor = [System.Drawing.Color]::FromArgb(55, 55, 55)
$cmbRefreshInterval.ForeColor = $script:theme.Text
$cmbRefreshInterval.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$cmbRefreshInterval.Font = New-Object System.Drawing.Font("Segoe UI", 9)

# Filter TextBox
$txtFilterSystems = New-Object System.Windows.Forms.TextBox
$txtFilterSystems.Location = New-Object System.Drawing.Point(600, 20)
$txtFilterSystems.Size = New-Object System.Drawing.Size(250, 28)
$txtFilterSystems.Anchor = [System.Windows.Forms.AnchorStyles]::Top
$txtFilterSystems.BackColor = [System.Drawing.Color]::FromArgb(55, 55, 55)
$txtFilterSystems.ForeColor = $script:theme.TextDim
$txtFilterSystems.Text = "Search systems..."
$txtFilterSystems.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$txtFilterSystems.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle

$panelSystemMonitorControls.Controls.AddRange(@($btnRefreshAll, $chkAutoRefresh, $cmbRefreshInterval, $txtFilterSystems))

# Status Summary Panel
$panelStatusSummary = New-Object System.Windows.Forms.Panel
$panelStatusSummary.Dock = [System.Windows.Forms.DockStyle]::Top
$panelStatusSummary.Height = 60
$panelStatusSummary.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 40)
$panelStatusSummary.Padding = New-Object System.Windows.Forms.Padding(20, 15, 20, 15)

$lblTotalServices = New-Object System.Windows.Forms.Label
$lblTotalServices.Text = "Total: 7"
$lblTotalServices.Location = New-Object System.Drawing.Point(20, 18)
$lblTotalServices.Size = New-Object System.Drawing.Size(120, 24)
$lblTotalServices.ForeColor = $script:theme.TextBright
$lblTotalServices.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Regular)

$lblRunning = New-Object System.Windows.Forms.Label
$lblRunning.Text = "Running: 0"
$lblRunning.Location = New-Object System.Drawing.Point(150, 18)
$lblRunning.Size = New-Object System.Drawing.Size(120, 24)
$lblRunning.ForeColor = $script:theme.Status.Running
$lblRunning.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Regular)

$lblStopped = New-Object System.Windows.Forms.Label
$lblStopped.Text = "Stopped: 0"
$lblStopped.Location = New-Object System.Drawing.Point(280, 18)
$lblStopped.Size = New-Object System.Drawing.Size(120, 24)
$lblStopped.ForeColor = $script:theme.Status.Error
$lblStopped.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Regular)

$lblWarnings = New-Object System.Windows.Forms.Label
$lblWarnings.Text = "Warnings: 0"
$lblWarnings.Location = New-Object System.Drawing.Point(410, 18)
$lblWarnings.Size = New-Object System.Drawing.Size(120, 24)
$lblWarnings.ForeColor = $script:theme.Status.Warning
$lblWarnings.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Regular)

$lblLastUpdate = New-Object System.Windows.Forms.Label
$lblLastUpdate.Text = "Last Update: Never"
$lblLastUpdate.Location = New-Object System.Drawing.Point(540, 18)
$lblLastUpdate.Size = New-Object System.Drawing.Size(250, 24)
$lblLastUpdate.ForeColor = $script:theme.TextDim
$lblLastUpdate.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$panelStatusSummary.Controls.AddRange(@($lblTotalServices, $lblRunning, $lblStopped, $lblWarnings, $lblLastUpdate))

# Cards Container
$flowLayoutPanelCards = New-Object System.Windows.Forms.FlowLayoutPanel
$flowLayoutPanelCards.Dock = [System.Windows.Forms.DockStyle]::Fill
$flowLayoutPanelCards.AutoScroll = $true
$flowLayoutPanelCards.WrapContents = $true
$flowLayoutPanelCards.BackColor = $script:theme.Background
$flowLayoutPanelCards.Padding = New-Object System.Windows.Forms.Padding(20, 20, 20, 20)

$tabSystemMonitor.Controls.AddRange(@($flowLayoutPanelCards, $panelStatusSummary, $panelSystemMonitorControls))
$tabControl.TabPages.Add($tabSystemMonitor)

# ============================================================================
# SCHEDULED TASKS TAB
# ============================================================================

$tabScheduledTasks = New-Object System.Windows.Forms.TabPage
$tabScheduledTasks.Text = "Scheduled Tasks"
$tabScheduledTasks.BackColor = $script:theme.Background
$tabScheduledTasks.UseVisualStyleBackColor = $false

# DataGridView for tasks
$dgvScheduledTasks = New-Object System.Windows.Forms.DataGridView
$dgvScheduledTasks.Dock = [System.Windows.Forms.DockStyle]::Fill
$dgvScheduledTasks.AutoSizeColumnsMode = [System.Windows.Forms.DataGridViewAutoSizeColumnsMode]::Fill
$dgvScheduledTasks.SelectionMode = [System.Windows.Forms.DataGridViewSelectionMode]::FullRowSelect
$dgvScheduledTasks.MultiSelect = $false
$dgvScheduledTasks.ReadOnly = $true
$dgvScheduledTasks.AllowUserToAddRows = $false

# Add columns
$colTaskName = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
$colTaskName.Name = "TaskName"
$colTaskName.HeaderText = "Task Name"
$colTaskName.Width = 200

$colStatus = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
$colStatus.Name = "Status"
$colStatus.HeaderText = "Status"
$colStatus.Width = 100

$colLastRun = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
$colLastRun.Name = "LastRunTime"
$colLastRun.HeaderText = "Last Run Time"
$colLastRun.Width = 150

$colNextRun = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
$colNextRun.Name = "NextRunTime"
$colNextRun.HeaderText = "Next Run Time"
$colNextRun.Width = 150

$colLastResult = New-Object System.Windows.Forms.DataGridViewTextBoxColumn
$colLastResult.Name = "LastResult"
$colLastResult.HeaderText = "Last Result"
$colLastResult.Width = 100

$dgvScheduledTasks.Columns.Add($colTaskName)
$dgvScheduledTasks.Columns.Add($colStatus)
$dgvScheduledTasks.Columns.Add($colLastRun)
$dgvScheduledTasks.Columns.Add($colNextRun)
$dgvScheduledTasks.Columns.Add($colLastResult)

Apply-DarkTheme -Control $dgvScheduledTasks

# Action Buttons Panel
$panelTaskActions = New-Object System.Windows.Forms.Panel
$panelTaskActions.Dock = [System.Windows.Forms.DockStyle]::Bottom
$panelTaskActions.Height = 60
$panelTaskActions.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 40)
$panelTaskActions.Padding = New-Object System.Windows.Forms.Padding(15, 10, 15, 10)

$btnEnableTask = New-Object System.Windows.Forms.Button
$btnEnableTask.Text = "Enable"
$btnEnableTask.Location = New-Object System.Drawing.Point(15, 12)
$btnEnableTask.Size = New-Object System.Drawing.Size(100, 35)
$btnEnableTask.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnEnableTask.ForeColor = $script:theme.Status.Running
$btnEnableTask.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnEnableTask.FlatAppearance.BorderColor = $script:theme.Status.Running
$btnEnableTask.FlatAppearance.BorderSize = 1
$btnEnableTask.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnEnableTask.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnDisableTask = New-Object System.Windows.Forms.Button
$btnDisableTask.Text = "Disable"
$btnDisableTask.Location = New-Object System.Drawing.Point(125, 12)
$btnDisableTask.Size = New-Object System.Drawing.Size(100, 35)
$btnDisableTask.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnDisableTask.ForeColor = $script:theme.Status.Error
$btnDisableTask.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnDisableTask.FlatAppearance.BorderColor = $script:theme.Status.Error
$btnDisableTask.FlatAppearance.BorderSize = 1
$btnDisableTask.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnDisableTask.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnRunTask = New-Object System.Windows.Forms.Button
$btnRunTask.Text = "Run Now"
$btnRunTask.Location = New-Object System.Drawing.Point(235, 12)
$btnRunTask.Size = New-Object System.Drawing.Size(100, 35)
$btnRunTask.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRunTask.ForeColor = $script:theme.TextBright
$btnRunTask.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRunTask.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
$btnRunTask.FlatAppearance.BorderSize = 1
$btnRunTask.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnRunTask.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnViewTaskDetails = New-Object System.Windows.Forms.Button
$btnViewTaskDetails.Text = "Details"
$btnViewTaskDetails.Location = New-Object System.Drawing.Point(345, 12)
$btnViewTaskDetails.Size = New-Object System.Drawing.Size(100, 35)
$btnViewTaskDetails.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnViewTaskDetails.ForeColor = $script:theme.Text
$btnViewTaskDetails.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnViewTaskDetails.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
$btnViewTaskDetails.FlatAppearance.BorderSize = 1
$btnViewTaskDetails.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnViewTaskDetails.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnRefreshTasks = New-Object System.Windows.Forms.Button
$btnRefreshTasks.Text = "Refresh"
$btnRefreshTasks.Location = New-Object System.Drawing.Point(1290, 12)
$btnRefreshTasks.Size = New-Object System.Drawing.Size(100, 35)
$btnRefreshTasks.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRefreshTasks.ForeColor = $script:theme.Text
$btnRefreshTasks.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRefreshTasks.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
$btnRefreshTasks.FlatAppearance.BorderSize = 1
$btnRefreshTasks.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnRefreshTasks.Anchor = [System.Windows.Forms.AnchorStyles]::Top -bor [System.Windows.Forms.AnchorStyles]::Right
$btnRefreshTasks.Cursor = [System.Windows.Forms.Cursors]::Hand

$panelTaskActions.Controls.AddRange(@($btnEnableTask, $btnDisableTask, $btnRunTask, $btnViewTaskDetails, $btnRefreshTasks))

$tabScheduledTasks.Controls.AddRange(@($dgvScheduledTasks, $panelTaskActions))
$tabControl.TabPages.Add($tabScheduledTasks)

# ============================================================================
# LOG VIEWER TAB
# ============================================================================

$tabLogViewer = New-Object System.Windows.Forms.TabControl
$tabLogViewer.Dock = [System.Windows.Forms.DockStyle]::Fill
$tabLogViewer.BackColor = $script:theme.Background

# Monitor Log Tab
$tabMonitorLog = New-Object System.Windows.Forms.TabPage
$tabMonitorLog.Text = "Monitor Log"
$tabMonitorLog.BackColor = $script:theme.Systems.SystemMonitor.Background

# Watcher Log Tab
$tabWatcherLog = New-Object System.Windows.Forms.TabPage
$tabWatcherLog.Text = "Watcher Log"
$tabWatcherLog.BackColor = $script:theme.Systems.Watcher.Background

# ScriptHub Sync Logs Tab
$tabScriptHubSyncLogs = New-Object System.Windows.Forms.TabPage
$tabScriptHubSyncLogs.Text = "ScriptHub Sync"
$tabScriptHubSyncLogs.BackColor = $script:theme.Systems.ScriptHubSync.Background

# PostgreSQL Logs Tab
$tabPostgreSQLLogs = New-Object System.Windows.Forms.TabPage
$tabPostgreSQLLogs.Text = "PostgreSQL"
$tabPostgreSQLLogs.BackColor = $script:theme.Systems.PostgreSQL.Background

# Redpanda Logs Tab
$tabRedpandaLogs = New-Object System.Windows.Forms.TabPage
$tabRedpandaLogs.Text = "Redpanda"
$tabRedpandaLogs.BackColor = $script:theme.Systems.Redpanda.Background

# Kafka Consumer Txns Logs Tab
$tabKafkaTxnsLogs = New-Object System.Windows.Forms.TabPage
$tabKafkaTxnsLogs.Text = "Kafka Consumer Txns"
$tabKafkaTxnsLogs.BackColor = $script:theme.Systems.KafkaConsumer.Background

# Kafka Consumer Promote Logs Tab
$tabKafkaPromoteLogs = New-Object System.Windows.Forms.TabPage
$tabKafkaPromoteLogs.Text = "Kafka Consumer Promote"
$tabKafkaPromoteLogs.BackColor = $script:theme.Systems.KafkaConsumer.Background

# Function to create log tab content
function Create-LogTab {
    param(
        [System.Windows.Forms.TabPage]$TabPage,
        [string]$LogFile,
        [System.Drawing.Color]$SystemColor,
        [string]$ContainerName = $null
    )
    
    # Controls Panel
    $panelLogControls = New-Object System.Windows.Forms.Panel
    $panelLogControls.Dock = [System.Windows.Forms.DockStyle]::Top
    $panelLogControls.Height = 55
    $panelLogControls.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 40)
    $panelLogControls.Padding = New-Object System.Windows.Forms.Padding(15, 10, 15, 10)
    
    # Back to Dashboard Button
    $btnBackToDashboard = New-Object System.Windows.Forms.Button
    $btnBackToDashboard.Text = "< Back to Dashboard"
    $btnBackToDashboard.Location = New-Object System.Drawing.Point(15, 12)
    $btnBackToDashboard.Size = New-Object System.Drawing.Size(150, 32)
    $btnBackToDashboard.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
    $btnBackToDashboard.ForeColor = $script:theme.TextBright
    $btnBackToDashboard.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btnBackToDashboard.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
    $btnBackToDashboard.FlatAppearance.BorderSize = 1
    $btnBackToDashboard.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
    $btnBackToDashboard.Cursor = [System.Windows.Forms.Cursors]::Hand
    $btnBackToDashboard.Add_Click({
        $tabControl.SelectedTab = $tabSystemMonitor
    })
    
    # Follow Mode CheckBox
    $chkFollow = New-Object System.Windows.Forms.CheckBox
    $chkFollow.Text = "Follow log"
    $chkFollow.Location = New-Object System.Drawing.Point(180, 16)
    $chkFollow.BackColor = [System.Drawing.Color]::Transparent
    $chkFollow.ForeColor = $script:theme.Text
    $chkFollow.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    
    # Auto-Scroll CheckBox
    $chkAutoScroll = New-Object System.Windows.Forms.CheckBox
    $chkAutoScroll.Text = "Auto-scroll"
    $chkAutoScroll.Location = New-Object System.Drawing.Point(280, 16)
    $chkAutoScroll.Checked = $true
    $chkAutoScroll.BackColor = [System.Drawing.Color]::Transparent
    $chkAutoScroll.ForeColor = $script:theme.Text
    $chkAutoScroll.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    
    # Search TextBox
    $txtSearch = New-Object System.Windows.Forms.TextBox
    $txtSearch.Location = New-Object System.Drawing.Point(400, 14)
    $txtSearch.Size = New-Object System.Drawing.Size(220, 28)
    $txtSearch.Text = "Search..."
    $txtSearch.BackColor = [System.Drawing.Color]::FromArgb(55, 55, 55)
    $txtSearch.ForeColor = $script:theme.TextDim
    $txtSearch.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
    $txtSearch.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $txtSearch.Add_GotFocus({
        if ($txtSearch.Text -eq "Search...") {
            $txtSearch.Text = ""
            $txtSearch.ForeColor = $script:theme.Text
        }
    })
    $txtSearch.Add_LostFocus({
        if ([string]::IsNullOrWhiteSpace($txtSearch.Text)) {
            $txtSearch.Text = "Search..."
            $txtSearch.ForeColor = $script:theme.TextDim
        }
    })
    
    # Log Level Filter ComboBox
    $cmbLogLevel = New-Object System.Windows.Forms.ComboBox
    $cmbLogLevel.Items.AddRange(@("All", "INFO", "WARN", "ERROR", "SUCCESS"))
    $cmbLogLevel.SelectedIndex = 0
    $cmbLogLevel.Location = New-Object System.Drawing.Point(630, 14)
    $cmbLogLevel.Size = New-Object System.Drawing.Size(110, 28)
    $cmbLogLevel.BackColor = [System.Drawing.Color]::FromArgb(55, 55, 55)
    $cmbLogLevel.ForeColor = $script:theme.Text
    $cmbLogLevel.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $cmbLogLevel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    
    # Clear Button
    $btnClear = New-Object System.Windows.Forms.Button
    $btnClear.Text = "Clear"
    $btnClear.Location = New-Object System.Drawing.Point(750, 12)
    $btnClear.Size = New-Object System.Drawing.Size(80, 32)
    $btnClear.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
    $btnClear.ForeColor = $script:theme.Text
    $btnClear.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btnClear.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
    $btnClear.FlatAppearance.BorderSize = 1
    $btnClear.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $btnClear.Cursor = [System.Windows.Forms.Cursors]::Hand
    
    # Export Button
    $btnExport = New-Object System.Windows.Forms.Button
    $btnExport.Text = "Export"
    $btnExport.Location = New-Object System.Drawing.Point(840, 12)
    $btnExport.Size = New-Object System.Drawing.Size(80, 32)
    $btnExport.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
    $btnExport.ForeColor = $script:theme.Text
    $btnExport.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btnExport.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
    $btnExport.FlatAppearance.BorderSize = 1
    $btnExport.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $btnExport.Cursor = [System.Windows.Forms.Cursors]::Hand
    
    $panelLogControls.Controls.AddRange(@($btnBackToDashboard, $chkFollow, $chkAutoScroll, $txtSearch, $cmbLogLevel, $btnClear, $btnExport))
    
    # RichTextBox for log display
    $richTextBox = New-Object System.Windows.Forms.RichTextBox
    $richTextBox.Dock = [System.Windows.Forms.DockStyle]::Fill
    $richTextBox.Font = New-Object System.Drawing.Font("Consolas", 9.5)
    $richTextBox.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 25)
    $richTextBox.ForeColor = $script:theme.Text
    $richTextBox.ReadOnly = $true
    $richTextBox.WordWrap = $false
    $richTextBox.ScrollBars = [System.Windows.Forms.RichTextBoxScrollBars]::Both
    $richTextBox.BorderStyle = [System.Windows.Forms.BorderStyle]::None
    $richTextBox.Padding = New-Object System.Windows.Forms.Padding(10, 10, 10, 10)
    
    # Event handlers
    $chkFollow.Add_CheckedChanged({
        if ($chkFollow.Checked) {
            if ($ContainerName) {
                Start-DockerLogTailing -ContainerName $ContainerName -RichTextBox $richTextBox -SystemColor $SystemColor
            } else {
                Start-LogTailing -LogFile $LogFile -RichTextBox $richTextBox -SystemColor $SystemColor
            }
        } else {
            if ($ContainerName) {
                Stop-DockerLogTailing -ContainerName $ContainerName
            } else {
                Stop-LogTailing -LogFile $LogFile
            }
        }
    })
    
    $chkAutoScroll.Add_CheckedChanged({
        $script:autoScrollEnabled = $chkAutoScroll.Checked
    })
    
    $btnClear.Add_Click({
        $richTextBox.Clear()
    })
    
    $btnExport.Add_Click({
        $saveDialog = New-Object System.Windows.Forms.SaveFileDialog
        $saveDialog.Filter = "RTF Files (*.rtf)|*.rtf|Text Files (*.txt)|*.txt|All Files (*.*)|*.*"
        $saveDialog.FileName = "log_export.rtf"
        if ($saveDialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            if ($saveDialog.FilterIndex -eq 1) {
                $richTextBox.SaveFile($saveDialog.FileName, [System.Windows.Forms.RichTextBoxStreamType]::RichText)
            } else {
                $richTextBox.SaveFile($saveDialog.FileName, [System.Windows.Forms.RichTextBoxStreamType]::PlainText)
            }
        }
    })
    
    # Load initial log content
    if ($ContainerName) {
        Load-DockerLogs -ContainerName $ContainerName -RichTextBox $richTextBox
    } else {
        if (Test-Path $LogFile) {
            $lines = Get-Content $LogFile -Tail 5000 -ErrorAction SilentlyContinue
            $richTextBox.SuspendLayout()
            $richTextBox.Clear()
            foreach ($line in $lines) {
                Add-LogLine -RichTextBox $richTextBox -Line $line -SystemColor $SystemColor
            }
            $richTextBox.ResumeLayout()
            $richTextBox.SelectionStart = $richTextBox.TextLength
            $richTextBox.ScrollToCaret()
        } else {
            $richTextBox.Text = "Log file not found: $LogFile"
        }
    }
    
    $TabPage.Controls.AddRange(@($richTextBox, $panelLogControls))
    
    # Return controls for later reference
    return @{
        RichTextBox = $richTextBox
        ChkFollow = $chkFollow
        ChkAutoScroll = $chkAutoScroll
        TxtSearch = $txtSearch
        CmbLogLevel = $cmbLogLevel
        BtnClear = $btnClear
        BtnExport = $btnExport
    }
}

# Create log tabs
$monitorLogControls = Create-LogTab -TabPage $tabMonitorLog -LogFile "D:\Project-Kylo\.kylo\monitor.log" -SystemColor $script:theme.Systems.SystemMonitor.Primary
$watcherLogControls = Create-LogTab -TabPage $tabWatcherLog -LogFile "D:\Project-Kylo\.kylo\watch.log" -SystemColor $script:theme.Systems.Watcher.Primary
$scriptHubSyncLogControls = Create-LogTab -TabPage $tabScriptHubSyncLogs -LogFile "D:\Project-Kylo\tools\scripthub_legacy\logs\sync_log_*.log" -SystemColor $script:theme.Systems.ScriptHubSync.Primary
$postgreSQLLogControls = Create-LogTab -TabPage $tabPostgreSQLLogs -ContainerName "kylo-pg" -SystemColor $script:theme.Systems.PostgreSQL.Primary
$redpandaLogControls = Create-LogTab -TabPage $tabRedpandaLogs -ContainerName "kylo-redpanda" -SystemColor $script:theme.Systems.Redpanda.Primary
$kafkaTxnsLogControls = Create-LogTab -TabPage $tabKafkaTxnsLogs -ContainerName "kylo-kafka-consumer-txns" -SystemColor $script:theme.Systems.KafkaConsumer.Primary
$kafkaPromoteLogControls = Create-LogTab -TabPage $tabKafkaPromoteLogs -ContainerName "kylo-kafka-consumer-promote" -SystemColor $script:theme.Systems.KafkaConsumer.Primary

$tabLogViewer.TabPages.AddRange(@($tabMonitorLog, $tabWatcherLog, $tabScriptHubSyncLogs, $tabPostgreSQLLogs, $tabRedpandaLogs, $tabKafkaTxnsLogs, $tabKafkaPromoteLogs))

$tabLogViewerPage = New-Object System.Windows.Forms.TabPage
$tabLogViewerPage.Text = "Log Viewer"
$tabLogViewerPage.Controls.Add($tabLogViewer)
$tabControl.TabPages.Add($tabLogViewerPage)

# ============================================================================
# SERVICE CONTROLS TAB
# ============================================================================

$tabServiceControls = New-Object System.Windows.Forms.TabPage
$tabServiceControls.Text = "Service Controls"
$tabServiceControls.BackColor = $script:theme.Background
$tabServiceControls.UseVisualStyleBackColor = $false

# Scrollable panel for all controls
$scrollPanel = New-Object System.Windows.Forms.Panel
$scrollPanel.Dock = [System.Windows.Forms.DockStyle]::Fill
$scrollPanel.AutoScroll = $true
$scrollPanel.BackColor = $script:theme.Background

# Docker Services GroupBox
$grpDockerServices = New-Object System.Windows.Forms.GroupBox
$grpDockerServices.Text = "Docker Services"
$grpDockerServices.Location = New-Object System.Drawing.Point(15, 15)
$grpDockerServices.Size = New-Object System.Drawing.Size(1350, 220)
$grpDockerServices.BackColor = [System.Drawing.Color]::FromArgb(50, 50, 50)
$grpDockerServices.ForeColor = $script:theme.TextBright
$grpDockerServices.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$grpDockerServices.Padding = New-Object System.Windows.Forms.Padding(15, 25, 15, 15)

# Start All Button
$btnStartAllDocker = New-Object System.Windows.Forms.Button
$btnStartAllDocker.Text = "Start All"
$btnStartAllDocker.Location = New-Object System.Drawing.Point(15, 30)
$btnStartAllDocker.Size = New-Object System.Drawing.Size(120, 38)
$btnStartAllDocker.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnStartAllDocker.ForeColor = $script:theme.Status.Running
$btnStartAllDocker.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnStartAllDocker.FlatAppearance.BorderColor = $script:theme.Status.Running
$btnStartAllDocker.FlatAppearance.BorderSize = 1
$btnStartAllDocker.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$btnStartAllDocker.Cursor = [System.Windows.Forms.Cursors]::Hand

# Stop All Button
$btnStopAllDocker = New-Object System.Windows.Forms.Button
$btnStopAllDocker.Text = "Stop All"
$btnStopAllDocker.Location = New-Object System.Drawing.Point(145, 30)
$btnStopAllDocker.Size = New-Object System.Drawing.Size(120, 38)
$btnStopAllDocker.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnStopAllDocker.ForeColor = $script:theme.Status.Error
$btnStopAllDocker.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnStopAllDocker.FlatAppearance.BorderColor = $script:theme.Status.Error
$btnStopAllDocker.FlatAppearance.BorderSize = 1
$btnStopAllDocker.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$btnStopAllDocker.Cursor = [System.Windows.Forms.Cursors]::Hand

# Restart All Button
$btnRestartAllDocker = New-Object System.Windows.Forms.Button
$btnRestartAllDocker.Text = "Restart All"
$btnRestartAllDocker.Location = New-Object System.Drawing.Point(275, 30)
$btnRestartAllDocker.Size = New-Object System.Drawing.Size(120, 38)
$btnRestartAllDocker.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRestartAllDocker.ForeColor = $script:theme.Status.Warning
$btnRestartAllDocker.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRestartAllDocker.FlatAppearance.BorderColor = $script:theme.Status.Warning
$btnRestartAllDocker.FlatAppearance.BorderSize = 1
$btnRestartAllDocker.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$btnRestartAllDocker.Cursor = [System.Windows.Forms.Cursors]::Hand

# Progress Bar
$progressBarDocker = New-Object System.Windows.Forms.ProgressBar
$progressBarDocker.Location = New-Object System.Drawing.Point(10, 70)
$progressBarDocker.Size = New-Object System.Drawing.Size(780, 20)
$progressBarDocker.Visible = $false

$grpDockerServices.Controls.AddRange(@($btnStartAllDocker, $btnStopAllDocker, $btnRestartAllDocker, $progressBarDocker))

# Individual service controls will be added dynamically
$yPos = 100
$services = @(
    @{ Name = "PostgreSQL"; Container = "kylo-pg"; ComposeFile = "docker-compose.yml" },
    @{ Name = "Redpanda"; Container = "kylo-redpanda"; ComposeFile = "docker-compose.kafka.yml" },
    @{ Name = "Kafka Consumer Txns"; Container = "kylo-kafka-consumer-txns"; ComposeFile = "docker-compose.kafka-consumer.yml" },
    @{ Name = "Kafka Consumer Promote"; Container = "kylo-kafka-consumer-promote"; ComposeFile = "docker-compose.kafka-consumer.yml" }
)

foreach ($service in $services) {
    $lblService = New-Object System.Windows.Forms.Label
    $lblService.Text = $service.Name
    $lblService.Location = New-Object System.Drawing.Point(15, $yPos)
    $lblService.Size = New-Object System.Drawing.Size(200, 24)
    $lblService.ForeColor = $script:theme.TextBright
    $lblService.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    
    $btnStart = New-Object System.Windows.Forms.Button
    $btnStart.Text = "Start"
    $btnStart.Location = New-Object System.Drawing.Point(220, ($yPos - 5))
    $btnStart.Size = New-Object System.Drawing.Size(90, 32)
    $btnStart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
    $btnStart.ForeColor = $script:theme.Status.Running
    $btnStart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btnStart.FlatAppearance.BorderColor = $script:theme.Status.Running
    $btnStart.FlatAppearance.BorderSize = 1
    $btnStart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $btnStart.Cursor = [System.Windows.Forms.Cursors]::Hand
    $btnStart.Tag = $service
    $btnStart.Add_Click({
        $svc = $this.Tag
        $result = Start-DockerService -ServiceName $svc.Container -ComposeFile $svc.ComposeFile
        if ($result.Success) {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Success", "OK", "Information")
        } else {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
        }
        Update-AllSystemCards
    })
    
    $btnStop = New-Object System.Windows.Forms.Button
    $btnStop.Text = "Stop"
    $btnStop.Location = New-Object System.Drawing.Point(320, ($yPos - 5))
    $btnStop.Size = New-Object System.Drawing.Size(90, 32)
    $btnStop.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
    $btnStop.ForeColor = $script:theme.Status.Error
    $btnStop.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btnStop.FlatAppearance.BorderColor = $script:theme.Status.Error
    $btnStop.FlatAppearance.BorderSize = 1
    $btnStop.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $btnStop.Cursor = [System.Windows.Forms.Cursors]::Hand
    $btnStop.Tag = $service
    $btnStop.Add_Click({
        $svc = $this.Tag
        $result = Stop-DockerService -ServiceName $svc.Container
        if ($result.Success) {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Success", "OK", "Information")
        } else {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
        }
        Update-AllSystemCards
    })
    
    $btnRestart = New-Object System.Windows.Forms.Button
    $btnRestart.Text = "Restart"
    $btnRestart.Location = New-Object System.Drawing.Point(420, ($yPos - 5))
    $btnRestart.Size = New-Object System.Drawing.Size(100, 32)
    $btnRestart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
    $btnRestart.ForeColor = $script:theme.Status.Warning
    $btnRestart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $btnRestart.FlatAppearance.BorderColor = $script:theme.Status.Warning
    $btnRestart.FlatAppearance.BorderSize = 1
    $btnRestart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $btnRestart.Cursor = [System.Windows.Forms.Cursors]::Hand
    $btnRestart.Tag = $service
    $btnRestart.Add_Click({
        $svc = $this.Tag
        $result = Restart-DockerService -ServiceName $svc.Container -ComposeFile $svc.ComposeFile
        if ($result.Success) {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Success", "OK", "Information")
        } else {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
        }
        Update-AllSystemCards
    })
    
    $grpDockerServices.Controls.AddRange(@($lblService, $btnStart, $btnStop, $btnRestart))
    $yPos += 35
}

# Process Services GroupBox
$grpProcessServices = New-Object System.Windows.Forms.GroupBox
$grpProcessServices.Text = "Process Services"
$grpProcessServices.Location = New-Object System.Drawing.Point(15, 245)
$grpProcessServices.Size = New-Object System.Drawing.Size(1350, 110)
$grpProcessServices.BackColor = [System.Drawing.Color]::FromArgb(50, 50, 50)
$grpProcessServices.ForeColor = $script:theme.TextBright
$grpProcessServices.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$grpProcessServices.Padding = New-Object System.Windows.Forms.Padding(15, 25, 15, 15)

$lblWatcher = New-Object System.Windows.Forms.Label
$lblWatcher.Text = "Watcher Service"
$lblWatcher.Location = New-Object System.Drawing.Point(15, 30)
$lblWatcher.Size = New-Object System.Drawing.Size(200, 24)
$lblWatcher.ForeColor = $script:theme.TextBright
$lblWatcher.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$btnStartWatcher = New-Object System.Windows.Forms.Button
$btnStartWatcher.Text = "Start"
$btnStartWatcher.Location = New-Object System.Drawing.Point(220, 22)
$btnStartWatcher.Size = New-Object System.Drawing.Size(100, 35)
$btnStartWatcher.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnStartWatcher.ForeColor = $script:theme.Status.Running
$btnStartWatcher.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnStartWatcher.FlatAppearance.BorderColor = $script:theme.Status.Running
$btnStartWatcher.FlatAppearance.BorderSize = 1
$btnStartWatcher.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnStartWatcher.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnStopWatcher = New-Object System.Windows.Forms.Button
$btnStopWatcher.Text = "Stop"
$btnStopWatcher.Location = New-Object System.Drawing.Point(330, 22)
$btnStopWatcher.Size = New-Object System.Drawing.Size(100, 35)
$btnStopWatcher.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnStopWatcher.ForeColor = $script:theme.Status.Error
$btnStopWatcher.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnStopWatcher.FlatAppearance.BorderColor = $script:theme.Status.Error
$btnStopWatcher.FlatAppearance.BorderSize = 1
$btnStopWatcher.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnStopWatcher.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnRestartWatcher = New-Object System.Windows.Forms.Button
$btnRestartWatcher.Text = "Restart"
$btnRestartWatcher.Location = New-Object System.Drawing.Point(440, 22)
$btnRestartWatcher.Size = New-Object System.Drawing.Size(100, 35)
$btnRestartWatcher.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRestartWatcher.ForeColor = $script:theme.Status.Warning
$btnRestartWatcher.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRestartWatcher.FlatAppearance.BorderColor = $script:theme.Status.Warning
$btnRestartWatcher.FlatAppearance.BorderSize = 1
$btnRestartWatcher.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnRestartWatcher.Cursor = [System.Windows.Forms.Cursors]::Hand

$grpProcessServices.Controls.AddRange(@($lblWatcher, $btnStartWatcher, $btnStopWatcher, $btnRestartWatcher))

# ScriptHub Sync GroupBox
$grpScriptHubSync = New-Object System.Windows.Forms.GroupBox
$grpScriptHubSync.Text = "ScriptHub Sync"
$grpScriptHubSync.Location = New-Object System.Drawing.Point(15, 365)
$grpScriptHubSync.Size = New-Object System.Drawing.Size(1350, 170)
$grpScriptHubSync.BackColor = [System.Drawing.Color]::FromArgb(50, 50, 50)
$grpScriptHubSync.ForeColor = $script:theme.TextBright
$grpScriptHubSync.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$grpScriptHubSync.Padding = New-Object System.Windows.Forms.Padding(15, 25, 15, 15)

$btnRunSyncNow = New-Object System.Windows.Forms.Button
$btnRunSyncNow.Text = "Run Sync Now"
$btnRunSyncNow.Location = New-Object System.Drawing.Point(15, 30)
$btnRunSyncNow.Size = New-Object System.Drawing.Size(140, 38)
$btnRunSyncNow.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRunSyncNow.ForeColor = $script:theme.Systems.ScriptHubSync.Primary
$btnRunSyncNow.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRunSyncNow.FlatAppearance.BorderColor = $script:theme.Systems.ScriptHubSync.Primary
$btnRunSyncNow.FlatAppearance.BorderSize = 1
$btnRunSyncNow.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$btnRunSyncNow.Cursor = [System.Windows.Forms.Cursors]::Hand

$txtSyncResult = New-Object System.Windows.Forms.TextBox
$txtSyncResult.Location = New-Object System.Drawing.Point(15, 75)
$txtSyncResult.Size = New-Object System.Drawing.Size(1320, 80)
$txtSyncResult.Multiline = $true
$txtSyncResult.ReadOnly = $true
$txtSyncResult.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$txtSyncResult.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30)
$txtSyncResult.ForeColor = $script:theme.Text
$txtSyncResult.Font = New-Object System.Drawing.Font("Consolas", 8.5)
$txtSyncResult.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle

$grpScriptHubSync.Controls.AddRange(@($btnRunSyncNow, $txtSyncResult))

# System Monitor GroupBox
$grpSystemMonitor = New-Object System.Windows.Forms.GroupBox
$grpSystemMonitor.Text = "System Monitor"
$grpSystemMonitor.Location = New-Object System.Drawing.Point(15, 545)
$grpSystemMonitor.Size = New-Object System.Drawing.Size(1350, 110)
$grpSystemMonitor.BackColor = [System.Drawing.Color]::FromArgb(50, 50, 50)
$grpSystemMonitor.ForeColor = $script:theme.TextBright
$grpSystemMonitor.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$grpSystemMonitor.Padding = New-Object System.Windows.Forms.Padding(15, 25, 15, 15)

$btnStartMonitor = New-Object System.Windows.Forms.Button
$btnStartMonitor.Text = "Start Monitor"
$btnStartMonitor.Location = New-Object System.Drawing.Point(15, 30)
$btnStartMonitor.Size = New-Object System.Drawing.Size(130, 38)
$btnStartMonitor.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnStartMonitor.ForeColor = $script:theme.Status.Running
$btnStartMonitor.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnStartMonitor.FlatAppearance.BorderColor = $script:theme.Status.Running
$btnStartMonitor.FlatAppearance.BorderSize = 1
$btnStartMonitor.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnStartMonitor.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnStopMonitor = New-Object System.Windows.Forms.Button
$btnStopMonitor.Text = "Stop Monitor"
$btnStopMonitor.Location = New-Object System.Drawing.Point(155, 30)
$btnStopMonitor.Size = New-Object System.Drawing.Size(130, 38)
$btnStopMonitor.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnStopMonitor.ForeColor = $script:theme.Status.Error
$btnStopMonitor.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnStopMonitor.FlatAppearance.BorderColor = $script:theme.Status.Error
$btnStopMonitor.FlatAppearance.BorderSize = 1
$btnStopMonitor.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnStopMonitor.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnRestartMonitor = New-Object System.Windows.Forms.Button
$btnRestartMonitor.Text = "Restart Monitor"
$btnRestartMonitor.Location = New-Object System.Drawing.Point(295, 30)
$btnRestartMonitor.Size = New-Object System.Drawing.Size(140, 38)
$btnRestartMonitor.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRestartMonitor.ForeColor = $script:theme.Status.Warning
$btnRestartMonitor.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRestartMonitor.FlatAppearance.BorderColor = $script:theme.Status.Warning
$btnRestartMonitor.FlatAppearance.BorderSize = 1
$btnRestartMonitor.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnRestartMonitor.Cursor = [System.Windows.Forms.Cursors]::Hand

$grpSystemMonitor.Controls.AddRange(@($btnStartMonitor, $btnStopMonitor, $btnRestartMonitor))

$scrollPanel.Controls.AddRange(@($grpDockerServices, $grpProcessServices, $grpScriptHubSync, $grpSystemMonitor))
$tabServiceControls.Controls.Add($scrollPanel)
$tabControl.TabPages.Add($tabServiceControls)

# ============================================================================
# SYSTEM STATUS CARDS CREATION
# ============================================================================

function Create-SystemCard {
    param(
        [string]$SystemName,
        [string]$CardName,
        [System.Drawing.Color]$SystemColor,
        [scriptblock]$GetStatusFunction,
        [scriptblock]$UpdateCardFunction
    )
    
    $card = New-Object System.Windows.Forms.Panel
    $card.Name = $CardName
    $card.Size = New-Object System.Drawing.Size(400, 300)
    $card.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
    $card.BackColor = [System.Drawing.Color]::FromArgb(50, 50, 50)
    $card.Padding = New-Object System.Windows.Forms.Padding(15, 15, 15, 15)
    $card.Margin = New-Object System.Windows.Forms.Padding(10, 10, 10, 10)
    
    Apply-SystemCardTheme -CardPanel $card -SystemName $SystemName
    
    # Header Label
    $lblHeader = New-Object System.Windows.Forms.Label
    $lblHeader.Name = "lbl${CardName}Header"
    $lblHeader.Text = $SystemName
    $lblHeader.Font = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
    $lblHeader.ForeColor = $SystemColor
    $lblHeader.Location = New-Object System.Drawing.Point(15, 15)
    $lblHeader.Size = New-Object System.Drawing.Size(370, 28)
    
    # Status Label
    $lblStatus = New-Object System.Windows.Forms.Label
    $lblStatus.Name = "lbl${CardName}Status"
    $lblStatus.Text = "Status: Checking..."
    $lblStatus.Location = New-Object System.Drawing.Point(15, 48)
    $lblStatus.Size = New-Object System.Drawing.Size(370, 22)
    $lblStatus.ForeColor = $script:theme.Text
    $lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    
    # Additional labels will be added by specific card creation functions
    $card.Controls.AddRange(@($lblHeader, $lblStatus))
    
    # Store update function in tag
    $card.Tag = @{
        GetStatus = $GetStatusFunction
        UpdateCard = $UpdateCardFunction
        SystemName = $SystemName
    }
    
    return $card
}

# Create all system cards
$cardPostgreSQL = Create-SystemCard -SystemName "PostgreSQL" -CardName "PostgreSQL" -SystemColor $script:theme.Systems.PostgreSQL.Primary `
    -GetStatusFunction { Get-PostgreSQLStatus } `
    -UpdateCardFunction {
        param($status)
        $lblPostgreSQLStatus.Text = "Status: $($status.Status)"
        if ($status.Running) {
            $lblPostgreSQLStatus.ForeColor = $script:theme.Status.Running
        } elseif ($status.Error) {
            $lblPostgreSQLStatus.ForeColor = $script:theme.Status.Error
        } else {
            $lblPostgreSQLStatus.ForeColor = $script:theme.Status.Unknown
        }
    }

# Add PostgreSQL card specific labels
$lblPostgreSQLHealth = New-Object System.Windows.Forms.Label
$lblPostgreSQLHealth.Name = "lblPostgreSQLHealth"
$lblPostgreSQLHealth.Location = New-Object System.Drawing.Point(15, 75)
$lblPostgreSQLHealth.Size = New-Object System.Drawing.Size(370, 22)
$lblPostgreSQLHealth.ForeColor = $script:theme.Text
$lblPostgreSQLHealth.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblPostgreSQLUptime = New-Object System.Windows.Forms.Label
$lblPostgreSQLUptime.Name = "lblPostgreSQLUptime"
$lblPostgreSQLUptime.Location = New-Object System.Drawing.Point(15, 102)
$lblPostgreSQLUptime.Size = New-Object System.Drawing.Size(370, 22)
$lblPostgreSQLUptime.ForeColor = $script:theme.Text
$lblPostgreSQLUptime.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblPostgreSQLPort = New-Object System.Windows.Forms.Label
$lblPostgreSQLPort.Name = "lblPostgreSQLPort"
$lblPostgreSQLPort.Text = "Port: 5433"
$lblPostgreSQLPort.Location = New-Object System.Drawing.Point(15, 129)
$lblPostgreSQLPort.Size = New-Object System.Drawing.Size(370, 22)
$lblPostgreSQLPort.ForeColor = $script:theme.TextDim
$lblPostgreSQLPort.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$lblPostgreSQLLastCheck = New-Object System.Windows.Forms.Label
$lblPostgreSQLLastCheck.Name = "lblPostgreSQLLastCheck"
$lblPostgreSQLLastCheck.Location = New-Object System.Drawing.Point(15, 156)
$lblPostgreSQLLastCheck.Size = New-Object System.Drawing.Size(370, 22)
$lblPostgreSQLLastCheck.ForeColor = $script:theme.TextDim
$lblPostgreSQLLastCheck.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$btnPostgreSQLLogs = New-Object System.Windows.Forms.Button
$btnPostgreSQLLogs.Text = "View Logs"
$btnPostgreSQLLogs.Location = New-Object System.Drawing.Point(15, 240)
$btnPostgreSQLLogs.Size = New-Object System.Drawing.Size(120, 35)
$btnPostgreSQLLogs.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnPostgreSQLLogs.ForeColor = $script:theme.Systems.PostgreSQL.Primary
$btnPostgreSQLLogs.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnPostgreSQLLogs.FlatAppearance.BorderColor = $script:theme.Systems.PostgreSQL.Primary
$btnPostgreSQLLogs.FlatAppearance.BorderSize = 1
$btnPostgreSQLLogs.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnPostgreSQLLogs.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnPostgreSQLRestart = New-Object System.Windows.Forms.Button
$btnPostgreSQLRestart.Text = "Restart"
$btnPostgreSQLRestart.Location = New-Object System.Drawing.Point(145, 240)
$btnPostgreSQLRestart.Size = New-Object System.Drawing.Size(110, 35)
$btnPostgreSQLRestart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnPostgreSQLRestart.ForeColor = $script:theme.Systems.PostgreSQL.Primary
$btnPostgreSQLRestart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnPostgreSQLRestart.FlatAppearance.BorderColor = $script:theme.Systems.PostgreSQL.Primary
$btnPostgreSQLRestart.FlatAppearance.BorderSize = 1
$btnPostgreSQLRestart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnPostgreSQLRestart.Cursor = [System.Windows.Forms.Cursors]::Hand

$cardPostgreSQL.Controls.AddRange(@($lblPostgreSQLHealth, $lblPostgreSQLUptime, $lblPostgreSQLPort, $lblPostgreSQLLastCheck, $btnPostgreSQLLogs, $btnPostgreSQLRestart))

# Redpanda Card
$cardRedpanda = Create-SystemCard -SystemName "Redpanda" -CardName "Redpanda" -SystemColor $script:theme.Systems.Redpanda.Primary `
    -GetStatusFunction { Get-RedpandaStatus } `
    -UpdateCardFunction { param($status) }

$lblRedpandaHealth = New-Object System.Windows.Forms.Label
$lblRedpandaHealth.Name = "lblRedpandaHealth"
$lblRedpandaHealth.Location = New-Object System.Drawing.Point(15, 75)
$lblRedpandaHealth.Size = New-Object System.Drawing.Size(370, 22)
$lblRedpandaHealth.ForeColor = $script:theme.Text
$lblRedpandaHealth.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblRedpandaUptime = New-Object System.Windows.Forms.Label
$lblRedpandaUptime.Name = "lblRedpandaUptime"
$lblRedpandaUptime.Location = New-Object System.Drawing.Point(15, 102)
$lblRedpandaUptime.Size = New-Object System.Drawing.Size(370, 22)
$lblRedpandaUptime.ForeColor = $script:theme.Text
$lblRedpandaUptime.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblRedpandaPorts = New-Object System.Windows.Forms.Label
$lblRedpandaPorts.Name = "lblRedpandaPorts"
$lblRedpandaPorts.Text = "Ports: 9092, 9644"
$lblRedpandaPorts.Location = New-Object System.Drawing.Point(15, 129)
$lblRedpandaPorts.Size = New-Object System.Drawing.Size(370, 22)
$lblRedpandaPorts.ForeColor = $script:theme.TextDim
$lblRedpandaPorts.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$lblRedpandaLastCheck = New-Object System.Windows.Forms.Label
$lblRedpandaLastCheck.Name = "lblRedpandaLastCheck"
$lblRedpandaLastCheck.Location = New-Object System.Drawing.Point(15, 156)
$lblRedpandaLastCheck.Size = New-Object System.Drawing.Size(370, 22)
$lblRedpandaLastCheck.ForeColor = $script:theme.TextDim
$lblRedpandaLastCheck.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$btnRedpandaLogs = New-Object System.Windows.Forms.Button
$btnRedpandaLogs.Text = "View Logs"
$btnRedpandaLogs.Location = New-Object System.Drawing.Point(15, 240)
$btnRedpandaLogs.Size = New-Object System.Drawing.Size(120, 35)
$btnRedpandaLogs.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRedpandaLogs.ForeColor = $script:theme.Systems.Redpanda.Primary
$btnRedpandaLogs.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRedpandaLogs.FlatAppearance.BorderColor = $script:theme.Systems.Redpanda.Primary
$btnRedpandaLogs.FlatAppearance.BorderSize = 1
$btnRedpandaLogs.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnRedpandaLogs.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnRedpandaRestart = New-Object System.Windows.Forms.Button
$btnRedpandaRestart.Text = "Restart"
$btnRedpandaRestart.Location = New-Object System.Drawing.Point(145, 240)
$btnRedpandaRestart.Size = New-Object System.Drawing.Size(110, 35)
$btnRedpandaRestart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnRedpandaRestart.ForeColor = $script:theme.Systems.Redpanda.Primary
$btnRedpandaRestart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnRedpandaRestart.FlatAppearance.BorderColor = $script:theme.Systems.Redpanda.Primary
$btnRedpandaRestart.FlatAppearance.BorderSize = 1
$btnRedpandaRestart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnRedpandaRestart.Cursor = [System.Windows.Forms.Cursors]::Hand

$cardRedpanda.Controls.AddRange(@($lblRedpandaHealth, $lblRedpandaUptime, $lblRedpandaPorts, $lblRedpandaLastCheck, $btnRedpandaLogs, $btnRedpandaRestart))

# Kafka Consumer Txns Card
$cardKafkaTxns = Create-SystemCard -SystemName "KafkaConsumer" -CardName "KafkaTxns" -SystemColor $script:theme.Systems.KafkaConsumer.Primary `
    -GetStatusFunction { Get-KafkaConsumerStatus -ContainerName "kylo-kafka-consumer-txns" } `
    -UpdateCardFunction { param($status) }

$lblKafkaTxnsStatus = $cardKafkaTxns.Controls | Where-Object { $_.Name -eq "lblKafkaTxnsStatus" } | Select-Object -First 1
$lblKafkaTxnsTopic = New-Object System.Windows.Forms.Label
$lblKafkaTxnsTopic.Name = "lblKafkaTxnsTopic"
$lblKafkaTxnsTopic.Text = "Topic: txns.company.batches"
$lblKafkaTxnsTopic.Location = New-Object System.Drawing.Point(15, 75)
$lblKafkaTxnsTopic.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaTxnsTopic.ForeColor = $script:theme.Text
$lblKafkaTxnsTopic.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblKafkaTxnsMessages = New-Object System.Windows.Forms.Label
$lblKafkaTxnsMessages.Name = "lblKafkaTxnsMessages"
$lblKafkaTxnsMessages.Location = New-Object System.Drawing.Point(15, 102)
$lblKafkaTxnsMessages.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaTxnsMessages.ForeColor = $script:theme.Text
$lblKafkaTxnsMessages.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblKafkaTxnsUptime = New-Object System.Windows.Forms.Label
$lblKafkaTxnsUptime.Name = "lblKafkaTxnsUptime"
$lblKafkaTxnsUptime.Location = New-Object System.Drawing.Point(15, 129)
$lblKafkaTxnsUptime.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaTxnsUptime.ForeColor = $script:theme.Text
$lblKafkaTxnsUptime.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblKafkaTxnsLastCheck = New-Object System.Windows.Forms.Label
$lblKafkaTxnsLastCheck.Name = "lblKafkaTxnsLastCheck"
$lblKafkaTxnsLastCheck.Location = New-Object System.Drawing.Point(15, 156)
$lblKafkaTxnsLastCheck.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaTxnsLastCheck.ForeColor = $script:theme.TextDim
$lblKafkaTxnsLastCheck.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$btnKafkaTxnsLogs = New-Object System.Windows.Forms.Button
$btnKafkaTxnsLogs.Text = "View Logs"
$btnKafkaTxnsLogs.Location = New-Object System.Drawing.Point(15, 240)
$btnKafkaTxnsLogs.Size = New-Object System.Drawing.Size(120, 35)
$btnKafkaTxnsLogs.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnKafkaTxnsLogs.ForeColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaTxnsLogs.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnKafkaTxnsLogs.FlatAppearance.BorderColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaTxnsLogs.FlatAppearance.BorderSize = 1
$btnKafkaTxnsLogs.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnKafkaTxnsLogs.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnKafkaTxnsRestart = New-Object System.Windows.Forms.Button
$btnKafkaTxnsRestart.Text = "Restart"
$btnKafkaTxnsRestart.Location = New-Object System.Drawing.Point(145, 240)
$btnKafkaTxnsRestart.Size = New-Object System.Drawing.Size(110, 35)
$btnKafkaTxnsRestart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnKafkaTxnsRestart.ForeColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaTxnsRestart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnKafkaTxnsRestart.FlatAppearance.BorderColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaTxnsRestart.FlatAppearance.BorderSize = 1
$btnKafkaTxnsRestart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnKafkaTxnsRestart.Cursor = [System.Windows.Forms.Cursors]::Hand

$cardKafkaTxns.Controls.AddRange(@($lblKafkaTxnsTopic, $lblKafkaTxnsMessages, $lblKafkaTxnsUptime, $lblKafkaTxnsLastCheck, $btnKafkaTxnsLogs, $btnKafkaTxnsRestart))

# Kafka Consumer Promote Card
$cardKafkaPromote = Create-SystemCard -SystemName "KafkaConsumer" -CardName "KafkaPromote" -SystemColor $script:theme.Systems.KafkaConsumer.Primary `
    -GetStatusFunction { Get-KafkaConsumerStatus -ContainerName "kylo-kafka-consumer-promote" } `
    -UpdateCardFunction { param($status) }

$lblKafkaPromoteTopic = New-Object System.Windows.Forms.Label
$lblKafkaPromoteTopic.Name = "lblKafkaPromoteTopic"
$lblKafkaPromoteTopic.Text = "Topic: rules.promote.batches"
$lblKafkaPromoteTopic.Location = New-Object System.Drawing.Point(15, 75)
$lblKafkaPromoteTopic.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaPromoteTopic.ForeColor = $script:theme.Text
$lblKafkaPromoteTopic.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblKafkaPromoteMessages = New-Object System.Windows.Forms.Label
$lblKafkaPromoteMessages.Name = "lblKafkaPromoteMessages"
$lblKafkaPromoteMessages.Location = New-Object System.Drawing.Point(15, 102)
$lblKafkaPromoteMessages.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaPromoteMessages.ForeColor = $script:theme.Text
$lblKafkaPromoteMessages.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblKafkaPromoteUptime = New-Object System.Windows.Forms.Label
$lblKafkaPromoteUptime.Name = "lblKafkaPromoteUptime"
$lblKafkaPromoteUptime.Location = New-Object System.Drawing.Point(15, 129)
$lblKafkaPromoteUptime.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaPromoteUptime.ForeColor = $script:theme.Text
$lblKafkaPromoteUptime.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblKafkaPromoteLastCheck = New-Object System.Windows.Forms.Label
$lblKafkaPromoteLastCheck.Name = "lblKafkaPromoteLastCheck"
$lblKafkaPromoteLastCheck.Location = New-Object System.Drawing.Point(15, 156)
$lblKafkaPromoteLastCheck.Size = New-Object System.Drawing.Size(370, 22)
$lblKafkaPromoteLastCheck.ForeColor = $script:theme.TextDim
$lblKafkaPromoteLastCheck.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$btnKafkaPromoteLogs = New-Object System.Windows.Forms.Button
$btnKafkaPromoteLogs.Text = "View Logs"
$btnKafkaPromoteLogs.Location = New-Object System.Drawing.Point(15, 240)
$btnKafkaPromoteLogs.Size = New-Object System.Drawing.Size(120, 35)
$btnKafkaPromoteLogs.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnKafkaPromoteLogs.ForeColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaPromoteLogs.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnKafkaPromoteLogs.FlatAppearance.BorderColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaPromoteLogs.FlatAppearance.BorderSize = 1
$btnKafkaPromoteLogs.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnKafkaPromoteLogs.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnKafkaPromoteRestart = New-Object System.Windows.Forms.Button
$btnKafkaPromoteRestart.Text = "Restart"
$btnKafkaPromoteRestart.Location = New-Object System.Drawing.Point(145, 240)
$btnKafkaPromoteRestart.Size = New-Object System.Drawing.Size(110, 35)
$btnKafkaPromoteRestart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnKafkaPromoteRestart.ForeColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaPromoteRestart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnKafkaPromoteRestart.FlatAppearance.BorderColor = $script:theme.Systems.KafkaConsumer.Primary
$btnKafkaPromoteRestart.FlatAppearance.BorderSize = 1
$btnKafkaPromoteRestart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnKafkaPromoteRestart.Cursor = [System.Windows.Forms.Cursors]::Hand

$cardKafkaPromote.Controls.AddRange(@($lblKafkaPromoteTopic, $lblKafkaPromoteMessages, $lblKafkaPromoteUptime, $lblKafkaPromoteLastCheck, $btnKafkaPromoteLogs, $btnKafkaPromoteRestart))

# Watcher Service Card
$cardWatcher = Create-SystemCard -SystemName "Watcher" -CardName "Watcher" -SystemColor $script:theme.Systems.Watcher.Primary `
    -GetStatusFunction { Get-WatcherStatus } `
    -UpdateCardFunction { param($status) }

$lblWatcherPID = New-Object System.Windows.Forms.Label
$lblWatcherPID.Name = "lblWatcherPID"
$lblWatcherPID.Location = New-Object System.Drawing.Point(15, 75)
$lblWatcherPID.Size = New-Object System.Drawing.Size(370, 22)
$lblWatcherPID.ForeColor = $script:theme.Text
$lblWatcherPID.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblWatcherInterval = New-Object System.Windows.Forms.Label
$lblWatcherInterval.Name = "lblWatcherInterval"
$lblWatcherInterval.Location = New-Object System.Drawing.Point(15, 102)
$lblWatcherInterval.Size = New-Object System.Drawing.Size(370, 22)
$lblWatcherInterval.ForeColor = $script:theme.Text
$lblWatcherInterval.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblWatcherCompanies = New-Object System.Windows.Forms.Label
$lblWatcherCompanies.Name = "lblWatcherCompanies"
$lblWatcherCompanies.Location = New-Object System.Drawing.Point(15, 129)
$lblWatcherCompanies.Size = New-Object System.Drawing.Size(370, 22)
$lblWatcherCompanies.ForeColor = $script:theme.Text
$lblWatcherCompanies.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblWatcherLastActivity = New-Object System.Windows.Forms.Label
$lblWatcherLastActivity.Name = "lblWatcherLastActivity"
$lblWatcherLastActivity.Location = New-Object System.Drawing.Point(15, 156)
$lblWatcherLastActivity.Size = New-Object System.Drawing.Size(370, 22)
$lblWatcherLastActivity.ForeColor = $script:theme.TextDim
$lblWatcherLastActivity.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$btnWatcherLogs = New-Object System.Windows.Forms.Button
$btnWatcherLogs.Text = "View Logs"
$btnWatcherLogs.Location = New-Object System.Drawing.Point(15, 240)
$btnWatcherLogs.Size = New-Object System.Drawing.Size(120, 35)
$btnWatcherLogs.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnWatcherLogs.ForeColor = $script:theme.Systems.Watcher.Primary
$btnWatcherLogs.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnWatcherLogs.FlatAppearance.BorderColor = $script:theme.Systems.Watcher.Primary
$btnWatcherLogs.FlatAppearance.BorderSize = 1
$btnWatcherLogs.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnWatcherLogs.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnWatcherRestart = New-Object System.Windows.Forms.Button
$btnWatcherRestart.Text = "Restart"
$btnWatcherRestart.Location = New-Object System.Drawing.Point(145, 240)
$btnWatcherRestart.Size = New-Object System.Drawing.Size(110, 35)
$btnWatcherRestart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnWatcherRestart.ForeColor = $script:theme.Systems.Watcher.Primary
$btnWatcherRestart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnWatcherRestart.FlatAppearance.BorderColor = $script:theme.Systems.Watcher.Primary
$btnWatcherRestart.FlatAppearance.BorderSize = 1
$btnWatcherRestart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnWatcherRestart.Cursor = [System.Windows.Forms.Cursors]::Hand

$cardWatcher.Controls.AddRange(@($lblWatcherPID, $lblWatcherInterval, $lblWatcherCompanies, $lblWatcherLastActivity, $btnWatcherLogs, $btnWatcherRestart))

# ScriptHub Sync Card
$cardScriptHubSync = Create-SystemCard -SystemName "ScriptHubSync" -CardName "ScriptHubSync" -SystemColor $script:theme.Systems.ScriptHubSync.Primary `
    -GetStatusFunction { Get-ScriptHubSyncStatus } `
    -UpdateCardFunction { param($status) }

$lblScriptHubSyncLastSync = New-Object System.Windows.Forms.Label
$lblScriptHubSyncLastSync.Name = "lblScriptHubSyncLastSync"
$lblScriptHubSyncLastSync.Location = New-Object System.Drawing.Point(15, 75)
$lblScriptHubSyncLastSync.Size = New-Object System.Drawing.Size(370, 22)
$lblScriptHubSyncLastSync.ForeColor = $script:theme.Text
$lblScriptHubSyncLastSync.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblScriptHubSyncNextSync = New-Object System.Windows.Forms.Label
$lblScriptHubSyncNextSync.Name = "lblScriptHubSyncNextSync"
$lblScriptHubSyncNextSync.Location = New-Object System.Drawing.Point(15, 102)
$lblScriptHubSyncNextSync.Size = New-Object System.Drawing.Size(370, 22)
$lblScriptHubSyncNextSync.ForeColor = $script:theme.Text
$lblScriptHubSyncNextSync.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblScriptHubSyncResult = New-Object System.Windows.Forms.Label
$lblScriptHubSyncResult.Name = "lblScriptHubSyncResult"
$lblScriptHubSyncResult.Location = New-Object System.Drawing.Point(15, 129)
$lblScriptHubSyncResult.Size = New-Object System.Drawing.Size(370, 22)
$lblScriptHubSyncResult.ForeColor = $script:theme.Text
$lblScriptHubSyncResult.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblScriptHubSyncRows = New-Object System.Windows.Forms.Label
$lblScriptHubSyncRows.Name = "lblScriptHubSyncRows"
$lblScriptHubSyncRows.Location = New-Object System.Drawing.Point(15, 156)
$lblScriptHubSyncRows.Size = New-Object System.Drawing.Size(370, 22)
$lblScriptHubSyncRows.ForeColor = $script:theme.TextDim
$lblScriptHubSyncRows.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$btnScriptHubSyncRun = New-Object System.Windows.Forms.Button
$btnScriptHubSyncRun.Text = "Run Now"
$btnScriptHubSyncRun.Location = New-Object System.Drawing.Point(15, 240)
$btnScriptHubSyncRun.Size = New-Object System.Drawing.Size(120, 35)
$btnScriptHubSyncRun.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnScriptHubSyncRun.ForeColor = $script:theme.Systems.ScriptHubSync.Primary
$btnScriptHubSyncRun.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnScriptHubSyncRun.FlatAppearance.BorderColor = $script:theme.Systems.ScriptHubSync.Primary
$btnScriptHubSyncRun.FlatAppearance.BorderSize = 1
$btnScriptHubSyncRun.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnScriptHubSyncRun.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnScriptHubSyncLogs = New-Object System.Windows.Forms.Button
$btnScriptHubSyncLogs.Text = "View Logs"
$btnScriptHubSyncLogs.Location = New-Object System.Drawing.Point(145, 240)
$btnScriptHubSyncLogs.Size = New-Object System.Drawing.Size(120, 35)
$btnScriptHubSyncLogs.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnScriptHubSyncLogs.ForeColor = $script:theme.Systems.ScriptHubSync.Primary
$btnScriptHubSyncLogs.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnScriptHubSyncLogs.FlatAppearance.BorderColor = $script:theme.Systems.ScriptHubSync.Primary
$btnScriptHubSyncLogs.FlatAppearance.BorderSize = 1
$btnScriptHubSyncLogs.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnScriptHubSyncLogs.Cursor = [System.Windows.Forms.Cursors]::Hand

$cardScriptHubSync.Controls.AddRange(@($lblScriptHubSyncLastSync, $lblScriptHubSyncNextSync, $lblScriptHubSyncResult, $lblScriptHubSyncRows, $btnScriptHubSyncRun, $btnScriptHubSyncLogs))

# System Monitor Card
$cardSystemMonitor = Create-SystemCard -SystemName "SystemMonitor" -CardName "SystemMonitor" -SystemColor $script:theme.Systems.SystemMonitor.Primary `
    -GetStatusFunction { Get-SystemMonitorStatus } `
    -UpdateCardFunction { param($status) }

$lblSystemMonitorTask = New-Object System.Windows.Forms.Label
$lblSystemMonitorTask.Name = "lblSystemMonitorTask"
$lblSystemMonitorTask.Text = "Task: KyloSystemMonitor"
$lblSystemMonitorTask.Location = New-Object System.Drawing.Point(15, 75)
$lblSystemMonitorTask.Size = New-Object System.Drawing.Size(370, 22)
$lblSystemMonitorTask.ForeColor = $script:theme.Text
$lblSystemMonitorTask.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblSystemMonitorServices = New-Object System.Windows.Forms.Label
$lblSystemMonitorServices.Name = "lblSystemMonitorServices"
$lblSystemMonitorServices.Text = "Services Monitored: 7"
$lblSystemMonitorServices.Location = New-Object System.Drawing.Point(15, 102)
$lblSystemMonitorServices.Size = New-Object System.Drawing.Size(370, 22)
$lblSystemMonitorServices.ForeColor = $script:theme.Text
$lblSystemMonitorServices.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblSystemMonitorUptime = New-Object System.Windows.Forms.Label
$lblSystemMonitorUptime.Name = "lblSystemMonitorUptime"
$lblSystemMonitorUptime.Location = New-Object System.Drawing.Point(15, 129)
$lblSystemMonitorUptime.Size = New-Object System.Drawing.Size(370, 22)
$lblSystemMonitorUptime.ForeColor = $script:theme.Text
$lblSystemMonitorUptime.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$lblSystemMonitorLastCheck = New-Object System.Windows.Forms.Label
$lblSystemMonitorLastCheck.Name = "lblSystemMonitorLastCheck"
$lblSystemMonitorLastCheck.Location = New-Object System.Drawing.Point(15, 156)
$lblSystemMonitorLastCheck.Size = New-Object System.Drawing.Size(370, 22)
$lblSystemMonitorLastCheck.ForeColor = $script:theme.TextDim
$lblSystemMonitorLastCheck.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)

$btnSystemMonitorLogs = New-Object System.Windows.Forms.Button
$btnSystemMonitorLogs.Text = "View Logs"
$btnSystemMonitorLogs.Location = New-Object System.Drawing.Point(15, 240)
$btnSystemMonitorLogs.Size = New-Object System.Drawing.Size(120, 35)
$btnSystemMonitorLogs.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnSystemMonitorLogs.ForeColor = $script:theme.Systems.SystemMonitor.Primary
$btnSystemMonitorLogs.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnSystemMonitorLogs.FlatAppearance.BorderColor = $script:theme.Systems.SystemMonitor.Primary
$btnSystemMonitorLogs.FlatAppearance.BorderSize = 1
$btnSystemMonitorLogs.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnSystemMonitorLogs.Cursor = [System.Windows.Forms.Cursors]::Hand

$btnSystemMonitorRestart = New-Object System.Windows.Forms.Button
$btnSystemMonitorRestart.Text = "Restart"
$btnSystemMonitorRestart.Location = New-Object System.Drawing.Point(145, 240)
$btnSystemMonitorRestart.Size = New-Object System.Drawing.Size(110, 35)
$btnSystemMonitorRestart.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$btnSystemMonitorRestart.ForeColor = $script:theme.Systems.SystemMonitor.Primary
$btnSystemMonitorRestart.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnSystemMonitorRestart.FlatAppearance.BorderColor = $script:theme.Systems.SystemMonitor.Primary
$btnSystemMonitorRestart.FlatAppearance.BorderSize = 1
$btnSystemMonitorRestart.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnSystemMonitorRestart.Cursor = [System.Windows.Forms.Cursors]::Hand

$cardSystemMonitor.Controls.AddRange(@($lblSystemMonitorTask, $lblSystemMonitorServices, $lblSystemMonitorUptime, $lblSystemMonitorLastCheck, $btnSystemMonitorLogs, $btnSystemMonitorRestart))

# Add all cards to flow layout panel
$flowLayoutPanelCards.Controls.AddRange(@($cardPostgreSQL, $cardRedpanda, $cardKafkaTxns, $cardKafkaPromote, $cardWatcher, $cardScriptHubSync, $cardSystemMonitor))

# ============================================================================
# EVENT HANDLERS
# ============================================================================

# Refresh All Button
$btnRefreshAll.Add_Click({
    $btnRefreshAll.Enabled = $false
    $btnRefreshAll.Text = "Refreshing..."
    Update-AllSystemCards
    $btnRefreshAll.Enabled = $true
    $btnRefreshAll.Text = "Refresh All"
})

# Auto-Refresh Toggle
$chkAutoRefresh.Add_CheckedChanged({
    if ($chkAutoRefresh.Checked) {
        if ($script:refreshTimer) {
            $script:refreshTimer.Start()
        }
    } else {
        if ($script:refreshTimer) {
            $script:refreshTimer.Stop()
        }
    }
})

# Refresh Interval ComboBox
$cmbRefreshInterval.Add_SelectedIndexChanged({
    $intervals = @(5, 10, 30, 60)
    $selectedInterval = $intervals[$cmbRefreshInterval.SelectedIndex]
    if ($script:refreshTimer) {
        $script:refreshTimer.Interval = $selectedInterval * 1000
    }
})

# Filter TextBox
$txtFilterSystems.Add_GotFocus({
    if ($txtFilterSystems.Text -eq "Search systems...") {
        $txtFilterSystems.Text = ""
        $txtFilterSystems.ForeColor = $script:theme.Text
    }
})

$txtFilterSystems.Add_LostFocus({
    if ([string]::IsNullOrWhiteSpace($txtFilterSystems.Text)) {
        $txtFilterSystems.Text = "Search systems..."
        $txtFilterSystems.ForeColor = $script:theme.TextDim
    }
})

$txtFilterSystems.Add_TextChanged({
    $filterText = $txtFilterSystems.Text.ToLower()
    if ($filterText -eq "search systems...") { return }
    
    foreach ($card in $flowLayoutPanelCards.Controls) {
        if ($card -is [System.Windows.Forms.Panel] -and $card.Name -like "*Card*") {
            $cardName = $card.Name -replace "card", "" -replace "Card", ""
            if ($cardName.ToLower().Contains($filterText) -or [string]::IsNullOrWhiteSpace($filterText)) {
                $card.Visible = $true
            } else {
                $card.Visible = $false
            }
        }
    }
})

# PostgreSQL View Logs Button
$btnPostgreSQLLogs.Add_Click({
    $tabControl.SelectedTab = $tabLogViewerPage
    $tabLogViewer.SelectedTab = $tabPostgreSQLLogs
    Load-DockerLogs -ContainerName "kylo-pg" -RichTextBox $postgreSQLLogControls.RichTextBox
})

# PostgreSQL Restart Button
$btnPostgreSQLRestart.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Restart PostgreSQL container?",
        "Confirm Restart",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        $btnPostgreSQLRestart.Enabled = $false
        $btnPostgreSQLRestart.Text = "Restarting..."
        
        Start-Job -ScriptBlock {
            docker restart kylo-pg
        } | Out-Null
        
        Start-Sleep -Seconds 3
        Update-PostgreSQLCard
        $btnPostgreSQLRestart.Enabled = $true
        $btnPostgreSQLRestart.Text = "Restart"
    }
})

# Redpanda View Logs Button
$btnRedpandaLogs.Add_Click({
    $tabControl.SelectedTab = $tabLogViewerPage
    $tabLogViewer.SelectedTab = $tabRedpandaLogs
    Load-DockerLogs -ContainerName "kylo-redpanda" -RichTextBox $redpandaLogControls.RichTextBox
})

# Redpanda Restart Button
$btnRedpandaRestart.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Restart Redpanda container?",
        "Confirm Restart",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        $btnRedpandaRestart.Enabled = $false
        $btnRedpandaRestart.Text = "Restarting..."
        Start-Job -ScriptBlock { docker restart kylo-redpanda } | Out-Null
        Start-Sleep -Seconds 3
        Update-RedpandaCard
        $btnRedpandaRestart.Enabled = $true
        $btnRedpandaRestart.Text = "Restart"
    }
})

# Kafka Consumer Txns buttons
$btnKafkaTxnsLogs.Add_Click({
    $tabControl.SelectedTab = $tabLogViewerPage
    $tabLogViewer.SelectedTab = $tabKafkaTxnsLogs
    Load-DockerLogs -ContainerName "kylo-kafka-consumer-txns" -RichTextBox $kafkaTxnsLogControls.RichTextBox
})

$btnKafkaTxnsRestart.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Restart Kafka Consumer Txns container?",
        "Confirm Restart",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        $btnKafkaTxnsRestart.Enabled = $false
        $btnKafkaTxnsRestart.Text = "Restarting..."
        Start-Job -ScriptBlock { docker restart kylo-kafka-consumer-txns } | Out-Null
        Start-Sleep -Seconds 3
        Update-AllSystemCards
        $btnKafkaTxnsRestart.Enabled = $true
        $btnKafkaTxnsRestart.Text = "Restart"
    }
})

# Kafka Consumer Promote buttons
$btnKafkaPromoteLogs.Add_Click({
    $tabControl.SelectedTab = $tabLogViewerPage
    $tabLogViewer.SelectedTab = $tabKafkaPromoteLogs
    Load-DockerLogs -ContainerName "kylo-kafka-consumer-promote" -RichTextBox $kafkaPromoteLogControls.RichTextBox
})

$btnKafkaPromoteRestart.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Restart Kafka Consumer Promote container?",
        "Confirm Restart",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        $btnKafkaPromoteRestart.Enabled = $false
        $btnKafkaPromoteRestart.Text = "Restarting..."
        Start-Job -ScriptBlock { docker restart kylo-kafka-consumer-promote } | Out-Null
        Start-Sleep -Seconds 3
        Update-AllSystemCards
        $btnKafkaPromoteRestart.Enabled = $true
        $btnKafkaPromoteRestart.Text = "Restart"
    }
})

# Watcher buttons
$btnWatcherLogs.Add_Click({
    $tabControl.SelectedTab = $tabLogViewerPage
    $tabLogViewer.SelectedTab = $tabWatcherLog
})

$btnWatcherRestart.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Restart watcher service?",
        "Confirm Restart",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        Stop-WatcherService | Out-Null
        Start-Sleep -Seconds 2
        $result = Start-WatcherService
        if ($result.Success) {
            [System.Windows.Forms.MessageBox]::Show("Watcher restarted", "Success", "OK", "Information")
        }
        Update-AllSystemCards
    }
})

# ScriptHub Sync buttons
$btnScriptHubSyncRun.Add_Click({
    $btnRunSyncNow.PerformClick()
})

$btnScriptHubSyncLogs.Add_Click({
    $tabControl.SelectedTab = $tabLogViewerPage
    $tabLogViewer.SelectedTab = $tabScriptHubSyncLogs
})

# System Monitor buttons
$btnSystemMonitorLogs.Add_Click({
    $tabControl.SelectedTab = $tabLogViewerPage
    $tabLogViewer.SelectedTab = $tabMonitorLog
})

$btnSystemMonitorRestart.Add_Click({
    $btnRestartMonitor.PerformClick()
})

# Scheduled Tasks Event Handlers
$btnEnableTask.Add_Click({
    $selectedRow = $dgvScheduledTasks.SelectedRows[0]
    if ($selectedRow) {
        $taskName = $selectedRow.Cells[0].Value
        try {
            Enable-ScheduledTask -TaskName $taskName
            [System.Windows.Forms.MessageBox]::Show("Task enabled successfully", "Success", "OK", "Information")
            Load-ScheduledTasks
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Failed to enable task: $_", "Error", "OK", "Error")
        }
    }
})

$btnDisableTask.Add_Click({
    $selectedRow = $dgvScheduledTasks.SelectedRows[0]
    if ($selectedRow) {
        $taskName = $selectedRow.Cells[0].Value
        try {
            Disable-ScheduledTask -TaskName $taskName
            [System.Windows.Forms.MessageBox]::Show("Task disabled successfully", "Success", "OK", "Information")
            Load-ScheduledTasks
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Failed to disable task: $_", "Error", "OK", "Error")
        }
    }
})

$btnRunTask.Add_Click({
    $selectedRow = $dgvScheduledTasks.SelectedRows[0]
    if ($selectedRow) {
        $taskName = $selectedRow.Cells[0].Value
        $btnRunTask.Enabled = $false
        $btnRunTask.Text = "Running..."
        
        try {
            Start-ScheduledTask -TaskName $taskName
            Start-Sleep -Seconds 2
            $task = Get-ScheduledTask -TaskName $taskName
            if ($task.State -eq "Running") {
                [System.Windows.Forms.MessageBox]::Show("Task started successfully", "Success", "OK", "Information")
            } else {
                [System.Windows.Forms.MessageBox]::Show("Task may have completed quickly", "Info", "OK", "Information")
            }
            Load-ScheduledTasks
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Failed to run task: $_", "Error", "OK", "Error")
        } finally {
            $btnRunTask.Enabled = $true
            $btnRunTask.Text = "Run Now"
        }
    }
})

$btnViewTaskDetails.Add_Click({
    $selectedRow = $dgvScheduledTasks.SelectedRows[0]
    if ($selectedRow) {
        $taskName = $selectedRow.Cells[0].Value
        Show-TaskDetailsDialog -TaskName $taskName
    }
})

$btnRefreshTasks.Add_Click({
    Load-ScheduledTasks
})

# Service Controls Event Handlers
$btnStartAllDocker.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Start all Docker services?",
        "Confirm",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        $btnStartAllDocker.Enabled = $false
        $progressBarDocker.Visible = $true
        $progressBarDocker.Value = 0
        
        Start-Job -ScriptBlock {
            Set-Location "D:\Project-Kylo"
            docker compose -f docker-compose.yml up -d
            docker compose -f docker-compose.kafka.yml up -d
            docker compose -f docker-compose.kafka-consumer.yml up -d
        } | Out-Null
        
        # Monitor progress
        $timer = New-Object System.Windows.Forms.Timer
        $timer.Interval = 1000
        $elapsed = 0
        $timer.Add_Tick({
            $elapsed++
            $progressBarDocker.Value = [Math]::Min(90, $elapsed * 10)
            
            $containers = @("kylo-pg", "kylo-redpanda", "kylo-kafka-consumer-txns", "kylo-kafka-consumer-promote")
            $running = 0
            foreach ($container in $containers) {
                $status = docker ps --filter "name=$container" --format "{{.Names}}" 2>&1
                if ($status -eq $container) { $running++ }
            }
            
            if ($running -eq $containers.Count -or $elapsed -gt 30) {
                $timer.Stop()
                $progressBarDocker.Value = 100
                Start-Sleep -Seconds 1
                $progressBarDocker.Visible = $false
                $btnStartAllDocker.Enabled = $true
                Update-AllSystemCards
                [System.Windows.Forms.MessageBox]::Show("All services started", "Success", "OK", "Information")
            }
        })
        $timer.Start()
    }
})

$btnStopAllDocker.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Stop all Docker services?",
        "Confirm",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        $result = Stop-AllDockerServices
        if ($result.Success) {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Success", "OK", "Information")
        } else {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
        }
        Update-AllSystemCards
    }
})

$btnRestartAllDocker.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Restart all Docker services?",
        "Confirm",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        Stop-AllDockerServices | Out-Null
        Start-Sleep -Seconds 2
        $result = Start-AllDockerServices
        if ($result.Success) {
            [System.Windows.Forms.MessageBox]::Show("All services restarted", "Success", "OK", "Information")
        } else {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
        }
        Update-AllSystemCards
    }
})

$btnStartWatcher.Add_Click({
    $result = Start-WatcherService
    if ($result.Success) {
        [System.Windows.Forms.MessageBox]::Show($result.Message, "Success", "OK", "Information")
    } else {
        [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
    }
    Update-AllSystemCards
})

$btnStopWatcher.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Stop watcher service?",
        "Confirm",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        $result = Stop-WatcherService
        if ($result.Success) {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Success", "OK", "Information")
        } else {
            [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
        }
        Update-AllSystemCards
    }
})

$btnRestartWatcher.Add_Click({
    Stop-WatcherService | Out-Null
    Start-Sleep -Seconds 2
    $result = Start-WatcherService
    if ($result.Success) {
        [System.Windows.Forms.MessageBox]::Show("Watcher restarted", "Success", "OK", "Information")
    } else {
        [System.Windows.Forms.MessageBox]::Show($result.Message, "Error", "OK", "Error")
    }
    Update-AllSystemCards
})

$btnRunSyncNow.Add_Click({
    $btnRunSyncNow.Enabled = $false
    $btnRunSyncNow.Text = "Running..."
    $txtSyncResult.Text = "Executing sync scripts..."
    
    $job = Start-Job -ScriptBlock {
        Set-Location "D:\Project-Kylo\tools\scripthub_legacy"
        $env:PYTHONPATH = "D:\Project-Kylo\tools\scripthub_legacy"
        python scripts\run_both_syncs.py 2>&1
    }
    
    # Monitor job
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 1000
    $timer.Add_Tick({
        if ($job.State -eq "Completed") {
            $output = Receive-Job $job
            $txtSyncResult.Text = $output -join "`r`n"
            Remove-Job $job
            $timer.Stop()
            $btnRunSyncNow.Enabled = $true
            $btnRunSyncNow.Text = "Run Sync Now"
            Update-AllSystemCards
        } elseif ($job.State -eq "Failed") {
            $txtSyncResult.Text = "Sync failed"
            Remove-Job $job
            $timer.Stop()
            $btnRunSyncNow.Enabled = $true
            $btnRunSyncNow.Text = "Run Sync Now"
        }
    })
    $timer.Start()
})

$btnStartMonitor.Add_Click({
    try {
        Start-ScheduledTask -TaskName "KyloSystemMonitor"
        [System.Windows.Forms.MessageBox]::Show("Monitor started", "Success", "OK", "Information")
        Update-AllSystemCards
    } catch {
        [System.Windows.Forms.MessageBox]::Show("Failed to start monitor: $_", "Error", "OK", "Error")
    }
})

$btnStopMonitor.Add_Click({
    $result = [System.Windows.Forms.MessageBox]::Show(
        "Stop system monitor?",
        "Confirm",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($result -eq [System.Windows.Forms.DialogResult]::Yes) {
        try {
            Stop-ScheduledTask -TaskName "KyloSystemMonitor"
            [System.Windows.Forms.MessageBox]::Show("Monitor stopped", "Success", "OK", "Information")
            Update-AllSystemCards
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Failed to stop monitor: $_", "Error", "OK", "Error")
        }
    }
})

$btnRestartMonitor.Add_Click({
    try {
        Stop-ScheduledTask -TaskName "KyloSystemMonitor" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Start-ScheduledTask -TaskName "KyloSystemMonitor"
        [System.Windows.Forms.MessageBox]::Show("Monitor restarted", "Success", "OK", "Information")
        Update-AllSystemCards
    } catch {
        [System.Windows.Forms.MessageBox]::Show("Failed to restart monitor: $_", "Error", "OK", "Error")
    }
})

# ============================================================================
# UPDATE FUNCTIONS
# ============================================================================

function Update-PostgreSQLCard {
    try {
        $status = Get-PostgreSQLStatus
        $systemColors = Get-SystemColor -SystemName "PostgreSQL"
        
        # Find status label from card controls
        $lblStatus = $cardPostgreSQL.Controls | Where-Object { $_.Name -like "*Status*" } | Select-Object -First 1
        if ($lblStatus) {
            $lblStatus.Text = "Status: $($status.Status)"
            if ($status.Running) {
                $lblStatus.ForeColor = $script:theme.Status.Running
            } elseif ($status.Error) {
                $lblStatus.ForeColor = $script:theme.Status.Error
            } else {
                $lblStatus.ForeColor = $script:theme.Status.Unknown
            }
        }
        
        if ($lblPostgreSQLHealth) {
            $lblPostgreSQLHealth.Text = "Health: $($status.Health)"
            if ($status.Health -eq "Healthy") {
                $lblPostgreSQLHealth.ForeColor = $systemColors.Primary
            } else {
                $lblPostgreSQLHealth.ForeColor = $script:theme.Status.Warning
            }
        }
        
        if ($lblPostgreSQLUptime) {
            if ($status.Uptime) {
                $lblPostgreSQLUptime.Text = "Uptime: $(Format-Uptime $status.Uptime)"
            } else {
                $lblPostgreSQLUptime.Text = "Uptime: N/A"
            }
        }
        
        if ($lblPostgreSQLLastCheck) {
            $lblPostgreSQLLastCheck.Text = "Last Check: $($status.LastCheck.ToString('HH:mm:ss'))"
        }
    } catch {
        Write-Warning "Error updating PostgreSQL card: $_"
    }
}

function Update-RedpandaCard {
    try {
        $status = Get-RedpandaStatus
        $systemColors = Get-SystemColor -SystemName "Redpanda"
        
        $lblRedpandaStatus = $cardRedpanda.Controls | Where-Object { $_.Name -like "*Status*" } | Select-Object -First 1
        if ($lblRedpandaStatus) {
            $lblRedpandaStatus.Text = "Status: $($status.Status)"
            if ($status.Running) {
                $lblRedpandaStatus.ForeColor = $script:theme.Status.Running
            } elseif ($status.Error) {
                $lblRedpandaStatus.ForeColor = $script:theme.Status.Error
            } else {
                $lblRedpandaStatus.ForeColor = $script:theme.Status.Unknown
            }
        }
        
        $lblRedpandaHealth.Text = "Health: $($status.Health)"
        if ($status.Health -eq "Healthy") {
            $lblRedpandaHealth.ForeColor = $systemColors.Primary
        } else {
            $lblRedpandaHealth.ForeColor = $script:theme.Status.Warning
        }
        
        if ($status.Uptime) {
            $lblRedpandaUptime.Text = "Uptime: $(Format-Uptime $status.Uptime)"
        } else {
            $lblRedpandaUptime.Text = "Uptime: N/A"
        }
        
        $lblRedpandaLastCheck.Text = "Last Check: $($status.LastCheck.ToString('HH:mm:ss'))"
    } catch {
        Write-Warning "Error updating Redpanda card: $_"
    }
}

function Update-KafkaConsumerCard {
    param([string]$ContainerName, [System.Windows.Forms.Panel]$Card)
    
    try {
        $status = Get-KafkaConsumerStatus -ContainerName $ContainerName
        $systemColors = Get-SystemColor -SystemName "KafkaConsumer"
        
        $lblStatus = $Card.Controls | Where-Object { $_.Name -like "*Status*" } | Select-Object -First 1
        if ($lblStatus) {
            $lblStatus.Text = "Status: $($status.Status)"
            if ($status.Running) {
                $lblStatus.ForeColor = $script:theme.Status.Running
            } else {
                $lblStatus.ForeColor = $script:theme.Status.Error
            }
        }
        
        $lblMessages = $Card.Controls | Where-Object { $_.Name -like "*Messages*" } | Select-Object -First 1
        if ($lblMessages) {
            $lblMessages.Text = "Messages Processed: $($status.MessageCount)"
        }
        
        $lblUptime = $Card.Controls | Where-Object { $_.Name -like "*Uptime*" } | Select-Object -First 1
        if ($lblUptime) {
            if ($status.Uptime) {
                $lblUptime.Text = "Uptime: $(Format-Uptime $status.Uptime)"
            } else {
                $lblUptime.Text = "Uptime: N/A"
            }
        }
        
        $lblLastCheck = $Card.Controls | Where-Object { $_.Name -like "*LastCheck*" } | Select-Object -First 1
        if ($lblLastCheck) {
            $lblLastCheck.Text = "Last Check: $(Get-Date -Format 'HH:mm:ss')"
        }
    } catch {
        Write-Warning "Error updating Kafka Consumer card: $_"
    }
}

function Update-WatcherCard {
    try {
        $status = Get-WatcherStatus
        $systemColors = Get-SystemColor -SystemName "Watcher"
        
        $lblWatcherStatus = $cardWatcher.Controls | Where-Object { $_.Name -like "*Status*" } | Select-Object -First 1
        if ($lblWatcherStatus) {
            $lblWatcherStatus.Text = "Status: $(if ($status.Running) { 'Running' } else { 'Stopped' })"
            $lblWatcherStatus.ForeColor = if ($status.Running) { $script:theme.Status.Running } else { $script:theme.Status.Error }
        }
        
        $lblWatcherPID.Text = if ($status.PID) { "PID: $($status.PID)" } else { "PID: N/A" }
        $lblWatcherInterval.Text = "Watch Interval: $($status.WatchInterval)s"
        $lblWatcherCompanies.Text = "Companies: $($status.CompaniesWatched)"
        $lblWatcherLastActivity.Text = if ($status.LastActivityTime) { 
            "Last Activity: $($status.LastActivityTime.ToString('HH:mm:ss'))" 
        } else { 
            "Last Activity: N/A" 
        }
    } catch {
        Write-Warning "Error updating Watcher card: $_"
    }
}

function Update-ScriptHubSyncCard {
    try {
        $status = Get-ScriptHubSyncStatus
        $systemColors = Get-SystemColor -SystemName "ScriptHubSync"
        
        $lblScriptHubSyncStatus = $cardScriptHubSync.Controls | Where-Object { $_.Name -like "*Status*" } | Select-Object -First 1
        if ($lblScriptHubSyncStatus) {
            $lblScriptHubSyncStatus.Text = "Status: $(if ($status.LastSync) { 'Active' } else { 'Unknown' })"
        }
        
        if ($lblScriptHubSyncLastSync) {
            $lblScriptHubSyncLastSync.Text = if ($status.LastSync) { 
                "Last Sync: $($status.LastSync.ToString('yyyy-MM-dd HH:mm:ss'))" 
            } else { 
                "Last Sync: Never" 
            }
        }
        
        if ($lblScriptHubSyncNextSync) {
            $lblScriptHubSyncNextSync.Text = if ($status.NextSync) { 
                "Next Sync: $($status.NextSync.ToString('HH:mm:ss'))" 
            } else { 
                "Next Sync: N/A" 
            }
        }
        
        if ($lblScriptHubSyncResult) {
            $lblScriptHubSyncResult.Text = "Last Result: $($status.LastResult)"
            $lblScriptHubSyncResult.ForeColor = if ($status.LastResult -eq "Success") { 
                $script:theme.Status.Running 
            } elseif ($status.LastResult -eq "Failed") { 
                $script:theme.Status.Error 
            } else { 
                $script:theme.Text 
            }
        }
        
        if ($lblScriptHubSyncRows) {
            $lblScriptHubSyncRows.Text = "Rows Updated: $($status.RowsUpdated)"
        }
    } catch {
        Write-Warning "Error updating ScriptHub Sync card: $_"
    }
}

function Update-SystemMonitorCard {
    try {
        $status = Get-SystemMonitorStatus
        $systemColors = Get-SystemColor -SystemName "SystemMonitor"
        
        $lblSystemMonitorStatus = $cardSystemMonitor.Controls | Where-Object { $_.Name -like "*Status*" } | Select-Object -First 1
        if ($lblSystemMonitorStatus) {
            $lblSystemMonitorStatus.Text = "Status: $(if ($status.Running) { 'Running' } else { 'Stopped' })"
            $lblSystemMonitorStatus.ForeColor = if ($status.Running) { $script:theme.Status.Running } else { $script:theme.Status.Error }
        }
        
        if ($lblSystemMonitorServices) {
            $lblSystemMonitorServices.Text = "Services Monitored: $($status.ServicesMonitored)"
        }
        if ($lblSystemMonitorUptime) {
            $lblSystemMonitorUptime.Text = if ($status.Uptime) { 
                "Uptime: $(Format-Uptime $status.Uptime)" 
            } else { 
                "Uptime: N/A" 
            }
        }
        if ($lblSystemMonitorLastCheck) {
            $lblSystemMonitorLastCheck.Text = if ($status.LastStatusCheck) { 
                "Last Check: $($status.LastStatusCheck.ToString('HH:mm:ss'))" 
            } else { 
                "Last Check: N/A" 
            }
        }
    } catch {
        Write-Warning "Error updating System Monitor card: $_"
    }
}

function Update-AllSystemCards {
    try {
        Update-PostgreSQLCard
        Update-RedpandaCard
        Update-KafkaConsumerCard -ContainerName "kylo-kafka-consumer-txns" -Card $cardKafkaTxns
        Update-KafkaConsumerCard -ContainerName "kylo-kafka-consumer-promote" -Card $cardKafkaPromote
        Update-WatcherCard
        Update-ScriptHubSyncCard
        Update-SystemMonitorCard
        Update-StatusSummary
        $lastUpdateLabel.Text = "Last Update: $(Get-Date -Format 'HH:mm:ss')"
    } catch {
        Write-Warning "Error updating system cards: $_"
    }
}

function Update-StatusSummary {
    try {
        $allStatus = @(
            (Get-PostgreSQLStatus)
            (Get-RedpandaStatus)
            (Get-KafkaConsumerStatus -ContainerName "kylo-kafka-consumer-txns")
            (Get-KafkaConsumerStatus -ContainerName "kylo-kafka-consumer-promote")
            (Get-WatcherStatus)
            (Get-ScriptHubSyncStatus)
            (Get-SystemMonitorStatus)
        )
        
        $total = $allStatus.Count
        $running = ($allStatus | Where-Object { $_.Running }).Count
        $stopped = ($allStatus | Where-Object { -not $_.Running }).Count
        $warnings = ($allStatus | Where-Object { $_.Health -eq "Unhealthy" -or $_.Status -like "*Warning*" }).Count
        
        $lblTotalServices.Text = "Total: $total"
        $lblRunning.Text = "Running: $running"
        $lblRunning.ForeColor = $script:theme.Status.Running
        $lblStopped.Text = "Stopped: $stopped"
        $lblStopped.ForeColor = $script:theme.Status.Error
        $lblWarnings.Text = "Warnings: $warnings"
        $lblWarnings.ForeColor = $script:theme.Status.Warning
        $lblLastUpdate.Text = "Last Update: $(Get-Date -Format 'HH:mm:ss')"
    } catch {
        Write-Warning "Error updating status summary: $_"
    }
}

function Load-ScheduledTasks {
    $taskNames = @("KyloSystemMonitor", "Kylo Auto-Start", "KyloSyncPeriodic", "KyloSyncStartup")
    
    $dgvScheduledTasks.Rows.Clear()
    
    foreach ($taskName in $taskNames) {
        try {
            $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            if ($task) {
                $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
                
                $status = if ($task.State -eq "Running" -or $task.State -eq "Ready") { 
                    "Enabled" 
                } else { 
                    "Disabled" 
                }
                
                $lastRun = if ($taskInfo.LastRunTime) { 
                    $taskInfo.LastRunTime.ToString("yyyy-MM-dd HH:mm:ss") 
                } else { 
                    "Never" 
                }
                
                $nextRun = "N/A"  # Would need to parse trigger schedule
                
                $lastResult = Get-TaskLastResult -TaskName $taskName
                
                $rowIndex = $dgvScheduledTasks.Rows.Add($taskName, $status, $lastRun, $nextRun, $lastResult)
                
                # Color code status
                if ($status -eq "Enabled") {
                    $dgvScheduledTasks.Rows[$rowIndex].Cells[1].Style.ForeColor = $script:theme.Status.Running
                } else {
                    $dgvScheduledTasks.Rows[$rowIndex].Cells[1].Style.ForeColor = $script:theme.Status.Error
                }
                
                # Color code last result
                if ($lastResult -eq "Success") {
                    $dgvScheduledTasks.Rows[$rowIndex].Cells[4].Style.ForeColor = $script:theme.Status.Running
                } elseif ($lastResult -eq "Failed") {
                    $dgvScheduledTasks.Rows[$rowIndex].Cells[4].Style.ForeColor = $script:theme.Status.Error
                }
            }
        } catch {
            Write-Warning "Error loading task $taskName : $_"
        }
    }
}

function Show-TaskDetailsDialog {
    param([string]$TaskName)
    
    $dialog = New-Object System.Windows.Forms.Form
    $dialog.Text = "Task Details: $TaskName"
    $dialog.Size = New-Object System.Drawing.Size(600, 500)
    $dialog.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterParent
    $dialog.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $dialog.MaximizeBox = $false
    $dialog.MinimizeBox = $false
    
    Apply-DarkTheme -Control $dialog
    
    $tabControlDetails = New-Object System.Windows.Forms.TabControl
    $tabControlDetails.Dock = [System.Windows.Forms.DockStyle]::Fill
    
    # General Tab
    $tabGeneral = New-Object System.Windows.Forms.TabPage
    $tabGeneral.Text = "General"
    
    $txtTaskName = New-Object System.Windows.Forms.TextBox
    $txtTaskName.Location = New-Object System.Drawing.Point(10, 10)
    $txtTaskName.Size = New-Object System.Drawing.Size(560, 20)
    $txtTaskName.ReadOnly = $true
    $txtTaskName.BackColor = $script:theme.PanelBg
    $txtTaskName.ForeColor = $script:theme.Text
    
    # Add more fields...
    $tabGeneral.Controls.Add($txtTaskName)
    $tabControlDetails.TabPages.Add($tabGeneral)
    
    # Load task details
    try {
        $task = Get-ScheduledTask -TaskName $TaskName
        $xmlPath = "$env:TEMP\task_$($TaskName -replace '[^\w]', '_').xml"
        schtasks /Query /TN $TaskName /XML 2>&1 | Out-File $xmlPath -Encoding UTF8
        
        if (Test-Path $xmlPath) {
            $xml = [xml](Get-Content $xmlPath)
            $txtTaskName.Text = $TaskName
            # Populate other fields...
            Remove-Item $xmlPath -ErrorAction SilentlyContinue
        }
    } catch {
        [System.Windows.Forms.MessageBox]::Show("Error loading task details: $_", "Error", "OK", "Error")
    }
    
    $dialog.Controls.Add($tabControlDetails)
    $dialog.ShowDialog() | Out-Null
}

# ============================================================================
# REAL-TIME UPDATE TIMER
# ============================================================================

$script:refreshTimer = New-Object System.Windows.Forms.Timer
$script:refreshTimer.Interval = 10000  # 10 seconds
$script:refreshTimer.Add_Tick({
    # Start background job for status checks
    $statusJob = Start-Job -ScriptBlock {
        Set-Location "D:\Project-Kylo"
        . (Join-Path $using:helpersPath "SystemMonitor.ps1")
        
        $status = @{
            PostgreSQL = Get-PostgreSQLStatus
            Redpanda = Get-RedpandaStatus
            KafkaTxns = Get-KafkaConsumerStatus -ContainerName "kylo-kafka-consumer-txns"
            KafkaPromote = Get-KafkaConsumerStatus -ContainerName "kylo-kafka-consumer-promote"
            Watcher = Get-WatcherStatus
            Sync = Get-ScriptHubSyncStatus
            Monitor = Get-SystemMonitorStatus
        }
        return $status
    }
    
    # Register callback
    Register-ObjectEvent -InputObject $statusJob -EventName "StateChanged" -Action {
        if ($Event.SourceEventArgs.NewState -eq "Completed") {
            $status = Receive-Job $Event.SourceEventArgs
            # Update UI thread-safely
            $form.Invoke([Action]{
                Update-AllSystemCards
            })
            Remove-Job $Event.SourceEventArgs
        }
    }
})

if ($chkAutoRefresh.Checked) {
    $script:refreshTimer.Start()
}

# ============================================================================
# CLEANUP ON FORM CLOSE
# ============================================================================

$form.Add_FormClosing({
    # Stop all timers
    if ($script:refreshTimer) {
        $script:refreshTimer.Stop()
        $script:refreshTimer.Dispose()
    }
    
    # Stop all log watchers
    foreach ($watcherInfo in $script:logWatchers.Values) {
        try {
            $watcherInfo.Watcher.EnableRaisingEvents = $false
            $watcherInfo.Watcher.Dispose()
            Unregister-Event -SourceIdentifier $watcherInfo.Handler.Name -ErrorAction SilentlyContinue
        } catch {}
    }
    
    # Stop all Docker log jobs
    foreach ($job in $script:dockerLogJobs.Values) {
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -ErrorAction SilentlyContinue
    }
    
    # Stop all Docker log timers
    foreach ($timer in $script:dockerLogTimers.Values) {
        $timer.Stop()
        $timer.Dispose()
    }
    
    # Stop all background jobs
    Get-Job | Stop-Job -ErrorAction SilentlyContinue
    Get-Job | Remove-Job -ErrorAction SilentlyContinue
    
    # Dispose all event handlers
    Get-EventSubscriber | Unregister-Event -ErrorAction SilentlyContinue
})

# ============================================================================
# INITIALIZATION
# ============================================================================

# Load initial data
Load-ScheduledTasks
Update-AllSystemCards

# Show form
[System.Windows.Forms.Application]::EnableVisualStyles()
$form.ShowDialog() | Out-Null

