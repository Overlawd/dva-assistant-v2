# admin_tasks.ps1 - DVA Assistant Admin Console
# Windows PowerShell script for managing the stack

param(
    [switch]$NoMenu
)

$PROJECT_ROOT = $PSScriptRoot
if (-not $PROJECT_ROOT -or $PROJECT_ROOT -eq "") {
    $PROJECT_ROOT = Split-Path -Parent $PSCommandPath
}
if (-not $PROJECT_ROOT -or $PROJECT_ROOT -eq "") {
    $PROJECT_ROOT = (Get-Location).Path
}
$PROJECT_ROOT = (Resolve-Path $PROJECT_ROOT -ErrorAction SilentlyContinue).Path

$composeFile = Join-Path $PROJECT_ROOT "docker-compose.yml"
if (-not (Test-Path $composeFile)) {
    Write-Error "Could not find docker-compose.yml at: $composeFile"
    Write-Host "Please run this script from the DVA Assistant project directory." -ForegroundColor Yellow
    exit 1
}

$CONTAINER_PREFIX = "dva-"
$BACKUP_DIR = Join-Path $PROJECT_ROOT "backups"

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Get-ContainerName {
    param([string]$Service)
    return "$CONTAINER_PREFIX$Service"
}

function Test-ContainersRunning {
    $services = @("ollama", "db", "web", "scraper", "scheduler")
    $running = @()
    foreach ($svc in $services) {
        $name = Get-ContainerName -Service $svc
        $status = docker ps --filter "name=$name" --format "{{.Names}}"
        if ($status -eq $name) {
            $running += $svc
        }
    }
    return $running
}

function Show-MainMenu {
    Write-Header "DVA Assistant - Admin Console"
    
    $running = Test-ContainersRunning
    Write-Host "Running services: $($running -join ', ')" -ForegroundColor $(if ($running.Count -eq 5) { "Green" } else { "Yellow" })
    Write-Host ""
    
    Write-Host "[1] Restart Application" -ForegroundColor Yellow
    Write-Host "[2] GPU Management" -ForegroundColor Yellow
    Write-Host "[3] Switch Model" -ForegroundColor Yellow
    Write-Host "[4] GPU Mode (Enable/Disable)" -ForegroundColor Yellow
    Write-Host "[5] Diagnostic" -ForegroundColor Yellow
    Write-Host "[6] Data Management" -ForegroundColor Yellow
    Write-Host "[7] Manage Models" -ForegroundColor Yellow
    Write-Host "[8] View Logs" -ForegroundColor Yellow
    Write-Host "[9] Database Utilities" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "[Q] Quit" -ForegroundColor Red
    Write-Host ""
}

function Restart-Application {
    Write-Header "Restart Application"
    
    Write-Host "[1] Full restart (stop + start)" -ForegroundColor Yellow
    Write-Host "[2] Rolling restart (no downtime)" -ForegroundColor Yellow
    Write-Host "[3] Restart specific service" -ForegroundColor Yellow
    Write-Host "[4] Rebuild and restart" -ForegroundColor Yellow
    Write-Host "[B] Back to main menu" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Select option"
    
    switch ($choice) {
        "1" {
            Write-Host "Stopping all containers..." -ForegroundColor Yellow
            docker compose -f (Join-Path $PROJECT_ROOT "docker-compose.yml") down
            Write-Host "Starting all containers..." -ForegroundColor Yellow
            docker compose -f (Join-Path $PROJECT_ROOT "docker-compose.yml") up -d
            Write-Host "Done! Waiting for services to be healthy..." -ForegroundColor Green
            Start-Sleep 10
            docker ps --filter "name=dva-" --format "table {{.Names}}\t{{.Status}}"
        }
        "2" {
            Write-Host "Performing rolling restart..." -ForegroundColor Yellow
            docker compose -f (Join-Path $PROJECT_ROOT "docker-compose.yml") restart
            Write-Host "Done!" -ForegroundColor Green
        }
        "3" {
            Write-Host "Available services: ollama, db, web, scraper, scheduler" -ForegroundColor Cyan
            $svc = Read-Host "Enter service name"
            docker compose -f (Join-Path $PROJECT_ROOT "docker-compose.yml") restart $svc
        }
        "4" {
            Write-Host "Rebuilding containers..." -ForegroundColor Yellow
            docker compose -f (Join-Path $PROJECT_ROOT "docker-compose.yml") build
            docker compose -f (Join-Path $PROJECT_ROOT "docker-compose.yml") up -d
            Write-Host "Done!" -ForegroundColor Green
        }
    }
}

function Show-GPUMenu {
    Write-Header "GPU Management"
    
    Write-Host "[1] View GPU statistics (nvidia-smi)" -ForegroundColor Yellow
    Write-Host "[2] Test GPU access in Docker" -ForegroundColor Yellow
    Write-Host "[3] Check NVIDIA driver version" -ForegroundColor Yellow
    Write-Host "[B] Back to main menu" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Select option"
    
    switch ($choice) {
        "1" {
            Write-Host "GPU Statistics:" -ForegroundColor Cyan
            nvidia-smi
        }
        "2" {
            Write-Host "Testing GPU in Docker..." -ForegroundColor Yellow
            docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu20.04 nvidia-smi
        }
        "3" {
            Write-Host "NVIDIA Driver:" -ForegroundColor Cyan
            nvidia-smi --query-gpu=driver_version --format=csv,noheader
        }
    }
}

function Switch-Model {
    Write-Header "Switch Model"
    
    $envFile = Join-Path $PROJECT_ROOT ".env"
    if (-not (Test-Path $envFile)) {
        Write-Host "Error: .env file not found at: $envFile" -ForegroundColor Red
        Write-Host "PROJECT_ROOT detected as: $PROJECT_ROOT" -ForegroundColor Yellow
        return
    }
    
    Write-Host "[1] Change Chat Model (MODEL_NAME)" -ForegroundColor Yellow
    Write-Host "[2] Change Reasoning Model (MODEL_COMPLEX)" -ForegroundColor Yellow
    Write-Host "[3] Change SQL Model (SQL_MODEL)" -ForegroundColor Yellow
    Write-Host "[4] Change Summarizer Model (SUMMARIZER_MODEL)" -ForegroundColor Yellow
    Write-Host "[5] Change Embedding Model (EMBEDDING_MODEL)" -ForegroundColor Yellow
    Write-Host "[6] Change Context Window (LLM_CTX)" -ForegroundColor Yellow
    Write-Host "[B] Back to main menu" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Select option"
    
    if ($choice -eq "B") { return }
    
    $varName = switch ($choice) {
        "1" { "MODEL_NAME" }
        "2" { "MODEL_COMPLEX" }
        "3" { "SQL_MODEL" }
        "4" { "SUMMARIZER_MODEL" }
        "5" { "EMBEDDING_MODEL" }
        "6" { "LLM_CTX" }
        default { $null }
    }
    
    if ($varName) {
        if ($choice -eq "6") {
            $newValue = Read-Host "Enter new $varName value (current: $((Get-Content $envFile | Select-String "^$varName=" -Raw) -replace '.*=', ''))"
        } else {
            Write-Host "Common models:" -ForegroundColor Cyan
            if ($choice -eq "1") { 
                Write-Host "  Chat: llama3.1:8b, llama3:8b, mistral:7b, phi3:3.8b-mini, qwen2.5:7b"
            } elseif ($choice -eq "2") { 
                Write-Host "  Reasoning: qwen2.5:14b, deepseek-coder-v2:236b, mixtral:8x7b"
            } elseif ($choice -eq "3") { 
                Write-Host "  SQL: codellama:7b, llama3.1:8b"
            } elseif ($choice -eq "4") { 
                Write-Host "  Summarizer: qwen2.5:7b, llama3.1:8b"
            } elseif ($choice -eq "5") { 
                Write-Host "  Embeddings: mxbai-embed-large, nomic-embed-text"
            }
            $newValue = Read-Host "Enter new $varName value"
        }
        
        if ($newValue) {
            $content = Get-Content $envFile -Raw
            if ($content -match "^$varName=") {
                $content = $content -replace "^$varName=.*", "$varName=$newValue"
            } else {
                $content += "`n$varName=$newValue"
            }
            Set-Content -Path $envFile -Value $content
            Write-Host "Updated $varName=$newValue" -ForegroundColor Green
            Write-Host "Restarting services..." -ForegroundColor Yellow
            docker compose -f (Join-Path $PROJECT_ROOT "docker-compose.yml") restart web scraper
        }
    }
}

function Set-GPUMode {
    Write-Header "Enable / Disable GPU Mode"
    
    $composeFile = Join-Path $PROJECT_ROOT "docker-compose.yml"
    $content = Get-Content $composeFile -Raw
    
    if ($content -match "count: all") {
        Write-Host "GPU mode is currently: ENABLED" -ForegroundColor Green
        $confirm = Read-Host "Disable GPU mode? (y/n)"
        if ($confirm -eq "y") {
            $content = $content -replace "count: all", "count: 0"
            Set-Content -Path $composeFile -Value $content
            Write-Host "GPU mode disabled. Restart required." -ForegroundColor Yellow
        }
    } else {
        Write-Host "GPU mode is currently: DISABLED" -ForegroundColor Red
        $confirm = Read-Host "Enable GPU mode? (y/n)"
        if ($confirm -eq "y") {
            $content = $content -replace "count: 0", "count: all"
            Set-Content -Path $composeFile -Value $content
            Write-Host "GPU mode enabled. Restart required." -ForegroundColor Green
        }
    }
}

function Show-Diagnostic {
    Write-Header "Full Diagnostic"
    
    $services = @("ollama", "db", "web", "scraper", "scheduler")
    $allHealthy = $true
    
    Write-Host "Container Status:" -ForegroundColor Cyan
    foreach ($svc in $services) {
        $name = Get-ContainerName -Service $svc
        $status = docker ps --filter "name=$name" --format "{{.Status}}"
        if ($status) {
            Write-Host "  $name : $status" -ForegroundColor Green
        } else {
            Write-Host "  $name : NOT RUNNING" -ForegroundColor Red
            $allHealthy = $false
        }
    }
    
    Write-Host ""
    Write-Host "Ollama API Test:" -ForegroundColor Cyan
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
        $models = $response.models.name -join ", "
        Write-Host "  Connected - Models: $models" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to connect: $_" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Database Test:" -ForegroundColor Cyan
    $dbContainer = Get-ContainerName -Service "db"
    $result = docker exec $dbContainer psql -U postgres -d dva_db -t -c "SELECT COUNT(*) FROM scraped_content" 2>$null
    if ($result) {
        Write-Host "  Connected - Content count: $($result.Trim())" -ForegroundColor Green
    } else {
        Write-Host "  Failed to connect" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Disk Space:" -ForegroundColor Cyan
    $drive = (Get-Location).Drive.Name
    $disk = Get-PSDrive -Name $drive
    $freeGB = [math]::Round($disk.Free / 1GB, 2)
    Write-Host "  $drive`: free $freeGB GB"
    
    Write-Host ""
    if ($allHealthy) {
        Write-Host "All systems healthy!" -ForegroundColor Green
    } else {
        Write-Host "Some issues detected. Run option 1 to restart." -ForegroundColor Yellow
    }
}

function Show-DataMenu {
    Write-Header "Data Management"
    
    Write-Host "[1] Create backup" -ForegroundColor Yellow
    Write-Host "[2] List backups" -ForegroundColor Yellow
    Write-Host "[3] Restore from backup" -ForegroundColor Yellow
    Write-Host "[4] Delete old backups (>30 days)" -ForegroundColor Yellow
    Write-Host "[B] Back to main menu" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Select option"
    
    switch ($choice) {
        "1" {
            $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
            $backupPath = Join-Path $BACKUP_DIR $timestamp
            New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
            
            $dbContainer = Get-ContainerName -Service "db"
            
            Write-Host "Backing up database..." -ForegroundColor Yellow
            docker exec $dbContainer pg_dump -U postgres dva_db > (Join-Path $backupPath "db.sql")
            
            $manifest = @{
                timestamp = $timestamp
                type = "full"
                created = Get-Date -Format "o"
            } | ConvertTo-Json
            Set-Content -Path (Join-Path $backupPath "manifest.json") -Value $manifest
            
            Write-Host "Backup created: $backupPath" -ForegroundColor Green
        }
        "2" {
            if (Test-Path $BACKUP_DIR) {
                Get-ChildItem $BACKUP_DIR -Directory | ForEach-Object {
                    $manifest = Join-Path $_.FullName "manifest.json"
                    $date = if (Test-Path $manifest) { 
                        (Get-Content $manifest | ConvertFrom-Json).created 
                    } else { "Unknown" }
                    Write-Host "  $($_.Name) - $date"
                }
            } else {
                Write-Host "No backups found." -ForegroundColor Yellow
            }
        }
        "3" {
            Write-Host "Available backups:" -ForegroundColor Cyan
            if (Test-Path $BACKUP_DIR) {
                $backups = Get-ChildItem $BACKUP_DIR -Directory
                $backups | ForEach-Object { Write-Host "  $($_.Name)" }
                $name = Read-Host "Enter backup folder name to restore"
                $backupPath = Join-Path $BACKUP_DIR $name
                if (Test-Path $backupPath) {
                    $dbContainer = Get-ContainerName -Service "db"
                    $sqlFile = Join-Path $backupPath "db.sql"
                    if (Test-Path $sqlFile) {
                        Write-Host "Restoring database..." -ForegroundColor Yellow
                        Get-Content $sqlFile | docker exec -i $dbContainer psql -U postgres dva_db
                        Write-Host "Restore complete!" -ForegroundColor Green
                    }
                } else {
                    Write-Host "Backup not found!" -ForegroundColor Red
                }
            }
        }
        "4" {
            $cutoff = (Get-Date).AddDays(-30)
            Get-ChildItem $BACKUP_DIR -Directory | Where-Object { $_.LastWriteTime -lt $cutoff } | ForEach-Object {
                Write-Host "Deleting old backup: $($_.Name)" -ForegroundColor Yellow
                Remove-Item $_.FullName -Recurse -Force
            }
            Write-Host "Cleanup complete!" -ForegroundColor Green
        }
    }
}

function Show-ModelMenu {
    Write-Header "Pull / Manage Models"
    
    Write-Host "[1] List installed models" -ForegroundColor Yellow
    Write-Host "[2] Pull a new model" -ForegroundColor Yellow
    Write-Host "[3] Delete a model" -ForegroundColor Yellow
    Write-Host "[B] Back to main menu" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Select option"
    $ollama = Get-ContainerName -Service "ollama"
    
    switch ($choice) {
        "1" {
            Write-Host "Installed models:" -ForegroundColor Cyan
            docker exec $ollama ollama list
        }
        "2" {
            $model = Read-Host "Enter model name (e.g., llama3.1:8b)"
            if ($model) {
                Write-Host "Pulling $model..." -ForegroundColor Yellow
                docker exec $ollama ollama pull $model
                Write-Host "Done!" -ForegroundColor Green
            }
        }
        "3" {
            $model = Read-Host "Enter model name to delete"
            if ($model) {
                docker exec $ollama ollama rm $model
                Write-Host "Model deleted!" -ForegroundColor Green
            }
        }
    }
}

function Show-LogsMenu {
    Write-Header "View Logs"
    
    Write-Host "[1] Web container" -ForegroundColor Yellow
    Write-Host "[2] Scraper container" -ForegroundColor Yellow
    Write-Host "[3] Database" -ForegroundColor Yellow
    Write-Host "[4] Ollama" -ForegroundColor Yellow
    Write-Host "[B] Back to main menu" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Select option"
    
    $container = switch ($choice) {
        "1" { Get-ContainerName -Service "web" }
        "2" { Get-ContainerName -Service "scraper" }
        "3" { Get-ContainerName -Service "db" }
        "4" { Get-ContainerName -Service "ollama" }
        default { $null }
    }
    
    if ($container -and $choice -ne "B") {
        Write-Host "Showing last 50 lines... (Ctrl+C to exit)" -ForegroundColor Cyan
        docker logs --tail 50 -f $container
    }
}

function Show-DatabaseMenu {
    Write-Header "Database Utilities"
    
    Write-Host "[1] Run test_database.py" -ForegroundColor Yellow
    Write-Host "[2] Run scraper (100 pages)" -ForegroundColor Yellow
    Write-Host "[3] Run scraper with --force" -ForegroundColor Yellow
    Write-Host "[4] Run reembed tool" -ForegroundColor Yellow
    Write-Host "[5] Check content stats" -ForegroundColor Yellow
    Write-Host "[B] Back to main menu" -ForegroundColor Gray
    Write-Host ""
    
    $choice = Read-Host "Select option"
    $scraper = Get-ContainerName -Service "scraper"
    
    switch ($choice) {
        "1" {
            docker exec $scraper python -c "import main; print('Import OK')" 2>$null
            if ($?) { Write-Host "Main module OK" -ForegroundColor Green }
        }
        "2" {
            Write-Host "Running scraper..." -ForegroundColor Yellow
            docker exec $scraper python scraper.py 100
        }
        "3" {
            Write-Host "Running scraper with --force..." -ForegroundColor Yellow
            docker exec $scraper python scraper.py 100 --force
        }
        "4" {
            Write-Host "Running reembed..." -ForegroundColor Yellow
            docker exec $scraper python reembed.py
        }
        "5" {
            $db = Get-ContainerName -Service "db"
            docker exec $db psql -U postgres -d dva_db -c "SELECT source_type, COUNT(*) FROM scraped_content GROUP BY source_type"
        }
    }
}

# Main loop
if (-not $NoMenu) {
    $running = $true
    while ($running) {
        Show-MainMenu
        $menuInput = Read-Host "Select option"
        
        switch -regex ($menuInput) {
            "^[1-9]$" {
                switch ($menuInput) {
                    "1" { Restart-Application }
                    "2" { Show-GPUMenu }
                    "3" { Switch-Model }
                    "4" { Set-GPUMode }
                    "5" { Show-Diagnostic }
                    "6" { Show-DataMenu }
                    "7" { Show-ModelMenu }
                    "8" { Show-LogsMenu }
                    "9" { Show-DatabaseMenu }
                }
            }
            "^[Qq]$" { 
                Write-Host "Goodbye!" -ForegroundColor Green
                $running = $false
            }
            "" {
                # Enter pressed with no input - do nothing
            }
            default {
                Write-Host "Invalid option. Please try again." -ForegroundColor Yellow
                Start-Sleep 1
            }
        }
    }
}
