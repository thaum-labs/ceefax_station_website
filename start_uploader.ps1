# Ceefax Station Uploader - Auto Configuration Script
# This script configures and starts the uploader with production settings
# Run this from the repository root directory

$callsign = "M7TJF"
$grid = "IO81UF"
$server = "https://ceefaxstation.com"
$token = "XjouK8GEhhczBsidV70PbThv3iNlmGBawAAmYx0BsaI"

Write-Host "=== Ceefax Station Uploader ===" -ForegroundColor Cyan
Write-Host "Server: $server" -ForegroundColor Green
Write-Host "Callsign: $callsign" -ForegroundColor Green
Write-Host "Grid: $grid" -ForegroundColor Green
Write-Host ""
Write-Host "Starting uploader (watching for new log files)..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Run the uploader (will watch for new files continuously)
python -m ceefaxstation upload --server $server --token $token --callsign $callsign --grid $grid

