@echo off
cd /d "%~dp0"
set "OAI_RUNTIME=python"
if defined OAI_PYTHON set "OAI_RUNTIME=%OAI_PYTHON%"
"%OAI_RUNTIME%" -c "import sys" >nul 2>&1
if errorlevel 1 goto failed
"%OAI_RUNTIME%" -c "import numpy, SimpleITK, PIL" >nul 2>&1
if errorlevel 1 (
  "%OAI_RUNTIME%" -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
"%OAI_RUNTIME%" app.py
pause
exit /b
:failed
echo Activate a Python environment or set OAI_PYTHON to a Python executable.
pause
