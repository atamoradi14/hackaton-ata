$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& wsl --list --verbose
& docker version
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with Linux engine and WSL integration.' }
$linuxRoot = (& wsl -d Ubuntu-24.04 -- wslpath -a $root.Replace('\','/')).Trim()
& wsl -d Ubuntu-24.04 -- bash "$linuxRoot/scripts/setup-wsl.sh"
if ($LASTEXITCODE -ne 0) { throw 'WSL setup failed.' }
Push-Location $root
try {
if (-not (Get-ChildItem 'C:\Program Files\QGIS*\bin\qgis_process-qgis-ltr.bat' -ErrorAction SilentlyContinue)) {
    & winget install --id OSGeo.QGIS_LTR --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw 'QGIS installer requires attention; administrator consent may be needed.' }
}
if (-not (Test-Path 'C:\Program Files\CloudCompare\CloudCompare.exe')) {
    & winget install --id CloudCompare.CloudCompare --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw 'CloudCompare installer requires attention.' }
}
& npm.cmd exec --yes --package=playwright@1.64.0-alpha-1790635538000 -- playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Playwright browser installation failed.' }
& docker pull ghcr.io/github/github-mcp-server@sha256:ffced0d76e77428532a2ced185516992d77fd146d69eec2f244e6237d1a97796
& docker compose build tools
if ($LASTEXITCODE -ne 0) { throw 'Docker tooling build failed.' }
& wsl -d Ubuntu-24.04 -- bash "$linuxRoot/scripts/setup-optional-wsl.sh"
if ($LASTEXITCODE -ne 0) { throw 'Optional SWMM environment setup failed.' }
} finally { Pop-Location }
& (Join-Path $PSScriptRoot 'validate.ps1')
