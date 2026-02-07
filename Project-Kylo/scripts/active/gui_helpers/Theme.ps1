# Theme System Functions
# Provides theme application and color management for Kylo Monitor GUI

# Theme color dictionary
$script:theme = @{
    # Base Cursor-like dark theme
    Background = [System.Drawing.Color]::FromArgb(30, 30, 30)      # #1E1E1E
    PanelBg = [System.Drawing.Color]::FromArgb(45, 45, 48)         # #2D2D30
    Text = [System.Drawing.Color]::FromArgb(204, 204, 204)          # #CCCCCC
    TextBright = [System.Drawing.Color]::FromArgb(255, 255, 255)    # #FFFFFF
    TextDim = [System.Drawing.Color]::FromArgb(128, 128, 128)       # #808080
    Border = [System.Drawing.Color]::FromArgb(60, 60, 60)           # #3C3C3C
    
    # System-specific color schemes
    Systems = @{
        PostgreSQL = @{
            Primary = [System.Drawing.Color]::FromArgb(74, 158, 255)    # #4A9EFF
            Accent = [System.Drawing.Color]::FromArgb(107, 182, 255)   # #6BB6FF
            Background = [System.Drawing.Color]::FromArgb(30, 42, 58)  # #1E2A3A
            Border = [System.Drawing.Color]::FromArgb(74, 158, 255)    # #4A9EFF
        }
        Redpanda = @{
            Primary = [System.Drawing.Color]::FromArgb(155, 89, 182)    # #9B59B6
            Accent = [System.Drawing.Color]::FromArgb(183, 148, 230)   # #B794E6
            Background = [System.Drawing.Color]::FromArgb(42, 30, 58)  # #2A1E3A
            Border = [System.Drawing.Color]::FromArgb(155, 89, 182)    # #9B59B6
        }
        KafkaConsumer = @{
            Primary = [System.Drawing.Color]::FromArgb(255, 140, 66)    # #FF8C42
            Accent = [System.Drawing.Color]::FromArgb(255, 179, 102)   # #FFB366
            Background = [System.Drawing.Color]::FromArgb(58, 46, 30)  # #3A2E1E
            Border = [System.Drawing.Color]::FromArgb(255, 140, 66)    # #FF8C42
        }
        Watcher = @{
            Primary = [System.Drawing.Color]::FromArgb(82, 196, 26)    # #52C41A
            Accent = [System.Drawing.Color]::FromArgb(115, 209, 61)    # #73D13D
            Background = [System.Drawing.Color]::FromArgb(30, 58, 30)   # #1E3A1E
            Border = [System.Drawing.Color]::FromArgb(82, 196, 26)    # #52C41A
        }
        ScriptHubSync = @{
            Primary = [System.Drawing.Color]::FromArgb(19, 194, 194)    # #13C2C2
            Accent = [System.Drawing.Color]::FromArgb(54, 207, 201)   # #36CFC9
            Background = [System.Drawing.Color]::FromArgb(30, 58, 58) # #1E3A3A
            Border = [System.Drawing.Color]::FromArgb(19, 194, 194)    # #13C2C2
        }
        SystemMonitor = @{
            Primary = [System.Drawing.Color]::FromArgb(32, 178, 170)   # #20B2AA
            Accent = [System.Drawing.Color]::FromArgb(72, 209, 204)    # #48D1CC
            Background = [System.Drawing.Color]::FromArgb(30, 58, 58) # #1E3A3A
            Border = [System.Drawing.Color]::FromArgb(32, 178, 170)   # #20B2AA
        }
    }
    
    # Status colors (universal)
    Status = @{
        Running = [System.Drawing.Color]::FromArgb(82, 196, 26)       # Green
        Warning = [System.Drawing.Color]::FromArgb(255, 193, 7)        # Yellow
        Error = [System.Drawing.Color]::FromArgb(255, 77, 79)          # Red
        Unknown = [System.Drawing.Color]::FromArgb(128, 128, 128)      # Gray
        Starting = [System.Drawing.Color]::FromArgb(255, 152, 0)       # Orange
    }
}

function Get-Theme {
    return $script:theme
}

function Apply-DarkTheme {
    param([System.Windows.Forms.Control]$Control)
    
    try {
        $Control.BackColor = $script:theme.Background
        $Control.ForeColor = $script:theme.Text
        
        # Apply to all child controls recursively
        foreach ($child in $Control.Controls) {
            try {
                if ($child -is [System.Windows.Forms.Panel] -or 
                    $child -is [System.Windows.Forms.GroupBox] -or
                    $child -is [System.Windows.Forms.FlowLayoutPanel] -or
                    $child -is [System.Windows.Forms.TableLayoutPanel]) {
                    $child.BackColor = $script:theme.PanelBg
                    $child.ForeColor = $script:theme.Text
                } elseif ($child -is [System.Windows.Forms.Label] -or
                          $child -is [System.Windows.Forms.Button] -or
                          $child -is [System.Windows.Forms.TextBox] -or
                          $child -is [System.Windows.Forms.RichTextBox] -or
                          $child -is [System.Windows.Forms.ComboBox] -or
                          $child -is [System.Windows.Forms.CheckBox]) {
                    $child.BackColor = $script:theme.PanelBg
                    $child.ForeColor = $script:theme.Text
                } elseif ($child -is [System.Windows.Forms.DataGridView]) {
                    $child.BackgroundColor = $script:theme.Background
                    $child.DefaultCellStyle.BackColor = $script:theme.PanelBg
                    $child.DefaultCellStyle.ForeColor = $script:theme.Text
                    $child.ColumnHeadersDefaultCellStyle.BackColor = $script:theme.PanelBg
                    $child.ColumnHeadersDefaultCellStyle.ForeColor = $script:theme.TextBright
                    $child.GridColor = $script:theme.Border
                    $child.BorderStyle = [System.Windows.Forms.BorderStyle]::None
                } elseif ($child -is [System.Windows.Forms.TabControl]) {
                    $child.BackColor = $script:theme.Background
                    # TabControl theming is limited in Windows Forms
                }
                
                # Recursive application
                if ($child.HasChildren) {
                    Apply-DarkTheme -Control $child
                }
            } catch {
                # Skip controls that don't support color properties
            }
        }
    } catch {
        Write-Warning "Error applying theme to control: $_"
    }
}

function Apply-SystemCardTheme {
    param(
        [System.Windows.Forms.Panel]$CardPanel,
        [string]$SystemName
    )
    
    try {
        if (-not $script:theme.Systems.ContainsKey($SystemName)) {
            Write-Warning "Unknown system name: $SystemName"
            return
        }
        
        $systemColors = $script:theme.Systems[$SystemName]
        
        # Apply background with slight transparency blend
        $baseBg = $script:theme.PanelBg
        $systemBg = $systemColors.Background
        # Blend: 80% base, 20% system color
        $blendedBg = [System.Drawing.Color]::FromArgb(
            [int](($baseBg.R * 0.8) + ($systemBg.R * 0.2)),
            [int](($baseBg.G * 0.8) + ($systemBg.G * 0.2)),
            [int](($baseBg.B * 0.8) + ($systemBg.B * 0.2))
        )
        $CardPanel.BackColor = $blendedBg
        $CardPanel.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
        
        # Apply to header label (if exists)
        $headerLabel = $CardPanel.Controls | Where-Object { $_.Name -like "*Header*" } | Select-Object -First 1
        if ($headerLabel) {
            $headerLabel.ForeColor = $systemColors.Primary
            if ($headerLabel.Font) {
                $headerLabel.Font = New-Object System.Drawing.Font($headerLabel.Font.FontFamily, $headerLabel.Font.Size, [System.Drawing.FontStyle]::Bold)
            }
        }
    } catch {
        Write-Warning "Error applying system card theme: $_"
    }
}

function Get-SystemColor {
    param([string]$SystemName)
    
    if ($script:theme.Systems.ContainsKey($SystemName)) {
        return $script:theme.Systems[$SystemName]
    }
    
    # Default fallback
    return @{
        Primary = $script:theme.Text
        Accent = $script:theme.TextDim
        Background = $script:theme.PanelBg
        Border = $script:theme.Border
    }
}

function Set-ControlColors {
    param(
        [System.Windows.Forms.Control]$Control,
        [System.Drawing.Color]$BackColor,
        [System.Drawing.Color]$ForeColor
    )
    
    try {
        if ($Control -is [System.Windows.Forms.DataGridView]) {
            $Control.BackgroundColor = $BackColor
            $Control.DefaultCellStyle.BackColor = $BackColor
            $Control.DefaultCellStyle.ForeColor = $ForeColor
        } else {
            $Control.BackColor = $BackColor
            $Control.ForeColor = $ForeColor
        }
    } catch {
        Write-Warning "Failed to set colors for control $($Control.Name): $_"
    }
}

# Functions are available after dot-sourcing this file

