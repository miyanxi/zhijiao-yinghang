@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0智教英航.exe" (
  echo 找不到智教英航.exe，请重新解压完整软件包。
  pause
  exit /b 1
)
start "智教英航" "%~dp0智教英航.exe"
endlocal
