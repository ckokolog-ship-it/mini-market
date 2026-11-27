# run_api.ps1 -- the REST service of the mini market (mm-api.jar) on Windows, through the wallet of
# the Forms (the alias MM_DB: no password anywhere).
#
#   powershell -ExecutionPolicy Bypass -File run_api.ps1
#   powershell -ExecutionPolicy Bypass -File run_api.ps1 -Port 8091 -Bind 0.0.0.0
#   powershell -ExecutionPolicy Bypass -File run_api.ps1 -Build      (the jar again, after a git pull)
#
# The jar: built here with the Maven Wrapper (mvnw.cmd: it downloads Maven the first time, no install)
# when it is missing or with -Build. Then: http://127.0.0.1:8300/api/health (docs\ODIGIES_REST.md).
# -Bind 127.0.0.1 (the default): this computer only. 0.0.0.0: the network too (the phones), with
# the login; plain HTTP, so only a network you trust. Ctrl+C stops it.
# Once before: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm (PROPOApplication); the first user
# of the shop: db\CREATE_MM_USER.sql.
# Another PC (no Forms there): -TnsAdmin <a folder with tnsnames.ora (MM_DB) and the folder
# forms_wallet>, copied from the Forms server.
# This file is ASCII on purpose: Windows PowerShell 5 reads a file without BOM as ANSI.
param(
  [int]$Port = 8300,
  [string]$Bind = '127.0.0.1',
  [string]$Domain = 'C:\Oracle\Middleware\Oracle_Home\user_projects\domains\forms_domain',
  [string]$TnsAdmin = '',
  [string]$Jdk = 'C:\Program Files\Java\jdk-17.0.21.0.3',
  [switch]$Build
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$jar = Join-Path $here 'target\mm-api.jar'
$java = Join-Path $Jdk 'bin\java.exe'
if (-not (Test-Path $java)) { throw "not found: $java (-Jdk <the folder of a JDK 17 or later>)" }
$env:JAVA_HOME = $Jdk
if ($Build -or -not (Test-Path $jar)) {
  Write-Host "== mvnw package (the first time it downloads Maven and the driver of Oracle: some minutes)"
  Push-Location $here
  try {
    & (Join-Path $here 'mvnw.cmd') -q -B clean package
    if ($LASTEXITCODE) { throw "mvnw package failed (the messages above)" }
  } finally { Pop-Location }
}
if (-not $TnsAdmin) { $TnsAdmin = Join-Path $Domain 'config\fmwconfig' }
if (-not (Test-Path "$TnsAdmin\forms_wallet\cwallet.sso")) {
  throw "no wallet in $TnsAdmin\forms_wallet: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm (or -TnsAdmin)"
}
$env:MM_TNS_ADMIN = $TnsAdmin
$env:MM_WALLET = "$TnsAdmin\forms_wallet"
$env:MM_DB_URL = 'jdbc:oracle:thin:/@MM_DB'
$env:MM_API_PORT = "$Port"
$env:MM_API_BIND = $Bind
Remove-Item Env:\MM_DB_USER, Env:\MM_DB_PASSWORD -ErrorAction SilentlyContinue
& $java -jar $jar
