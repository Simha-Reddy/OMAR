Param(
  [string]$BindHost = $(if ($env:HOST) { $env:HOST } else { '127.0.0.1' }),
  [int]$Port = $(if ($env:PORT) { [int]$env:PORT } else { 5050 }),
  [switch]$NoInstall,
  [switch]$UpgradePip
)

$ErrorActionPreference = 'Stop'

# App root is parent of the scripts folder
$AppRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $AppRoot 'python\python.exe'
$Requirements = Join-Path $AppRoot 'requirements.txt'
$RunServer = Join-Path $AppRoot 'run_server.py'

if (!(Test-Path $PythonExe)) {
  Write-Error "Embedded Python not found at $PythonExe"
  exit 1
}

Write-Host "Using embedded Python:" -ForegroundColor Cyan
& $PythonExe -V

try {
  if ($UpgradePip) {
    Write-Host "Upgrading pip..." -ForegroundColor DarkCyan
    & $PythonExe -m pip install --upgrade pip
  }
  if (-not $NoInstall) {
    Write-Host "Installing requirements from $Requirements ..." -ForegroundColor DarkCyan
    & $PythonExe -m pip install -r $Requirements
  }
}
catch {
  Write-Warning "Package install step encountered an error: $_"
}

$env:HOST = $BindHost
$env:PORT = "$Port"

Write-Host ("Starting OMAR_refactor server on http://{0}:{1} (waitress)..." -f $BindHost, $Port) -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray

& $PythonExe $RunServer
