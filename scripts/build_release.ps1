$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$PyInstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
$Dist = Join-Path $Root "dist\DesktopPetWorkshop"
$Release = Join-Path $Root "release"
$Zip = Join-Path $Release "DesktopPetWorkshop-win64.zip"

& $Python (Join-Path $PSScriptRoot "make_icon.py")
& $PyInstaller --noconfirm --clean (Join-Path $Root "desktop_pet.spec")

Copy-Item (Join-Path $Root "PORTABLE-README.txt") $Dist -Force
New-Item -ItemType Directory -Path $Release -Force | Out-Null
if (Test-Path $Zip) {
    Remove-Item $Zip -Force
}
# Windows Defender can transiently lock freshly copied PNGs; bsdtar handles
# that more reliably than Compress-Archive on large sprite collections.
& tar.exe -a -c -f $Zip -C $Dist .

Write-Host "Release ready:"
Write-Host $Dist
Write-Host $Zip
