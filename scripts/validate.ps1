$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
& docker version --format '{{.Server.Version}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker Linux engine unavailable.' }
$linuxRoot = (& wsl -d Ubuntu-24.04 -- wslpath -a $root.Replace('\','/')).Trim()
& wsl -d Ubuntu-24.04 -- bash "$linuxRoot/scripts/validate-wsl.sh"
if ($LASTEXITCODE -ne 0) { throw 'Environment/numerical validation failed. Inspect reports and solver.log.' }
$qgis = Get-ChildItem 'C:\Program Files\QGIS*\bin\qgis_process-qgis-ltr.bat' -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $qgis) { throw 'QGIS LTR processing executable missing.' }
& $qgis.FullName --version | Out-File reports/qgis-version.txt -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw 'QGIS startup failed.' }
if (Test-Path 'data/processed/site/pointcloud_crop.laz') {
    $crop = (Resolve-Path 'data/processed/site/pointcloud_crop.laz').Path
    & 'C:\Program Files\CloudCompare\CloudCompare.exe' -SILENT -AUTO_SAVE OFF -O -GLOBAL_SHIFT AUTO $crop
} else {
    & 'C:\Program Files\CloudCompare\CloudCompare.exe' -SILENT -AUTO_SAVE OFF -NO_TIMESTAMP
}
if ($LASTEXITCODE -ne 0) { throw 'CloudCompare startup failed.' }
& python scripts/validate-mcp.py
if ($LASTEXITCODE -ne 0) { throw 'Playwright MCP/browser validation failed.' }
& python scripts/validate-github-mcp.py
if ($LASTEXITCODE -ne 0) { throw 'GitHub MCP authentication/validation failed.' }
& docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose configuration invalid.' }
& docker compose run --rm tools
if ($LASTEXITCODE -ne 0) { throw 'Docker geospatial tooling validation failed.' }
& wsl -d Ubuntu-24.04 -- bash "$linuxRoot/scripts/validate-swmm.sh"
if ($LASTEXITCODE -ne 0) { throw 'Optional SWMM installation check failed.' }
Write-Output 'PASS: WSL, geospatial stack, real SFINCS numerics, native tools, MCP and Docker tooling.'
} finally { Pop-Location }
