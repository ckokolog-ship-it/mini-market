# run_docker.ps1 -- the REST service of the mini market (mm-api.jar) in Docker (Docker Desktop), instead of
# the Windows service (install_service.ps1): the same port, so one of the two at a time.
#
#   powershell -ExecutionPolicy Bypass -File run_docker.ps1            (build the jar, start: and after
#                                                                     a git pull, the new one)
#   powershell -ExecutionPolicy Bypass -File run_docker.ps1 -Logs
#   powershell -ExecutionPolicy Bypass -File run_docker.ps1 -Down
#
# The container: "mm-api", started again with Docker Desktop (restart: unless-stopped; Docker Desktop itself
# starts when someone logs on to Windows: Settings, General, "Start Docker Desktop when you sign in").
# The database through the wallet of the Forms (read-only in the container) and the tnsnames.ora of the
# domain, copied to api\docker\tns (localhost there becomes host.docker.internal: the computer).
# This file is ASCII on purpose: Windows PowerShell 5 reads a file without BOM as ANSI.
param(
  [int]$Port = 8090,
  [string]$Domain = 'C:\Oracle\Middleware\Oracle_Home\user_projects\domains\forms_domain',
  [string]$TnsAdmin = '',
  [string]$Jdk = 'C:\Program Files\Java\jdk-17.0.21.0.3',
  [switch]$Logs,
  [switch]$Down
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
Set-Location $here

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'docker not found: install Docker Desktop' }
docker info *> $null
if ($LASTEXITCODE) { throw 'Docker is not running: open Docker Desktop, wait for "Engine running", then this again' }

if ($Logs) { docker logs --tail 200 -f mm-api; exit 0 }
if ($Down) {
  $env:MM_WALLET_DIR = $here                       # (any folder: compose wants one)
  docker compose down
  Write-Host '== mm-api stopped (the container removed; started again by run_docker.ps1)'
  exit 0
}

$svc = Get-Service -Name 'mm-api' -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq 'Running') {
  throw 'the Windows service mm-api runs on the same port: stop it first (install_service.ps1 -Uninstall, or Stop-Service mm-api as an administrator)'
}

# the jar (the image only adds a Java runtime to it)
$java = "$Jdk\bin\java.exe"
if (-not (Test-Path $java)) { throw "not found: $java (-Jdk <the folder of a JDK 17 or later>)" }
$env:JAVA_HOME = $Jdk
Write-Host '== mvnw package'
& (Join-Path $here 'mvnw.cmd') -q -B clean package
if ($LASTEXITCODE) { throw 'mvnw package failed (the messages above)' }

# the wallet and the tnsnames.ora of the container
if (-not $TnsAdmin) { $TnsAdmin = "$Domain\config\fmwconfig" }
$wallet = "$TnsAdmin\forms_wallet"
if (-not (Test-Path "$wallet\cwallet.sso")) {
  throw "no wallet in ${wallet}: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm (or -TnsAdmin)"
}
if (-not (Select-String -Path "$TnsAdmin\tnsnames.ora" -Pattern '^\s*MM_DB\s*=' -Quiet)) {
  throw "no MM_DB in $TnsAdmin\tnsnames.ora: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm"
}
$tnsDir = Join-Path $here 'docker\tns'
New-Item -ItemType Directory -Force -Path $tnsDir | Out-Null
$tns = (Get-Content "$TnsAdmin\tnsnames.ora" -Raw) -replace '(?i)(HOST\s*=\s*)(localhost|127\.0\.0\.1)', '$1host.docker.internal'
[IO.File]::WriteAllText((Join-Path $tnsDir 'tnsnames.ora'), $tns, (New-Object Text.ASCIIEncoding))

$env:MM_WALLET_DIR = $wallet
$env:MM_API_PORT = "$Port"
Write-Host '== docker compose up (the first time: the Java runtime, some minutes)'
docker compose up -d --build
if ($LASTEXITCODE) { throw 'docker compose failed (the messages above)' }

for ($k = 0; $k -lt 40; $k++) {
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
    Write-Host ("== http://127.0.0.1:$Port/api/health: " + ($r | ConvertTo-Json -Compress))
    Write-Host "== mm-api runs in Docker: http://<the IP of this computer>:$Port/  (run_docker.ps1 -Logs)"
    exit 0
  } catch { Start-Sleep -Seconds 2 }
}
Write-Host '== no answer yet: run_docker.ps1 -Logs'
exit 1
