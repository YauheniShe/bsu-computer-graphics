@echo off
setlocal
cd /d "%~dp0labs\lab01" || exit /b 1

py -3 -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto run_py
python -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto run_python

echo Python 3.10+ with Tcl/Tk is required.
pause
exit /b 1

:run_py
py -3 app.py
if errorlevel 1 goto failed
exit /b 0

:run_python
python app.py
if errorlevel 1 goto failed
exit /b 0

:failed
pause
exit /b 1
