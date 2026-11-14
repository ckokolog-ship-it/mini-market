# build_reports.ps1 -- Reports 14.1.2 on Windows: the reports of the mini market, from the XML of the
# repo (mkreports.py) to the .rdf in the folder of the Reports Server (C:\reports_dev), with
# rwconverter. The environment is that of reports_builder.ps1 of PROPOApplication (retro\oracle\
# windows), which opens the Reports Builder on this PC: create_reptools.cmd once before.
#
#   powershell -ExecutionPolicy Bypass -File build_reports.ps1                    (all of them)
#   powershell -ExecutionPolicy Bypass -File build_reports.ps1 -Reports MM_LEDGER_P
#
# The connection: /@MM_DB, the wallet (forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm), no
# password. The log of each one: <Out>\<name>.log.
# This file is ASCII on purpose: Windows PowerShell 5 reads a file without BOM as ANSI.
param(
  [string[]]$Reports = @('MM_LEDGER_I', 'MM_LEDGER_P', 'MM_SALES', 'MM_VAT', 'MM_MIN_STOCK'),
  [string]$UserId = '/@MM_DB',
  [string]$OracleHome = 'C:\Oracle\Middleware\Oracle_Home',
  [string]$Domain = 'C:\Oracle\Middleware\Oracle_Home\user_projects\domains\forms_domain',
  [string]$Jdk = 'C:\Program Files\Java\jdk-17.0.21.0.3',
  [string]$Instance = 'reptools1',
  [string]$Out = 'C:\reports_dev'
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$OH = $OracleHome
$conv = "$OH\bin\rwconverter.exe"
if (-not (Test-Path $conv)) { throw "not found: $conv" }
$rt = "$Domain\config\fmwconfig\components\ReportsToolsComponent\$Instance"
if (-not (Test-Path "$rt\rwbuilder.conf")) { throw "no $rt\rwbuilder.conf: create_reptools.cmd of PROPOApplication first" }

# as reports_builder.ps1: a short PATH, REPORTS_CLASSPATH from the jars, the instance of the tools
$jars = @(Get-ChildItem "$OH\reports\jlib\*.jar" | ForEach-Object FullName) + @(
  "$OH\jlib\zrclient.jar", "$OH\jlib\utj.jar", "$OH\jlib\dfc.jar",
  "$OH\oracle_common\jlib\ewt3.jar",
  "$OH\oracle_common\modules\oracle.bali.share\share.jar",
  "$OH\oracle_common\modules\oracle.bali.jewt\jewt4.jar",
  "$OH\oracle_common\modules\oracle.help\ohj.jar",
  "$OH\oracle_common\modules\oracle.help\help-share.jar",
  "$OH\oracle_common\modules\oracle.help\oracle_ice.jar",
  "$OH\lib\xmlparserv2.jar", "$OH\lib\xschema.jar"
) | Where-Object { Test-Path $_ }
New-Item -ItemType Directory $Out -Force | Out-Null
$env:REPORTS_CLASSPATH = $jars -join ';'
$env:REPORTS_PATH = "$Out;$OH\reports\templates"
$env:PATH = "$Jdk\bin;$Jdk\bin\server;$OH\bin;$env:SystemRoot\system32;$env:SystemRoot"
$env:CLASSPATH = ''
$env:ORACLE_HOME = $OH
$env:DOMAIN_HOME = $Domain
$env:TNS_ADMIN = "$Domain\config\fmwconfig"
$env:COMPONENT_CONFIG_PATH = $rt
$env:REPORTS_INSTANCE = $rt
$env:CA_GPREFS = "$rt\tools\admin"
$env:CA_UPREFS = "$rt\tools\admin"
$env:NLS_LANG = 'AMERICAN_GREECE.AL32UTF8'

$done = @()
foreach ($r in $Reports) {
  $name = $r.ToUpper()
  $xml = Join-Path $here "$name.xml"
  if (-not (Test-Path $xml)) { throw "no ${xml}: python3 mkreports.py" }
  $rdf = Join-Path $Out "$name.rdf"
  $log = Join-Path $Out "$name.log"
  Remove-Item $rdf, $log -ErrorAction SilentlyContinue
  Write-Host "== ${name}: $xml -> $rdf"
  $p = Start-Process $conv -Wait -PassThru -NoNewWindow -WorkingDirectory $Out -ArgumentList @(
    'batch=yes', "source=$xml", 'stype=xmlfile', "dest=$rdf", 'dtype=rdffile', 'overwrite=yes',
    'compile_all=yes', "userid=$UserId", "logfile=$log")
  if (Test-Path $log) { Get-Content $log | ForEach-Object { Write-Host "   $_" } }
  if ($p.ExitCode -ne 0 -or -not (Test-Path $rdf)) {
    throw "${name}: rwconverter $($p.ExitCode), no .rdf (the messages above, $log)"
  }
  $done += $name
}
Write-Host "== OK: $($done -join ', ') in $Out"
Write-Host "== open one: http://<server>:9012/reports/rwservlet?mm&report=MM_LEDGER_P.rdf&destype=cache&desformat=HTML&P_KIND=C&P_ID=1&P_FROM=01/01/2026&P_TO=31/12/2026"
