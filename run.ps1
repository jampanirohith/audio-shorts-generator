$ErrorActionPreference = 'Stop'
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'FFmpeg is not on PATH.' }
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { throw 'FFprobe is not on PATH.' }
if (-not $env:SPOTIPY_CLIENT_ID -or -not $env:SPOTIPY_CLIENT_SECRET) {
  Write-Host 'Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET first.'
  exit 1
}
python main.py
