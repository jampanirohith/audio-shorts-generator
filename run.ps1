$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.env')) { Write-Host 'ERROR: .env not found. Copy .env.example to .env and fill in Spotify credentials.'; exit 1 }
python main.py
