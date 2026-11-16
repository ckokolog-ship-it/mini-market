# build_apk.ps1 -- the APK of the mini market on Windows, with Docker Desktop only (no Android Studio):
#
#   cd C:\Users\chris\eclipse-workspace\mini-market\mobile
#   powershell -ExecutionPolicy Bypass -File build_apk.ps1
#
# The APK: mobile\apk\MiniMarket-1.0.<yymmddhh>.apk. The first time: the builder (about 1.5 GB, 10-20
# minutes) and the key of the APKs (mobile\keystore: keep it and back it up; a new APK installs over the
# old app only with the same key). -Rebuild: the builder made again (a new SDK).
param([switch]$Rebuild)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'docker not found: install Docker Desktop and start it'
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker is not running: open Docker Desktop, wait for "Engine running", then this again'
}
$have = docker images -q mm-apk-builder
if ($Rebuild -or -not $have) {
    Write-Host '== the builder of the APK (the first time: 10-20 minutes)'
    docker build -t mm-apk-builder -f (Join-Path $PSScriptRoot 'apk.Dockerfile') $PSScriptRoot
    if ($LASTEXITCODE -ne 0) { throw 'docker build failed' }
}
Write-Host '== the APK'
# the caches of gradle and npm in volumes of their own: the next builds are quicker
docker run --rm -v "${repo}:/src" -v mm-apk-gradle:/root/.gradle -v mm-apk-npm:/root/.npm mm-apk-builder
if ($LASTEXITCODE -ne 0) { throw 'the build of the APK failed' }
Get-ChildItem (Join-Path $PSScriptRoot 'apk') -Filter *.apk | Sort-Object LastWriteTime | Select-Object -Last 1 |
    ForEach-Object { Write-Host ('== ' + $_.FullName) }
