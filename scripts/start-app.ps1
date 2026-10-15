$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    function Get-AucklandFlowLabState {
        $taskReply = & curl.exe --noproxy '*' --max-time 2 --silent 'http://127.0.0.1:8765/api/bootstrap'
        if ($LASTEXITCODE -eq 0) {
            try { return ($taskReply | ConvertFrom-Json) } catch { return $null }
        }
        return $null
    }
    if (-not (Test-Path 'web/node_modules/leaflet/dist/leaflet.js')) {
        & npm.cmd --prefix web ci --ignore-scripts --no-fund --no-audit
        if ($LASTEXITCODE -ne 0) { throw 'Leaflet installation failed.' }
    }
    $ready = Get-AucklandFlowLabState
    if ($ready -and $ready.name -eq 'Auckland FlowLab') {
        Write-Output 'Auckland FlowLab is already running: http://localhost:8765'
        return
    }
    New-Item reports -ItemType Directory -Force | Out-Null
    $linuxRoot = (& wsl -d Ubuntu-24.04 -- wslpath -a $root.Replace('\','/')).Trim()
    $taskProcess = Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu-24.04','--','bash',"`"$linuxRoot/scripts/serve-wsl.sh`"") -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'reports/app-stdout.log') -RedirectStandardError (Join-Path $root 'reports/app-stderr.log')
    @{launcher_pid=$taskProcess.Id;url='http://localhost:8765'} | ConvertTo-Json | Set-Content reports/app-process.json
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 300
        $ready = Get-AucklandFlowLabState
    } until (($ready -and $ready.name -eq 'Auckland FlowLab') -or (Get-Date) -gt $deadline)
    if (-not $ready) { throw 'App did not become ready. Inspect reports/app-stderr.log.' }
    Write-Output 'Auckland FlowLab is running: http://localhost:8765'
} finally { Pop-Location }
