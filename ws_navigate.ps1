# Navigate Chrome to URL via WebSocket
Add-Type -AssemblyName System.Net.WebSockets
Add-Type -AssemblyName System.Threading

$ErrorActionPreference = "Stop"

# Get WebSocket URL
$version = Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 5
$wsUrl = $version.webSocketDebuggerUrl
Write-Host "WebSocket: $wsUrl"

# Get target ID
$targets = Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/list" -TimeoutSec 5
$targetId = $targets[0].id
Write-Host "Target: $targetId"

# Use .NET WebSocket client
$client = [System.Net.WebSockets.ClientWebSocket]::new()
$ct = [Threading.CancellationToken]::None

try {
    $client.ConnectAsync($wsUrl, $ct).Wait()
    Write-Host "Connected to WebSocket"
    
    # Send attach command
    $attachCmd = @{
        id = 1
        method = "Target.attachToTarget"
        params = @{
            targetId = $targetId
            flatten = $true
        }
    } | ConvertTo-Json -Compress
    
    $client.SendAsync([ArraySegment[byte]][Text.Encoding]::UTF8.GetBytes($attachCmd), [Net.WebSockets.WebSocketMessageType]::Text, $true, $ct).Wait()
    
    # Receive response
    $buffer = [byte[]]::new(8192)
    $result = $client.ReceiveAsync([ArraySegment[byte]]$buffer, $ct).Wait()
    $response = [Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
    Write-Host "Attach: $response"
    
    # Send navigate command
    $navCmd = @{
        id = 2
        method = "Page.navigate"
        params = @{
            url = "http://127.0.0.1:8000/"
        }
    } | ConvertTo-Json -Compress
    
    $client.SendAsync([ArraySegment[byte]][Text.Encoding]::UTF8.GetBytes($navCmd), [Net.WebSockets.WebSocketMessageType]::Text, $true, $ct).Wait()
    
    # Receive response
    Start-Sleep -Milliseconds 500
    $result = $client.ReceiveAsync([ArraySegment[byte]]$buffer, $ct).Wait()
    $response = [Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
    Write-Host "Navigate: $response"
    
    $client.CloseAsync([Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "Done", $ct).Wait()
    Write-Host "Done!"
}
catch {
    Write-Host "Error: $_"
}