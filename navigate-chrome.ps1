# Navigate Chrome to URL via CDP
$ErrorActionPreference = "SilentlyContinue"

try {
    # Get first target
    $targets = Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/list" -TimeoutSec 5
    $targetId = $targets[0].id
    
    Write-Host "Target ID: $targetId"
    
    # Navigate using the session Http endpoint
    $navUrl = "http://127.0.0.1:9222/json/session/$targetId/Page.navigate"
    $body = @{url="http://127.0.0.1:8000/"} | ConvertTo-Json
    
    $result = Invoke-RestMethod -Uri $navUrl -Method POST -Body $body -ContentType "application/json" -TimeoutSec 10
    Write-Host "Navigate result: $result"
    
    # List tabs after
    Start-Sleep -Seconds 1
    $newTargets = Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/list"
    Write-Host "=== Tabs ==="
    foreach ($t in $newTargets) {
        Write-Host ("  " + $t.title + " -> " + $t.url)
    }
}
catch {
    Write-Host "Error: $_"
}