# tools/programar_en_windows.ps1
# ===============================
# Registra una tarea programada de Windows que corre
#   python tools\actualizar_desde_pc.py --publicar
# de lunes a viernes a las 08:30 y a las 12:30 (hora de la PC), desde un clon del
# repo en la rama `desarrollo`. Reemplaza al cron de GitHub mientras el BORA no
# responda a los servidores de GitHub. No toca ningún archivo del repo.
#
# Uso (PowerShell, una sola vez):
#   .\tools\programar_en_windows.ps1 -Repo C:\ruta\al\clon -Python C:\ruta\al\venv\Scripts\python.exe
# Quitarla:
#   Unregister-ScheduledTask -TaskName "Monitor BORA - actualizar desde PC" -Confirm:$false
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$Python,
    [string]$Nombre = "Monitor BORA - actualizar desde PC"
)

if (-not (Test-Path (Join-Path $Repo "tools\actualizar_desde_pc.py"))) { throw "No encuentro tools\actualizar_desde_pc.py en $Repo" }
if (-not (Test-Path $Python)) { throw "No encuentro $Python" }

$log = Join-Path $Repo "actualizar_desde_pc.log"
$accion = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $Repo `
    -Argument "/c `"`"$Python`" -W ignore tools\actualizar_desde_pc.py --publicar >> `"$log`" 2>&1`""
$dias = "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
$disparadores = @(
    New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dias -At "08:30"
    New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dias -At "12:30"
)
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparadores -Settings $ajustes `
    -Description "Genera y publica los reportes del BORA que falten (ver REFORMAS_2026-10-30.md)" -Force
Write-Host "Tarea '$Nombre' registrada. Log: $log"
