param(
    [int]$DansMinutes = 0,
    [string]$Heure = "",
    [string]$TacheSource = "Signal Matin",
    [string]$NomTache = "Signal Matin - impression ponctuelle"
)

$ErrorActionPreference = "Stop"

if (($DansMinutes -gt 0) -and $Heure) {
    throw "Choisis -DansMinutes ou -Heure, pas les deux."
}
if (($DansMinutes -le 0) -and (-not $Heure)) {
    throw "Indique -DansMinutes 5 ou -Heure '08:00'."
}

if ($DansMinutes -gt 0) {
    $At = (Get-Date).AddMinutes($DansMinutes)
} else {
    [DateTime]$Parsed = [DateTime]::MinValue
    $Ok = [DateTime]::TryParseExact(
        $Heure,
        "HH:mm",
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::None,
        [ref]$Parsed
    )
    if (-not $Ok) { throw "Heure invalide. Format attendu : HH:mm, par exemple 08:00." }
    $At = Get-Date -Hour $Parsed.Hour -Minute $Parsed.Minute -Second 0
    if ($At -le (Get-Date)) { $At = $At.AddDays(1) }
}

$Source = Get-ScheduledTask -TaskName $TacheSource -ErrorAction Stop
$SourceAction = @($Source.Actions)[0]
if (-not $SourceAction) { throw "La tache '$TacheSource' ne contient aucune action." }
if ($SourceAction.Arguments -notmatch "--print") {
    throw "La tache '$TacheSource' genere le PDF mais n'imprime pas. Reinstalle-la avec -Print."
}

$Action = New-ScheduledTaskAction `
    -Execute $SourceAction.Execute `
    -Argument $SourceAction.Arguments `
    -WorkingDirectory $SourceAction.WorkingDirectory
$Trigger = New-ScheduledTaskTrigger -Once -At $At
$Trigger.EndBoundary = $At.AddHours(2).ToString("s")
$Settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -DeleteExpiredTaskAfter (New-TimeSpan -Hours 12)

Register-ScheduledTask `
    -TaskName $NomTache `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Source.Principal `
    -Description "Impression ponctuelle Signal Matin programmee sans session Codex ouverte" `
    -Force | Out-Null

Write-Host "Impression programmee pour $($At.ToString('dd/MM/yyyy HH:mm:ss'))."
Write-Host "Elle reutilisera exactement Python, le dossier et l'imprimante de '$TacheSource'."
