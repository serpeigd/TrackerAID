# Arranca todo lo que el workflow semanal de n8n necesita: Docker Desktop
# (con el contenedor de n8n), la API de TrackerAID y Ollama.
#
# Pensado para lanzarse desde el Programador de tareas de Windows el
# domingo a las 23:00, para que a las 6:00 del lunes (el Schedule Trigger
# de n8n) todo esté listo. Homólogo de stop-pipeline-stack.ps1.
#
# Uso manual: powershell -File scripts\start-pipeline-stack.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$dockerDesktopExe = "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"

Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Arrancando Docker Desktop..."
if (-not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Start-Process $dockerDesktopExe
}

$maxWaitSeconds = 180
$waited = 0
while ($waited -lt $maxWaitSeconds) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 5
    $waited += 5
}
if ($waited -ge $maxWaitSeconds) {
    Write-Error "Docker no respondió tras $maxWaitSeconds s. Abortando."
    exit 1
}
Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Docker listo (esperados ${waited}s)."

Write-Output "Levantando n8n..."
Push-Location "$repoRoot\n8n"
docker compose up -d
Pop-Location

if (-not (Get-Process "ollama" -ErrorAction SilentlyContinue)) {
    Write-Output "Arrancando Ollama..."
    Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}

Write-Output "Arrancando la API de TrackerAID (uvicorn)..."
Start-Process powershell -ArgumentList @(
    "-NoProfile", "-WindowStyle", "Hidden", "-Command",
    "cd '$repoRoot'; .\.venv\Scripts\uvicorn.exe trackeraid.api:app --host 0.0.0.0 --port 8000 *> logs-uvicorn.txt"
)

Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Stack arrancado. n8n disparará el pipeline según su propio cron."
