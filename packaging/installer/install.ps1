$ErrorActionPreference = "Stop"

$packageName = "AIQuantPlatform-v1.0.0-windows.zip"
$zipPath = Join-Path $PSScriptRoot $packageName
$installRoot = Join-Path $env:LOCALAPPDATA "AIQuantPlatform"
$installDir = Join-Path $installRoot "AIQuantPlatform"
$exePath = Join-Path $installDir "AIQuantPlatform.exe"

if (-not (Test-Path $zipPath)) {
    throw "Package not found: $zipPath"
}

Write-Host "Installing AI Quant Platform..."
Write-Host "Target: $installDir"

Get-Process -Name "AIQuantPlatform" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
if (Test-Path $installDir) {
    Remove-Item -LiteralPath $installDir -Recurse -Force
}

Expand-Archive -LiteralPath $zipPath -DestinationPath $installRoot -Force

if (-not (Test-Path $exePath)) {
    throw "Installed executable not found: $exePath"
}

$shell = New-Object -ComObject WScript.Shell

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "AI Quant Platform.lnk"
$desktopLink = $shell.CreateShortcut($desktopShortcut)
$desktopLink.TargetPath = $exePath
$desktopLink.WorkingDirectory = $installDir
$desktopLink.Description = "AI Quant Platform"
$desktopLink.Save()

$programsDir = [Environment]::GetFolderPath("Programs")
$startMenuDir = Join-Path $programsDir "AI Quant Platform"
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null

$startShortcut = Join-Path $startMenuDir "AI Quant Platform.lnk"
$startLink = $shell.CreateShortcut($startShortcut)
$startLink.TargetPath = $exePath
$startLink.WorkingDirectory = $installDir
$startLink.Description = "AI Quant Platform"
$startLink.Save()

$uninstallPath = Join-Path $installRoot "Uninstall AI Quant Platform.cmd"
$uninstallContent = @"
@echo off
taskkill /IM AIQuantPlatform.exe /F >nul 2>nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -LiteralPath '$installDir' -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '$desktopShortcut' -Force -ErrorAction SilentlyContinue; Remove-Item -LiteralPath '$startMenuDir' -Recurse -Force -ErrorAction SilentlyContinue"
echo AI Quant Platform has been removed.
pause
"@
Set-Content -LiteralPath $uninstallPath -Value $uninstallContent -Encoding ASCII

Write-Host "Installation complete."
Write-Host "Launching AI Quant Platform..."
Start-Process -FilePath $exePath -WorkingDirectory $installDir
