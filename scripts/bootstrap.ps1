$ErrorActionPreference = "Stop"

if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
  throw "pnpm 11 or newer is required."
}

pnpm install --frozen-lockfile
Write-Host "Frontend dependencies installed."
Write-Host "For the full stack: docker compose up --build"
Write-Host "Open http://localhost:8080/en/command/dashboard"
