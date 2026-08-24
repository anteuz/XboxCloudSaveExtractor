@echo off
setlocal enabledelayedexpansion

echo =====================================================
echo  Building Universal Xbox Cloud Save Extractor
echo =====================================================

REM Locate Visual Studio Dev Prompt
set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat"

if not exist "%VS_DEV_CMD%" (
    set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
)
if not exist "%VS_DEV_CMD%" (
    set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat"
)
if not exist "%VS_DEV_CMD%" (
    set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
)

if not exist "%VS_DEV_CMD%" (
    echo [-] Error: Visual Studio Developer Command Prompt not found.
    echo     Please run this script from a Visual Studio Developer Command Prompt.
    pause
    exit /b 1
)

echo [*] Initializing Visual Studio environment...
call "%VS_DEV_CMD%" -arch=amd64 >nul 2>&1

echo [*] Compiling generic_extractor.cpp with C++/WinRT...
cl /nologo /std:c++20 /EHsc /W4 /O2 generic_extractor.cpp /link windowsapp.lib /out:xbox_save_extractor.exe

if %errorlevel% equ 0 (
    echo.
    echo [*** SUCCESS ***] Built xbox_save_extractor.exe successfully!
    echo.
) else (
    echo.
    echo [-] Compilation failed with error code %errorlevel%.
    echo.
)

