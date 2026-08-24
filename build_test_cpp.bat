@echo off
set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat"
if not exist "%VS_DEV_CMD%" set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
if not exist "%VS_DEV_CMD%" set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat"
if not exist "%VS_DEV_CMD%" set "VS_DEV_CMD=C:\Program Files\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"

call "%VS_DEV_CMD%" -arch=amd64 >nul 2>&1
cl /nologo /std:c++20 /EHsc /W4 tests\test_generic_extractor.cpp /link /out:test_cpp.exe
if %errorlevel% equ 0 (
    test_cpp.exe
)

