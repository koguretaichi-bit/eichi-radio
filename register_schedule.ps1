# Register a Windows scheduled task to run run_daily.ps1 every morning at 6:00.
# Usage: run  .\register_schedule.ps1  in PowerShell.

$taskName = "EichiRadioDeadReckoning"
$script   = Join-Path $PSScriptRoot "run_daily.ps1"

$action   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger  = New-ScheduledTaskTrigger -Daily -At ([DateTime]::Today.AddHours(6))
# -WakeToRun: wake the PC from sleep at 6:00. -StartWhenAvailable: if it was fully
# powered off, run as soon as the PC is next available (catch up the missed day).
# -RestartCount/-RestartInterval: if a run fails (e.g. Gemini 503), retry up to 3
# times, 20 min apart — rides out transient model/network outages.
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 20)

$params = @{
    TaskName    = $taskName
    Action      = $action
    Trigger     = $trigger
    Settings    = $settings
    Description = "Eichi Radio Dead Reckoning - daily 6:00 auto generation"
    Force       = $true
}
Register-ScheduledTask @params

Write-Host "OK: task '$taskName' registered to run daily at 06:00."
Write-Host "  check:  Get-ScheduledTask -TaskName $taskName"
Write-Host "  run now: Start-ScheduledTask -TaskName $taskName"
Write-Host "  remove: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
