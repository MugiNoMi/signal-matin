param(
    [string]$Time = "08:00",
    [switch]$Print,
    [switch]$Duplex,
    [string]$Printer = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python -ErrorAction Stop).Source
$Main = Join-Path $Root "main.py"
$Arguments = @("`"$Main`"")

if ($Print) {
    $Arguments += @("--print", "--live", "--confirm")
    if ($Duplex) { $Arguments += "--duplex" }
    if ($Printer) { $Arguments += @("--printer", "`"$Printer`"") }
} else {
    $Arguments += @("--generate", "--live")
}

$Action = New-ScheduledTaskAction -Execute $Python -Argument ($Arguments -join " ") -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable
Register-ScheduledTask -TaskName "Signal Matin" -Action $Action -Trigger $Trigger `
    -Settings $Settings -Description "Genere le journal personnel Signal Matin" -Force | Out-Null

Write-Host "Tache 'Signal Matin' installee pour $Time."
if (-not $Print) {
    Write-Host "Generation seulement. L'impression automatique n'est pas activee."
}
