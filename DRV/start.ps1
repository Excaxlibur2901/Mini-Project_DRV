#!/usr/bin/env pwsh
<#
.SYNOPSIS
  One-command startup for Decentralized Record Verifier (DRV).

.DESCRIPTION
  Starts Hardhat local EVM, deploys the contract, seeds real certificate hashes,
  generates sample PDFs if missing, and launches the FastAPI backend.

.EXAMPLE
  cd DRV
  .\start.ps1
#>

param(
    [string]$PythonExe = "C:\Python314\python.exe",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RootDir = $PSScriptRoot

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Decentralized Record Verifier — DRV    " -ForegroundColor Cyan
Write-Host "  B.Tech Mini Project | RCPCE Shirpur    " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Kill any stale Hardhat / uvicorn processes ──────────────────────────
Write-Host "[1/5] Cleaning up stale processes..." -ForegroundColor Yellow
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -eq "" -or $_.CommandLine -match "hardhat"
} | Stop-Process -Force -ErrorAction SilentlyContinue

# ── 2. Start Hardhat node in background ───────────────────────────────────
Write-Host "[2/5] Starting Hardhat local EVM node..." -ForegroundColor Yellow
$hardhatJob = Start-Process -FilePath "npx" `
    -ArgumentList "hardhat", "node" `
    -WorkingDirectory $RootDir `
    -NoNewWindow -PassThru
Start-Sleep -Seconds 4

if ($hardhatJob.HasExited) {
    Write-Host "  [ERROR] Hardhat node failed to start." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Hardhat node running at http://127.0.0.1:8545" -ForegroundColor Green

# ── 3. Deploy contract ─────────────────────────────────────────────────────
Write-Host "[3/5] Deploying RecordRegistry contract..." -ForegroundColor Yellow
npx hardhat run scripts/deploy.js --network localhost
if ($LASTEXITCODE -ne 0) { Write-Host "  [ERROR] Deploy failed." -ForegroundColor Red; exit 1 }
Write-Host "  [OK] Contract deployed to 0x5FbDB2315678afecb367f032d93F642f64180aa3" -ForegroundColor Green

# ── 4. Generate sample PDFs if missing ────────────────────────────────────
$certDir = Join-Path $RootDir "data\sample_certs"
if (-not (Test-Path (Join-Path $certDir "sample_cert_101.pdf"))) {
    Write-Host "[4/5] Generating sample certificate PDFs..." -ForegroundColor Yellow
    & $PythonExe scripts/generate_sample_certs.py
    if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] PDF generation failed — continuing." -ForegroundColor DarkYellow }
    else { Write-Host "  [OK] Sample PDFs created in data/sample_certs/" -ForegroundColor Green }
} else {
    Write-Host "[4/5] Sample PDFs already exist — skipping generation." -ForegroundColor Green
}

# Seed real hashes on-chain
Write-Host "       Seeding real certificate hashes..." -ForegroundColor Yellow
npx hardhat run scripts/seed_real.js --network localhost
if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] Seeding failed — chain may already be seeded." -ForegroundColor DarkYellow }
else { Write-Host "  [OK] CERT-101/102/103(revoked)/104 registered on-chain" -ForegroundColor Green }

# ── 5. Start FastAPI backend ───────────────────────────────────────────────
Write-Host "[5/5] Starting FastAPI backend on http://127.0.0.1:$Port ..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Verifier UI  : http://127.0.0.1:$Port/" -ForegroundColor Cyan
Write-Host "  Admin portal : http://127.0.0.1:$Port/admin.html" -ForegroundColor Cyan
Write-Host "  API docs     : http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
Write-Host "  API health   : http://127.0.0.1:$Port/api/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

& $PythonExe -m uvicorn app.main:app `
    --host 127.0.0.1 `
    --port $Port `
    --app-dir backend `
    --reload

