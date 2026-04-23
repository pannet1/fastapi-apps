param(
    [string]$Url = "http://127.0.0.1:8000"
)

# Start Chrome with remote debugging
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$userDataDir = "$env:TEMP\chrome-devtools"
$port = 9222

# Create directory if needed
if (!(Test-Path $userDataDir)) {
    New-Item -ItemType Directory -Path $userDataDir -Force | Out-Null
}

# Kill existing chrome with debug port if any
Get-Process -Name chrome -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | Stop-Process -Force -ErrorAction SilentlyContinue

# Start Chrome with debugging
Start-Process $chromePath -ArgumentList "--remote-debugging-port=$port","--no-first-run","--user-data-dir=$userDataDir" -WindowStyle Normal

# Wait and verify
Start-Sleep -Seconds 2
$response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/json/version" -TimeoutSec 3 -ErrorAction SilentlyContinue

if ($response) {
    Write-Host "Chrome DevTools listening on port $port"
    $response | ConvertTo-Json
    
    # Navigate to the app URL
    Write-Host "Navigating to $Url..."
    Start-Process $Url
} else {
    Write-Host "Failed to connect on port $port"
}