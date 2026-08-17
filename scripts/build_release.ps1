$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
$Dist = Join-Path $Root "dist\DesktopPetWorkshop"
$Release = Join-Path $Root "release"
$Zip = Join-Path $Release "DesktopPetWorkshop-v1.0.3-win64.zip"
$TempZip = Join-Path $Release "DesktopPetWorkshop-v1.0.3-win64.new.zip"

& $Python (Join-Path $PSScriptRoot "make_icon.py")
& $PyInstaller --noconfirm --clean (Join-Path $Root "desktop_pet.spec")

Copy-Item (Join-Path $Root "PORTABLE-README.txt") $Dist -Force
New-Item -ItemType Directory -Path $Release -Force | Out-Null
if (Test-Path $TempZip) {
    Remove-Item $TempZip -Force
}
# Windows Defender can transiently lock freshly copied PNGs; bsdtar handles
# that more reliably than Compress-Archive on large sprite collections.
& tar.exe -a -c -f $TempZip -C $Dist .

$Replaced = $false
for ($Attempt = 1; $Attempt -le 10; $Attempt++) {
    try {
        if (Test-Path $Zip) {
            Remove-Item $Zip -Force
        }
        Move-Item $TempZip $Zip -Force
        $Replaced = $true
        break
    }
    catch {
        if ($Attempt -eq 10) {
            throw "Cannot replace $Zip because another process keeps it open. Close Explorer preview/compression tools and run the build again."
        }
        Start-Sleep -Seconds 1
    }
}

if (-not $Replaced) {
    throw "Release archive was not replaced."
}

Write-Host "Release ready:"
Write-Host $Dist
Write-Host $Zip
