param([string]$Url = "http://127.0.0.1:8000")
$shell = New-Object -ComObject Shell.Application
$shell.Open($Url)
Write-Host "Opened: $Url"