$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$linuxRoot = (& wsl -d Ubuntu-24.04 -- wslpath -a $root.Replace('\','/')).Trim()
& wsl -d Ubuntu-24.04 -- bash "$linuxRoot/scripts/floodtwin.sh" @args
exit $LASTEXITCODE
