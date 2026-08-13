# Un solo comando: arranca el stack, lanza la ingesta, espera a que
# termine (o hasta MaxWaitMinutes como tope de seguridad) y lo cierra
# todo. Pensado para ejecutarlo tú a mano cuando quieras probar el
# pipeline completo, sin tocar el Programador de tareas de Windows.
#
# Uso (ejecutar desde dentro de la carpeta scripts\):
#   powershell -ExecutionPolicy Bypass -File run-pipeline-once.ps1
# Para un lote pequeño de prueba:
#   powershell -ExecutionPolicy Bypass -File run-pipeline-once.ps1 -MaxConvocatorias 20
#
# No hay una "espera fija de 15-60 min": se consulta /pipeline/status cada
# 30s y se corta en cuanto termina (completado o error). MaxWaitMinutes es
# solo el tope por si algo se queda colgado -- normalmente terminará
# bastante antes.

param(
    [int]$Dias = 7,
    [bool]$ConLLM = $true,
    [int]$MaxConvocatorias = 300,
    [int]$MaxWaitMinutes = 60,
    [int]$PollIntervalSeconds = 30
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot

Write-Output "=== 1/3: Arrancando el stack ==="
& "$scriptDir\start-pipeline-stack.ps1"

Write-Output ""
Write-Output "=== 2/3: Lanzando la ingesta (dias=$Dias con_llm=$ConLLM max=$MaxConvocatorias) ==="

$apiReady = $false
for ($i = 0; $i -lt 24; $i++) {
    try {
        Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3 | Out-Null
        $apiReady = $true
        break
    } catch {
        Start-Sleep -Seconds 5
    }
}
if (-not $apiReady) {
    Write-Error "La API no respondió en 2 min tras arrancar. Revisa uvicorn a mano (logs-uvicorn.txt) y no se apaga nada automáticamente para que puedas investigar."
    exit 1
}

$body = @{ dias = $Dias; con_llm = $ConLLM; max_convocatorias = $MaxConvocatorias } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/pipeline/ingest" -Method Post -Body $body -ContentType "application/json" | Out-Null

$deadline = (Get-Date).AddMinutes($MaxWaitMinutes)
$resultado = $null
do {
    Start-Sleep -Seconds $PollIntervalSeconds
    $resultado = Invoke-RestMethod -Uri "http://localhost:8000/pipeline/status"
    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] estado: $($resultado.estado)"
} while ((Get-Date) -lt $deadline -and $resultado.estado -notin @("completado", "error"))

Write-Output ""
Write-Output "=== Resultado ==="
$resultado | ConvertTo-Json -Depth 5

if ($resultado.estado -eq "en_curso") {
    Write-Output ""
    Write-Output "AVISO: se alcanzó el tope de $MaxWaitMinutes min y el pipeline seguía en curso."
    Write-Output "Se apaga igualmente el stack -- el trabajo en segundo plano de uvicorn se pierde a medio hacer."
    Write-Output "Sube -MaxWaitMinutes si tus lotes tardan más de lo normal."
}

Write-Output ""
Write-Output "=== 3/3: Apagando el stack ==="
& "$scriptDir\stop-pipeline-stack.ps1"
