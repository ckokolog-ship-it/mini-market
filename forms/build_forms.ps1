# build_forms.ps1 -- Forms 14.1.2 on Windows: the forms of the mini market, from the XML of the repo
# to the .fmx in the folder of FORMS_PATH (C:\forms_dev). build_forms.sh is the same for Linux.
#
#   powershell -ExecutionPolicy Bypass -File build_forms.ps1                    (all three)
#   powershell -ExecutionPolicy Bypass -File build_forms.ps1 -Forms MM_ITEMS
#
# Before, once: the database (db\INSTALL.sql demo) and the wallet with the alias MM_DB, from the
# folder retro\oracle\windows of PROPOApplication, as administrator:
#   forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm
# Then no password anywhere: sqlplus and frmcmp connect as /@MM_DB (the wallet of the domain).
# Open a form: fsal.ps1 -Form MM_ITEMS -Config mm
#
# - MM_TEXT.sql first (the Greek of the forms), with NLS_LANG ...AL32UTF8: it is UTF-8;
# - XML2Forms through java.exe straight, with the four jars of the Oracle_Home;
# - frmcmp.exe with batch=yes; NLS_LANG EL8MSWIN1253 for the tools (the forms are ASCII).
# This file is ASCII on purpose: Windows PowerShell 5 reads a file without BOM as ANSI.
param(
  [string[]]$Forms = @('MM_ITEMS', 'MM_CUSTOMERS', 'MM_SUPPLIERS'),
  [string]$UserId = '/@MM_DB',
  [string]$OracleHome = 'C:\Oracle\Middleware\Oracle_Home',
  [string]$Domain = 'C:\Oracle\Middleware\Oracle_Home\user_projects\domains\forms_domain',
  [string]$Jdk = 'C:\Program Files\Java\jdk-17.0.21.0.3',
  [string]$Out = 'C:\forms_dev'
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

$java = Join-Path $Jdk 'bin\java.exe'
$cmp = Join-Path $OracleHome 'bin\frmcmp.exe'
$sqlplus = Join-Path $OracleHome 'bin\sqlplus.exe'
foreach ($f in $java, $cmp, $sqlplus) { if (-not (Test-Path $f)) { throw "not found: $f" } }
$cp = (('frmxmltools.jar', 'frmjdapi.jar', 'xmlparserv2.jar', 'xschema.jar') | ForEach-Object {
  $j = Get-ChildItem $OracleHome -Recurse -Filter $_ -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $j) { throw "$_ : not found under $OracleHome" }
  $j.FullName
}) -join ';'
New-Item -ItemType Directory $Out -Force | Out-Null

$env:ORACLE_HOME = $OracleHome
$env:TNS_ADMIN = Join-Path $Domain 'config\fmwconfig'
$env:PATH = "$Jdk\bin;$Jdk\bin\server;$OracleHome\bin;$env:PATH"

# the Greek of the forms
$env:NLS_LANG = 'GREEK_GREECE.AL32UTF8'
Write-Host "== ..\db\MM_TEXT.sql"
$o = 'exit' | & $sqlplus -s $UserId "@$here\..\db\MM_TEXT.sql" | Out-String
Write-Host $o
if ($o -match 'ORA-|SP2-') {
  throw "MM_TEXT.sql: the messages above (the wallet: forms_wallet.cmd -DbUser mm -Alias MM_DB -Section mm)"
}
$env:NLS_LANG = 'AMERICAN_GREECE.EL8MSWIN1253'

$done = @()
foreach ($form in $Forms) {
  $name = $form.ToUpper()
  if (-not (Test-Path "$here\$name.xml")) { Write-Host "== ${name}: no $here\$name.xml"; continue }
  Push-Location $here
  try {
    Remove-Item "$name.fmb" -ErrorAction SilentlyContinue
    Write-Host "== $name.xml -> $name.fmb"
    & $java -cp $cp oracle.forms.util.xmltools.XML2Forms OVERWRITE=YES "$name.xml"
    if (-not (Test-Path "$name.fmb")) { Write-Host "== no $name.fmb: the messages above"; continue }
    Move-Item "$name.fmb" $Out -Force
  } finally { Pop-Location }

  Push-Location $Out
  try {
    Remove-Item "$name.fmx", "$name.err" -ErrorAction SilentlyContinue
    Write-Host "== $name.fmb -> $Out\$name.fmx"
    & $cmp module="$name.fmb" userid=$UserId module_type=form compile_all=yes batch=yes | Out-Host
    if (Test-Path "$name.fmx") {
      Write-Host "== $Out\$name.fmx: OK"
      $done += $name
    } else {
      Write-Host "== no $name.fmx: $Out\$name.err"
      if (Test-Path "$name.err") { Get-Content "$name.err" -Tail 30 | Out-Host }
    }
  } finally { Pop-Location }
}
Write-Host "== done: $($done -join ', ')  -- open with: fsal.ps1 -Form <FORM> -Config mm"
