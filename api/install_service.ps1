# install_service.ps1 -- the REST service of the mini market (mm-api.jar) as a Windows service: no
# window, it starts with Windows (delayed), it starts again by itself if it stops. Through the wallet of
# the Forms (the alias MM_DB), as run_api.ps1: no password anywhere. As an administrator:
#
#   powershell -ExecutionPolicy Bypass -File install_service.ps1              (install, or update: the
#                                                                             jar again after a git pull)
#   powershell -ExecutionPolicy Bypass -File install_service.ps1 -Bind 127.0.0.1   (this computer only)
#   powershell -ExecutionPolicy Bypass -File install_service.ps1 -Status
#   powershell -ExecutionPolicy Bypass -File install_service.ps1 -Uninstall
#
# The service: "mm-api" (services.msc: "Mini market API"), run by WinSW 2.12.0 (MIT,
# github.com/winsw/winsw: downloaded the first time, its SHA-256 checked). Its folder: api\service (the
# jar it runs, its settings mm-api.xml, its logs in api\service\logs). -Bind 0.0.0.0 (the default
# here): the network too (the phones), with a rule of the firewall for the port, private networks only.
# -DryRun: the files of the service only, nothing installed (no administrator needed).
# This file is ASCII on purpose: Windows PowerShell 5 reads a file without BOM as ANSI.
param(
  [int]$Port = 8300,
  [string]$Bind = '0.0.0.0',
  [string]$Domain = 'C:\Oracle\Middleware\Oracle_Home\user_projects\domains\forms_domain',
  [string]$TnsAdmin = '',
  [string]$Jdk = 'C:\Program Files\Java\jdk-17.0.21.0.3',
  [string]$DependsOn = 'OracleServiceFREE',
  [switch]$Status,
  [switch]$Uninstall,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$svcDir = Join-Path $here 'service'
$exe = Join-Path $svcDir 'mm-api.exe'
$name = 'mm-api'
$winswUrl = 'https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe'
$winswSha = '05B82D46AD331CC16BDC00DE5C6332C1EF818DF8CEEFCD49C726553209B3A0DA'
$rule = "mm-api $Port"

# (Get-Service: Windows only; -DryRun runs anywhere)
function Get-Svc([string]$n) {
  if ($IsLinux -or $IsMacOS) { return $null }
  return Get-Service -Name $n -ErrorAction SilentlyContinue
}

function Test-Admin {
  $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-Health {
  for ($k = 0; $k -lt 30; $k++) {
    try {
      $r = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
      Write-Host ("== http://127.0.0.1:$Port/api/health: " + ($r | ConvertTo-Json -Compress))
      return $true
    } catch { Start-Sleep -Seconds 2 }
  }
  Write-Host "== no answer on port $Port yet: see $svcDir\logs\mm-api.out.log and mm-api.err.log"
  return $false
}

if ($Status) {
  $s = Get-Svc $name
  if (-not $s) { Write-Host "== the service $name is not installed"; exit 0 }
  Write-Host ("== the service ${name}: " + $s.Status + ', start ' + $s.StartType)
  if ($s.Status -eq 'Running') { [void](Show-Health) }
  exit 0
}

if (-not $DryRun -and -not (Test-Admin)) {
  throw 'as an administrator: right click on PowerShell (or cmd), "Run as administrator", then this again'
}

if ($Uninstall) {
  if ((Get-Svc $name) -and (Test-Path $exe)) {
    & $exe stop | Out-Null
    & $exe uninstall
    if ($LASTEXITCODE) { throw 'the uninstall failed (the messages above)' }
  }
  Get-NetFirewallRule -DisplayName 'mm-api *' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  Write-Host "== the service $name removed (its folder stays: $svcDir)"
  exit 0
}

# the jar: built again here (as run_api.ps1 -Build), then copied to the folder of the service, so that
# a later build does not touch the one that runs
$java = "$Jdk\bin\java.exe"
if (-not $DryRun -and -not (Test-Path $java)) { throw "not found: $java (-Jdk <the folder of a JDK 17 or later>)" }
$jar = Join-Path $here 'target\mm-api.jar'
if (-not $DryRun) {
  $env:JAVA_HOME = $Jdk
  Write-Host '== mvnw package (the jar of the service)'
  Push-Location $here
  try {
    & (Join-Path $here 'mvnw.cmd') -q -B clean package
    if ($LASTEXITCODE) { throw 'mvnw package failed (the messages above)' }
  } finally { Pop-Location }
}
if (-not $TnsAdmin) { $TnsAdmin = "$Domain\config\fmwconfig" }
if (-not $DryRun -and -not (Test-Path "$TnsAdmin\forms_wallet\cwallet.sso")) {
  throw "no wallet in $TnsAdmin\forms_wallet: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm (or -TnsAdmin)"
}

New-Item -ItemType Directory -Force -Path $svcDir, (Join-Path $svcDir 'logs') | Out-Null
if (-not $DryRun -and -not (Test-Path $exe)) {
  Write-Host '== WinSW 2.12.0 (the runner of the service), the first time'
  $tmp = "$exe.download"
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $winswUrl -OutFile $tmp -UseBasicParsing
  $sha = (Get-FileHash -Algorithm SHA256 $tmp).Hash
  if ($sha -ne $winswSha) {
    Remove-Item $tmp -Force
    throw "WinSW: SHA-256 $sha, not the one expected: not used"
  }
  Move-Item $tmp $exe -Force
}

# the service stopped while its jar and its settings change
$svc = Get-Svc $name
if ($svc -and -not $DryRun -and $svc.Status -ne 'Stopped') {
  Write-Host "== stop $name"
  & $exe stop | Out-Null
  $svc.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
}
if (-not $DryRun) { Copy-Item $jar (Join-Path $svcDir 'mm-api.jar') -Force }

function X([string]$s) { return [System.Security.SecurityElement]::Escape($s) }
$depend = ''
if ($DependsOn -and (Get-Svc $DependsOn)) {
  $depend = "  <depend>$(X $DependsOn)</depend>`r`n"
}
$xml = @"
<!-- made by install_service.ps1: run it again to change it -->
<service>
  <id>$name</id>
  <name>Mini market API (mm-api)</name>
  <description>The REST service and the pages of the mini market, port $Port ($Bind).</description>
  <executable>$(X $java)</executable>
  <arguments>-Xmx512m -jar "%BASE%\mm-api.jar"</arguments>
  <workingdirectory>%BASE%</workingdirectory>
  <env name="JAVA_HOME" value="$(X $Jdk)" />
  <env name="MM_TNS_ADMIN" value="$(X $TnsAdmin)" />
  <env name="MM_WALLET" value="$(X "$TnsAdmin\forms_wallet")" />
  <env name="MM_DB_URL" value="jdbc:oracle:thin:/@MM_DB" />
  <env name="MM_API_PORT" value="$Port" />
  <env name="MM_API_BIND" value="$(X $Bind)" />
$depend  <startmode>Automatic</startmode>
  <delayedAutoStart>true</delayedAutoStart>
  <onfailure action="restart" delay="10 sec" />
  <onfailure action="restart" delay="30 sec" />
  <onfailure action="restart" delay="60 sec" />
  <resetfailure>1 hour</resetfailure>
  <stoptimeout>15 sec</stoptimeout>
  <logpath>%BASE%\logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>5</keepFiles>
  </log>
</service>
"@
$xmlFile = Join-Path $svcDir 'mm-api.xml'
[IO.File]::WriteAllText($xmlFile, $xml, (New-Object Text.UTF8Encoding($false)))
Write-Host "== $xmlFile"
if ($DryRun) { Write-Host '== -DryRun: nothing installed'; exit 0 }

if (-not $svc) {
  & $exe install
  if ($LASTEXITCODE) { throw 'the install of the service failed (the messages above)' }
} else {
  # (WinSW 2 has no "refresh": its settings of the service itself, as the start or the dependency,
  # change by an uninstall and an install; the service is stopped here already)
  & $exe uninstall
  if ($LASTEXITCODE) { throw 'the uninstall of the old service failed (the messages above)' }
  for ($k = 0; $k -lt 15 -and (Get-Svc $name); $k++) { Start-Sleep -Seconds 1 }   # gone (services.msc closed)
  & $exe install
  if ($LASTEXITCODE) { throw 'the install of the service failed (the messages above)' }
}

# the network: the port open for private networks only (as the WiFi of the shop)
if ($Bind -ne '127.0.0.1') {
  if (-not (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $rule -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private | Out-Null
    Write-Host "== firewall: $rule (private networks)"
  }
}

& $exe start
if ($LASTEXITCODE) { throw "the start failed: see $svcDir\logs" }
if (Show-Health) {
  Write-Host "== the service $name runs: http://<the IP of this computer>:$Port/ (services.msc: Mini market API)"
}
