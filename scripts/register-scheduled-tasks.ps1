# Registra en el Programador de tareas de Windows las 2 tareas del stack
# semanal de TrackerAID. NO se ejecuta solo ni desde Claude — tienes que
# lanzarlo tú mismo, a mano, en tu propia PowerShell:
#
#   powershell -ExecutionPolicy Bypass -File scripts\register-scheduled-tasks.ps1
#
# Qué hace cada tarea:
#   - "TrackerAID - Arrancar stack": domingo 22:45 -> start-pipeline-stack.ps1
#     (Docker Desktop + n8n + Ollama + API). 15 min de margen antes de que
#     el Schedule Trigger de n8n dispare el pipeline a las 23:00.
#   - "TrackerAID - Apagar stack": domingo 23:45 -> stop-pipeline-stack.ps1.
#     45 min de margen tras el arranque = ~35 min tras el disparo de n8n,
#     de sobra para la espera de 10 min + el procesado del lote.
#
# Ninguna de las dos fuerza el encendido del PC si está apagado del todo
# -- "Wake the computer to run this task" solo despierta de suspensión,
# nunca enciende una máquina apagada. Si el PC está apagado, esa semana
# simplemente no se ejecuta el pipeline (comportamiento pedido a propósito).
#
# Para revertir todo: quitar-scheduled-tasks.ps1 (o a mano desde la GUI
# de Task Scheduler, buscando "TrackerAID").

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Register-StackTask {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [string]$AtTime,
        [switch]$WakeToRun
    )

    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-ExecutionPolicy Bypass -File `"$ScriptPath`""

    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $AtTime

    $settingsParams = @{
        ExecutionTimeLimit = (New-TimeSpan -Hours 1)
        StartWhenAvailable = $false
    }
    if ($WakeToRun) { $settingsParams["WakeToRun"] = $true }
    $settings = New-ScheduledTaskSettingsSet @settingsParams

    # "Run only when user is logged on" (RunLevel por defecto de esta
    # llamada) -- no pide ni guarda tu contraseña de Windows. Requiere
    # sesión iniciada (aunque esté bloqueada) a esa hora.
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger `
        -Settings $settings -Force | Out-Null

    Write-Output "Registrada: $Name ($AtTime, domingo)"
}

Register-StackTask -Name "TrackerAID - Arrancar stack" `
    -ScriptPath "$repoRoot\scripts\start-pipeline-stack.ps1" `
    -AtTime "22:45" -WakeToRun

Register-StackTask -Name "TrackerAID - Apagar stack" `
    -ScriptPath "$repoRoot\scripts\stop-pipeline-stack.ps1" `
    -AtTime "23:45"

Write-Output ""
Write-Output "Hecho. Comprueba en Task Scheduler (busca 'TrackerAID') y prueba"
Write-Output "cada una con clic derecho -> Run antes de fiarte del domingo real."
