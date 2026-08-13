# Apaga todo lo que start-pipeline-stack.ps1 arrancó: la API de
# TrackerAID, Ollama, el contenedor de n8n y Docker Desktop entero (para
# liberar la RAM de la VM de WSL2 que usa por debajo).
#
# Pensado para lanzarse desde el Programador de tareas de Windows el lunes
# por la mañana, con margen de sobra tras el cron de las 6:00 de n8n
# (Schedule Trigger -> espera 10 min -> consulta estado). Con un lote
# normal, a las 7:00 ya debería haber terminado; ajusta la hora del
# trigger si tus lotes son más grandes.
#
# Uso manual: powershell -File scripts\stop-pipeline-stack.ps1

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Parando la API de TrackerAID..."
Get-CimInstance Win32_Process -Filter "Name = 'uvicorn.exe'" -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Output "Parando n8n..."
Push-Location "$repoRoot\n8n"
docker compose down
Pop-Location

Write-Output "Parando Ollama..."
Get-Process "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Output "Cerrando Docker Desktop..."
Get-Process "Docker Desktop" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process "com.docker.backend" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Stack apagado."
