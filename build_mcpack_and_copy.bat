@echo off
chcp 65001 >nul
setlocal

:: Пути
set "BASE=%~dp0"
set "SOURCE=%BASE%FallingDirt"
set "DEST=D:\Works\Minecraft\PocketMine-MP-5.44.3\resource_packs"

set "ZIP=%BASE%FallingDirt.zip"
set "MCPACK=%BASE%FallingDirt.mcpack"
set "MANIFEST=%SOURCE%\manifest.json"

echo ========================================
echo       FallingDirt Resource Pack
echo ========================================

:: Проверка папок и файла
if not exist "%SOURCE%\" (
    echo [ERROR] FallingDirt folder not found!
    pause
    exit /b 1
)

if not exist "%MANIFEST%" (
    echo [ERROR] manifest.json not found!
    pause
    exit /b 1
)

if not exist "%DEST%\" (
    echo [ERROR] resource_packs folder not found!
    pause
    exit /b 1
)

:: Увеличение версии в manifest.json
echo [1/6] Updating manifest version...

powershell -NoProfile -Command ^
    "$path = '%MANIFEST%';" ^
    "$utf8 = New-Object System.Text.UTF8Encoding($false);" ^
    "$json = [System.IO.File]::ReadAllText($path, $utf8);" ^
    "$data = $json | ConvertFrom-Json;" ^
    "$data.header.version[2] = [int]$data.header.version[2] + 1;" ^
    "$data.modules[0].version[2] = [int]$data.modules[0].version[2] + 1;" ^
    "$output = $data | ConvertTo-Json -Depth 20;" ^
    "[System.IO.File]::WriteAllText($path, $output, $utf8)"

if errorlevel 1 (
    echo [ERROR] Version update failed!
    pause
    exit /b 1
)

:: Удаление старых архивов рядом с BAT
echo [2/6] Removing old archives...

del /q "%ZIP%" 2>nul
del /q "%MCPACK%" 2>nul

:: Удаление старых архивов из resource_packs
echo [3/6] Cleaning resource_packs...

del /q "%DEST%\FallingDirt.zip" 2>nul
del /q "%DEST%\FallingDirt.mcpack" 2>nul

:: Создание ZIP без сжатия
echo [4/6] Creating ZIP archive...

powershell -NoProfile -Command ^
    "Compress-Archive -Path '%SOURCE%\*' -DestinationPath '%ZIP%' -CompressionLevel NoCompression"

if errorlevel 1 (
    echo [ERROR] ZIP creation failed!
    pause
    exit /b 1
)

:: Переименование ZIP в MCPACK
echo [5/6] Renaming ZIP to MCPACK...

ren "%ZIP%" "FallingDirt.mcpack"

if errorlevel 1 (
    echo [ERROR] Rename failed!
    pause
    exit /b 1
)

:: Копирование
echo [6/6] Installing resource pack...

copy /y "%MCPACK%" "%DEST%\FallingDirt.mcpack" >nul

if errorlevel 1 (
    echo [ERROR] Copy failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo       BUILD SUCCESSFUL!
echo ========================================
echo.
echo Installed: %DEST%\FallingDirt.mcpack
echo.

pause