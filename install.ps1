# BoomHackerWhite one-line installer (Windows PowerShell).
#
#   irm https://raw.githubusercontent.com/TheOwlOps/BoomHackerWhite/main/install.ps1 | iex
#
# Installs uv if missing, installs BoomHackerWhite as an isolated tool
# (commands: bhw, boom-hacker-white, strix), then runs `bhw --doctor`.

$ErrorActionPreference = "Stop"
$Repo = "git+https://github.com/TheOwlOps/BoomHackerWhite@main"

Write-Host "==> BoomHackerWhite installer"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing uv..."
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$HOME\.local\bin;$env:Path"
}

Write-Host "==> Installing BoomHackerWhite (this can take a minute)..."
uv tool install --force "boom-hacker-white @ $Repo"

$env:Path = "$HOME\.local\bin;$env:Path"
if (-not (Get-Command bhw -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'bhw' not on PATH. Add %USERPROFILE%\.local\bin to PATH and re-open PowerShell."
    exit 1
}

Write-Host ""
Write-Host "==> Running preflight checks..."
Write-Host ""
bhw --doctor

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Set your model + key:  `$env:STRIX_LLM='openai/gpt-5.4'; `$env:LLM_API_KEY='sk-...'"
Write-Host "  2. Make sure Docker Desktop is running."
Write-Host "  3. First scan:             bhw -t https://your-app.example"
