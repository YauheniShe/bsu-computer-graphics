@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if exist ".venv\Scripts\python.exe" goto dependencies

py -3 -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto create_py
python -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto create_python
echo Python 3.10+ with Tcl/Tk is required.
goto failed

:create_py
py -3 -m venv .venv
if errorlevel 1 goto failed
goto dependencies

:create_python
python -m venv .venv
if errorlevel 1 goto failed

:dependencies
".venv\Scripts\python.exe" -c "import numpy, PIL, tkinter" >nul 2>&1
if not errorlevel 1 goto run
echo Installing NumPy and Pillow...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

:run
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
exit /b 0

:failed
pause
exit /b 1
