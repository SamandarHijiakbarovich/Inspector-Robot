<#
.SYNOPSIS
  Boshqa inspektorlarga berish uchun ZIP arxiv yasaydi.
  Maxfiy narsalarni (sessiya, parollar, hisobot namunalari, baza) QO'SHMAYDI.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\Tarqatish-arxivi-yasash.ps1
#>
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$stamp = Get-Date -Format "yyyyMMdd"
$zip = Join-Path $PSScriptRoot "inspektor-robot-$stamp.zip"
$staging = Join-Path $env:TEMP ("inspektor-robot-" + [guid]::NewGuid().ToString("N"))

# Arxivga KIRADIGAN narsalar (ichki ma'lumot va sessiya YO'Q)
$include = @(
    "inspektor_bot", "main.py", "requirements.txt", "setup.ps1",
    "Robot.bat", "Ornatish.bat", "Yorliq-yaratish.bat",
    ".env.example", "README.md", "YORIQNOMA.md"
)
# Arxivga HECH QACHON kirmaydigan narsalar (maxfiy / kerakmas)
$excludeDirs = @("__pycache__", ".git", ".venv", "data", "tests")

New-Item -ItemType Directory -Path $staging -Force | Out-Null
foreach ($item in $include) {
    if (-not (Test-Path $item)) { continue }
    if (Test-Path $item -PathType Container) {
        Copy-Item $item -Destination $staging -Recurse
    } else {
        Copy-Item $item -Destination $staging
    }
}
# __pycache__ va boshqa keraksiz papkalarni tozalash
foreach ($d in $excludeDirs) {
    Get-ChildItem -Path $staging -Recurse -Directory -Filter $d -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# Xavfsizlik tekshiruvi: maxfiy fayllar tasodifan kirib qolmaganini aniqlash
$leaks = Get-ChildItem -Path $staging -Recurse -File |
    Where-Object { $_.Name -eq ".env" -or $_.Name -eq "robot.db" -or $_.Extension -eq ".txt" -and $_.Directory.Name -eq "fixtures" }
if ($leaks) {
    Write-Host "XATO: arxivga maxfiy fayllar kirib qolgan:" -ForegroundColor Red
    $leaks | ForEach-Object { Write-Host "  $($_.FullName)" }
    Remove-Item $staging -Recurse -Force
    exit 1
}

if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zip -Force
Remove-Item $staging -Recurse -Force

$size = [math]::Round((Get-Item $zip).Length / 1MB, 2)
Write-Host "Arxiv tayyor: $zip ($size MB)" -ForegroundColor Green
Write-Host "Ichida .env, data va hisobot namunalari YO'Q - xavfsiz tarqatsa bo'ladi."
