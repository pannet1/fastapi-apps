param(
    [string]$Url = "http://127.0.0.1:8000",
    [string]$DebugPort = "9222"
)

# Start Chrome with remote debugging
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$userDataDir = "$env:TEMP\chrome-devtools"
$port = $DebugPort

# Create directory if needed
if (!(Test-Path $userDataDir)) {
    New-Item -ItemType Directory -Path $userDataDir -Force | Out-Null
}

# Kill existing chrome instances
Get-Process -Name chrome -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Start Chrome with debugging on all interfaces
Start-Process $chromePath -ArgumentList "--remote-debugging-port=$port","--remote-debugging-address=0.0.0.0","--user-data-dir=$userDataDir" -WindowStyle Hidden

# Wait and verify
Start-Sleep -Seconds 3
$response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/json/version" -TimeoutSec 5 -ErrorAction SilentlyContinue

if ($response) {
    Write-Host "Chrome DevTools listening on port $port"
    $response | ConvertTo-Json
    
    # Navigate to the app URL using shell
    Start-Sleep -Seconds 1
    $shell = New-Object -ComObject Shell.Application
    $shell.Open($Url)
    Write-Host "Navigating to $Url..."
} else {
    Write-Host "Failed to connect on port $port"
}