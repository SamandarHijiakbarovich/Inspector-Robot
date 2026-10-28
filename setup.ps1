<#
.SYNOPSIS
  Inspektor robot uchun kerakli kutubxonalarni o'rnatadi.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\setup.ps1
  powershell -ExecutionPolicy Bypass -File .\setup.ps1 -PythonVersion 3.13
  powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Chromium -Recreate
#>
param(
    # Masalan "3.13". Bo'sh bo'lsa - standart Python ishlatiladi.
    [string]$PythonVersion = "",
    # Playwright'ning o'z Chromium brauzerini ham yuklab olish (Edge o'rniga).
    [switch]$Chromium,
    # .venv ni o'chirib, qaytadan yaratish.
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    $text" -ForegroundColor Green }
function Warn($text) { Write-Host "    $text" -ForegroundColor Yellow }
function Fail($text) { Write-Host ""; Write-Host "XATO: $text" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 1. Python
Step "Python topilmoqda"
$pyCmd = @()
if ($PythonVersion) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        Fail "'py' buyrug'i topilmadi. Python'ni python.org dan o'rnating."
    }
    $pyCmd = @("py", "-V:$PythonVersion")
    & py "-V:$PythonVersion" --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "Python $PythonVersion o'rnatilmagan. O'rnatish: py install $PythonVersion   (yoki python.org dan)"
    }
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pyCmd = @("py")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyCmd = @("python")
} else {
    Fail "Python topilmadi. https://www.python.org/downloads/ dan o'rnating."
}

$pyExe  = $pyCmd[0]
$pyArgs = @($pyCmd | Select-Object -Skip 1)
$version = (& $pyExe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
Ok "Python $version"
if ([version]$version -lt [version]"3.10") {
    Fail "Python 3.10 yoki undan yangi kerak (hozir $version)."
}

# ---------------------------------------------------------------- 2. Virtual muhit
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if ($Recreate -and (Test-Path ".venv")) {
    Step ".venv o'chirilmoqda"
    Remove-Item -Recurse -Force ".venv" -Confirm:$false
}
if (-not (Test-Path $venvPython)) {
    Step "Virtual muhit (.venv) yaratilmoqda"
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "venv yaratib bo'lmadi." }
    Ok ".venv yaratildi"
} else {
    $venvVersion = (& $venvPython -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
    Ok ".venv mavjud (Python $venvVersion). Qayta yaratish uchun: -Recreate"
}

# ---------------------------------------------------------------- 3. Kutubxonalar
Step "pip yangilanmoqda"
& $venvPython -m pip install --upgrade pip --disable-pip-version-check -q
if ($LASTEXITCODE -ne 0) { Fail "pip yangilanmadi. Internet ulanishini tekshiring." }

Step "Kutubxonalar o'rnatilmoqda (playwright, fastapi, uvicorn, jinja2)"
& $venvPython -m pip install -r requirements.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Warn "O'rnatishda xato. Ko'pincha sabab: Python $version juda yangi va 'greenlet' (Playwright"
    Warn "ishlatadi) uchun tayyor paket hali chiqmagan, kompilyatsiya uchun esa C++ kompilyator yo'q."
    Warn "Yechim - barqaror Python versiyasi bilan qayta urinish:"
    Warn "    py install 3.13"
    Warn "    powershell -ExecutionPolicy Bypass -File .\setup.ps1 -PythonVersion 3.13 -Recreate"
    Fail "pip install muvaffaqiyatsiz tugadi."
}
Ok "Kutubxonalar o'rnatildi"

# ---------------------------------------------------------------- 4. Brauzer
Step "Brauzer tekshirilmoqda"
$edgePaths = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$edgeFound = $edgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($Chromium -or -not $edgeFound) {
    if (-not $edgeFound) { Warn "Microsoft Edge topilmadi - Playwright Chromium yuklab olinadi." }
    & $venvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { Fail "Chromium yuklab olinmadi." }
    Ok "Chromium o'rnatildi. .env faylida BROWSER_CHANNEL=chromium qiling."
} else {
    Ok "Microsoft Edge topildi: $edgeFound (BROWSER_CHANNEL=msedge)"
}

# ---------------------------------------------------------------- 5. .env
Step ".env sozlamalar fayli"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Ok ".env yaratildi (.env.example nusxasi). ORG_INN va INSPECTOR_ID ni tekshiring."
} else {
    Ok ".env allaqachon mavjud - o'zgartirilmadi"
}
if ($Chromium -or -not $edgeFound) {
    $envText = Get-Content ".env" -Raw -Encoding UTF8
    if ($envText -match "(?m)^BROWSER_CHANNEL=msedge") {
        $envText = $envText -replace "(?m)^BROWSER_CHANNEL=msedge", "BROWSER_CHANNEL=chromium"
        [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot ".env"), $envText, (New-Object System.Text.UTF8Encoding $false))
        Ok ".env: BROWSER_CHANNEL=chromium qilib qo'yildi"
    }
}

# ---------------------------------------------------------------- 6. Tekshiruv
Step "O'rnatish tekshirilmoqda"
& $venvPython -c "import playwright, fastapi, uvicorn, jinja2; print('    importlar OK')"
if ($LASTEXITCODE -ne 0) { Fail "Kutubxonalar import qilinmadi." }

$env:PYTHONIOENCODING = "utf-8"
& $venvPython -m unittest discover -s tests -t . -q
if ($LASTEXITCODE -ne 0) { Fail "Testlar o'tmadi." }
Ok "Testlar o'tdi"

# ---------------------------------------------------------------- Tayyor
Write-Host ""
Write-Host "TAYYOR. Keyingi qadamlar:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1          # muhitni yoqish"
Write-Host "  python main.py login                  # 1. tizimga bir marta qo'lda kirish"
Write-Host "  python main.py dump --form 685        # 2. sahifani faylga saqlash (hech narsa bosilmaydi)"
Write-Host "  python main.py run                    # 3. dry_run rejimida sinov"
Write-Host "  python main.py dashboard              # 4. http://127.0.0.1:8000"
