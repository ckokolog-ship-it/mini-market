# run_api.ps1 -- the REST service of the mini market (mm-api.jar) on Windows, through the wallet of
# the Forms (the alias MM_DB: no password anywhere). The jar: mvn -q -B package in this folder (the
# first time this script builds it, if Maven is there).
#
#   powershell -ExecutionPolicy Bypass -File run_api.ps1
#   powershell -ExecutionPolicy Bypass -File run_api.ps1 -Port 8091
#
# Then: http://127.0.0.1:8090/api/health, /api/items?q=..., ... (docs\ODIGIES_REST.md). It listens on
# 127.0.0.1 only (this computer): there is no login yet. Ctrl+C stops it.
# Once before: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm (PROPOApplication).
# This file is ASCII on purpose: Windows PowerShell 5 reads a file without BOM as ANSI.
param(
  [int]$Port = 8090,
  [string]$Bind = '127.0.0.1',
  [string]$Domain = 'C:\Oracle\Middleware\Oracle_Home\user_projects\domains\forms_domain',
  [string]$Jdk = 'C:\Program Files\Java\jdk-17.0.21.0.3'
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$jar = Join-Path $here 'target\mm-api.jar'
$java = Join-Path $Jdk 'bin\java.exe'
if (-not (Test-Path $java)) { throw "not found: $java (-Jdk <the folder of a JDK 17 or later>)" }
if (-not (Test-Path $jar)) {
  if (-not (Get-Command mvn -ErrorAction SilentlyContinue)) { throw "no $jar, and no mvn to build it" }
  Write-Host "== mvn package (the first time: it downloads the driver)"
  Push-Location $here
  try { & mvn -q -B package; if ($LASTEXITCODE) { throw "mvn package failed" } } finally { Pop-Location }
}
$tns = Join-Path $Domain 'config\fmwconfig'
if (-not (Test-Path "$tns\forms_wallet\cwallet.sso")) {
  throw "no wallet in $tns\forms_wallet: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm"
}
$env:MM_TNS_ADMIN = $tns
$env:MM_WALLET = "$tns\forms_wallet"
$env:MM_DB_URL = 'jdbc:oracle:thin:/@MM_DB'
$env:MM_API_PORT = "$Port"
$env:MM_API_BIND = $Bind
Remove-Item Env:\MM_DB_USER, Env:\MM_DB_PASSWORD -ErrorAction SilentlyContinue
& $java -jar $jar
