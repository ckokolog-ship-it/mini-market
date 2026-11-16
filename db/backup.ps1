# backup.ps1 -- the backup of the database of the mini market (all of the schema MM: the items, the
# documents, the stock, the users, the cards with their PINs), with Data Pump (expdp), through the
# wallet of the Forms (the alias MM_DB: no password anywhere). As an administrator:
#
#   powershell -ExecutionPolicy Bypass -File backup.ps1                  (a backup now)
#   powershell -ExecutionPolicy Bypass -File backup.ps1 -Install -CopyTo E:\mm_backup
#                                     (every day at 23:15, as a task of Windows; and one now)
#   powershell -ExecutionPolicy Bypass -File backup.ps1 -Status          (the task, the last backups)
#   powershell -ExecutionPolicy Bypass -File backup.ps1 -Restore C:\mm_backup\mm_20261116_2315.dmp
#   powershell -ExecutionPolicy Bypass -File backup.ps1 -Uninstall       (the task removed; the files stay)
#
# The files: C:\mm_backup\mm_<date>_<time>.dmp (and its .log), the newest -Keep (14) kept; with
# -CopyTo (another disk, a USB disk) a copy there too, if it is plugged in. The folder: only the
# administrators and SYSTEM may open it (a backup has the PINs of the cards and their key).
# -Restore: all the data of the mini market replaced with that backup. Before it, a backup of what
# there is now (mm_before_restore_...); the service mm-api is stopped meanwhile; the Forms closed.
# Once before (as SYS, in FREEPDB1): GRANT_BACKUP.sql. And forms_wallet.cmd -DbUser mm -Alias MM_DB
# (PROPOApplication), as for run_api.ps1.
# This file is ASCII on purpose: Windows PowerShell 5 reads a file without BOM as ANSI.
param(
  [string]$Dir = 'C:\mm_backup',
  [string]$CopyTo = '',
  [int]$Keep = 14,
  [string]$At = '23:15',
  [string]$DbHome = 'C:\app\chris\product\26ai\dbhomeFree',
  [string]$Domain = 'C:\Oracle\Middleware\Oracle_Home\user_projects\domains\forms_domain',
  [string]$TnsAdmin = '',
  [string]$Alias = 'MM_DB',
  [string]$Restore = '',
  [switch]$Install,
  [switch]$Uninstall,
  [switch]$Status,
  [switch]$Force
)
$ErrorActionPreference = 'Stop'
$task = 'mm-backup'
$api = 'mm-api'
if (-not $TnsAdmin) { $TnsAdmin = "$Domain\config\fmwconfig" }
$env:TNS_ADMIN = $TnsAdmin
$onWindows = -not ($IsLinux -or $IsMacOS)
function Exe([string]$n) {
  $f = if ($onWindows) { "$n.exe" } else { $n }
  return [IO.Path]::Combine($DbHome, 'bin', $f)
}
$sqlplus = Exe 'sqlplus'
$history = Join-Path $Dir 'backup_history.txt'

function Test-Admin {
  if (-not $onWindows) { return $true }
  $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-Svc([string]$n) {
  if (-not $onWindows) { return $null }
  return Get-Service -Name $n -ErrorAction SilentlyContinue
}

# a script of SQL*Plus through the wallet; its lines back (no password: /@MM_DB)
function Sql([string]$text) {
  $out = ("whenever sqlerror exit failure`nset heading off feedback off pagesize 0 linesize 400 trimout on`n" + $text + "`nexit`n") |
    & $sqlplus -s -L "/@$Alias"
  if ($LASTEXITCODE) { throw ("SQL*Plus /@${Alias}: " + (($out | Where-Object { $_ -match '\S' }) -join ' | ')) }
  return @($out | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
}

# the folder of DATA_PUMP_DIR (where expdp writes, on the side of the database)
function Get-PumpDir {
  $r = @(Sql "select directory_path from all_directories where directory_name = 'DATA_PUMP_DIR';")
  if (-not $r) { throw 'MM may not use DATA_PUMP_DIR: GRANT_BACKUP.sql as SYS first (docs\ODIGIES_VASI.md, the backup)' }
  return $r[0]
}

# the folder of the backups: the administrators and SYSTEM only
function New-BackupDir([string]$d) {
  if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
  if ($onWindows) {
    & icacls $d /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE) { throw "icacls ${d}: the rights of the folder not set" }
  }
}

function Write-History([string]$line) {
  Add-Content -Path $history -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm') + '  ' + $line) -Encoding ASCII
}

# Data Pump: expdp or impdp with a file of parameters (the wallet: userid=/@MM_DB); its log checked
function Pump([string]$tool, [string[]]$params, [string]$log) {
  $par = [IO.Path]::Combine([IO.Path]::GetTempPath(), "mm_$tool.par")
  Set-Content $par -Encoding ASCII -Value (@("userid=/@$Alias") + $params)
  # (Windows PowerShell 5: with Stop, a line of the tool on stderr would end the script)
  $ErrorActionPreference = 'Continue'
  try {
    $out = & (Exe $tool) "parfile=$par" 2>&1 | ForEach-Object { "$_" }
  } finally { Remove-Item $par -Force -ErrorAction SilentlyContinue; $ErrorActionPreference = 'Stop' }
  $ok = ($out -join "`n") -match 'successfully completed|completed with \d+ error'
  if (-not $ok) {
    $out | Select-Object -Last 15 | ForEach-Object { Write-Host "   $_" }
    throw "$tool failed: see $log"
  }
  return ($out -join "`n") -match 'completed with \d+ error'
}

# a backup now: its name (mm_<stamp>.dmp in $Dir)
function Invoke-Backup([string]$prefix = 'mm') {
  New-BackupDir $Dir
  $pump = Get-PumpDir
  $name = $prefix + '_' + (Get-Date -Format 'yyyyMMdd_HHmm')
  Write-Host "== expdp: $name.dmp (the schema of $Alias, consistent as of now)"
  try {
    [void](Pump 'expdp' @('directory=DATA_PUMP_DIR', "dumpfile=$name.dmp", "logfile=$name.log",
      'flashback_time=systimestamp', 'reuse_dumpfiles=yes') (Join-Path $pump "$name.log"))
    # copied, then removed there (if the rights of the folder of the database allow it)
    foreach ($ext in 'dmp', 'log') {
      Copy-Item (Join-Path $pump "$name.$ext") (Join-Path $Dir "$name.$ext") -Force
      Remove-Item (Join-Path $pump "$name.$ext") -Force -ErrorAction SilentlyContinue
    }
  } catch {
    Write-History "FAILED  $name  $($_.Exception.Message)"
    throw
  }
  $file = Join-Path $Dir "$name.dmp"
  $mb = [math]::Round((Get-Item $file).Length / 1MB, 1)
  Write-Host "== $file ($mb MB)"
  $where = ''
  if ($CopyTo) {
    if (Test-Path ([IO.Path]::GetPathRoot($CopyTo))) {
      New-BackupDir $CopyTo
      Copy-Item $file, (Join-Path $Dir "$name.log") $CopyTo -Force
      Remove-Old $CopyTo
      $where = "  + $CopyTo"
      Write-Host "== a copy: $CopyTo"
    } else {
      $where = "  (no copy: $CopyTo not there)"
      Write-Host "== [!] $CopyTo is not there (the disk not plugged in): only $Dir this time"
    }
  }
  Remove-Old $Dir
  Write-History "OK      $name.dmp  $mb MB$where"
  return $file
}

# the newest $Keep backups kept (by count, not by days: a PC off for weeks keeps its last ones)
function Remove-Old([string]$d) {
  Get-ChildItem $d -Filter 'mm_2*.dmp' | Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep |
    ForEach-Object {
      Remove-Item $_.FullName -Force
      Remove-Item ([IO.Path]::ChangeExtension($_.FullName, 'log')) -Force -ErrorAction SilentlyContinue
    }
}

# all the objects of MM dropped (a few passes: views and packages first, then tables, sequences);
# nothing left, or it stops before the import
$dropAll = @'
alter session set ddl_lock_timeout = 60;
declare
  n number;
begin
  for pass in 1 .. 3 loop
    for o in (select object_name, object_type from user_objects
              where object_type in ('PACKAGE', 'PROCEDURE', 'FUNCTION', 'VIEW', 'SYNONYM', 'TYPE', 'TABLE', 'SEQUENCE')
                and object_name not like 'BIN$%' and object_name not like 'ISEQ$$%'
                and not (object_type = 'TABLE' and object_name like 'SYS\_%' escape '\')
              order by case object_type when 'TABLE' then 2 when 'SEQUENCE' then 3 else 1 end) loop
      begin
        execute immediate 'drop ' || o.object_type || ' "' || o.object_name || '"'
          || case o.object_type when 'TABLE' then ' cascade constraints purge' when 'TYPE' then ' force' end;
      exception when others then null;   -- gone already (a table with its sequence), or next pass
      end;
    end loop;
  end loop;
  select count(*) into n from user_objects
  where object_type in ('PACKAGE', 'VIEW', 'TABLE', 'SEQUENCE') and object_name not like 'ISEQ$$%';
  if n > 0 then
    raise_application_error(-20001, n || ' objects of MM still there (a Form open? close the Forms)');
  end if;
end;
/
'@

if ($Status) {
  if ($onWindows) {
    $t = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
    if ($t) {
      $i = $t | Get-ScheduledTaskInfo
      Write-Host ("== the task ${task}: " + $t.State + ', last ' + $i.LastRunTime + ' (result ' + $i.LastTaskResult + '), next ' + $i.NextRunTime)
    } else { Write-Host "== the task $task is not installed (-Install)" }
  }
  if (Test-Path $history) { Write-Host '== the last backups:'; Get-Content $history | Select-Object -Last 7 | ForEach-Object { Write-Host "   $_" } }
  else { Write-Host "== no backup yet in $Dir" }
  exit 0
}

if (-not (Test-Admin)) {
  throw 'as an administrator: right click on PowerShell, "Run as administrator", then this again'
}
if (-not (Test-Path $sqlplus)) { throw "not found: $sqlplus (-DbHome <the folder of the database, e.g. C:\app\<user>\product\26ai\dbhomeFree>)" }

if ($Uninstall) {
  if ($onWindows -and (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue)) {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false
  }
  Write-Host "== the task $task removed (the backups stay in $Dir)"
  exit 0
}

if ($Restore) {
  if (-not (Test-Path $Restore)) { throw "no such file: $Restore" }
  $Restore = (Resolve-Path $Restore).Path
  Write-Host "== ALL the data of the mini market will be replaced with $Restore"
  Write-Host '   (first a backup of what there is now; close the Forms; the service mm-api is stopped meanwhile)'
  if (-not $Force) {
    $yes = Read-Host 'Type RESTORE to go on'
    if ($yes -cne 'RESTORE') { Write-Host '== nothing done'; exit 1 }
  }
  $before = Invoke-Backup 'mm_before_restore'
  $svc = Get-Svc $api
  $wasRunning = $svc -and $svc.Status -eq 'Running'
  if ($wasRunning) { Write-Host "== stop $api"; Stop-Service $api -Force }
  try {
    $pump = Get-PumpDir
    $name = 'mm_restore_' + (Get-Date -Format 'yyyyMMdd_HHmm')
    Copy-Item $Restore (Join-Path $pump "$name.dmp") -Force
    Write-Host '== drop the objects of MM'
    [void](Sql $dropAll)
    Write-Host "== impdp $([IO.Path]::GetFileName($Restore))"
    $warn = Pump 'impdp' @('directory=DATA_PUMP_DIR', "dumpfile=$name.dmp", "logfile=$name.log") (Join-Path $pump "$name.log")
    Remove-Item (Join-Path $pump "$name.dmp") -Force -ErrorAction SilentlyContinue
    $bad = @(Sql "exec dbms_utility.compile_schema(user, false)`nselect count(*) from user_objects where status <> 'VALID';")
    $n = [int]($bad | Select-Object -Last 1)
    Write-History "RESTORE $([IO.Path]::GetFileName($Restore))  (before it: $([IO.Path]::GetFileName($before)))  invalid objects: $n"
    if ($warn) { Write-Host "== [!] impdp: completed with errors, see $pump\$name.log" }
    if ($n) { Write-Host "== [!] $n objects of MM not valid: INSTALL.sql again (the data stays)" }
    Write-Host "== restored from $Restore"
  } finally {
    if ($wasRunning) { Write-Host "== start $api"; Start-Service $api }
  }
  Write-Host "== if something is wrong: -Restore $before (what there was before)"
  exit 0
}

if ($Install) {
  if (-not $onWindows) { throw '-Install: Windows only' }
  [void](Invoke-Backup)
  $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Dir', "`"$Dir`"", '-Keep', $Keep,
         '-DbHome', "`"$DbHome`"", '-TnsAdmin', "`"$TnsAdmin`"", '-Alias', $Alias)
  if ($CopyTo) { $a += @('-CopyTo', "`"$CopyTo`"") }
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ($a -join ' ')
  $when = New-ScheduledTaskTrigger -Daily -At $At
  $who = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
  $how = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -AllowStartIfOnBatteries
  Register-ScheduledTask -TaskName $task -Action $action -Trigger $when -Principal $who -Settings $how `
    -Description "The backup of the database of the mini market (backup.ps1), into $Dir" -Force | Out-Null
  Write-Host "== the task ${task}: every day at $At (and at the next start, if the PC was off then); -Status"
  exit 0
}

[void](Invoke-Backup)
