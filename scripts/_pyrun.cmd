@echo off
REM Cross-platform Python launcher for AI log hooks (Windows cmd.exe).
REM Uses the project venv first, then tries py -3 -> python -> python3.
REM Exits 0 silently if no Python is found - hooks must never block the AI tool.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" %*
  exit /b %ERRORLEVEL%
)

if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" %*
  exit /b %ERRORLEVEL%
)

py -3 -c "import sys" >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 %*
  exit /b %ERRORLEVEL%
)

python -c "import sys" >nul 2>nul
if %ERRORLEVEL%==0 (
  python %*
  exit /b %ERRORLEVEL%
)

python3 -c "import sys" >nul 2>nul
if %ERRORLEVEL%==0 (
  python3 %*
  exit /b %ERRORLEVEL%
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
  if exist "%%D\python.exe" (
    "%%D\python.exe" %*
    exit /b %ERRORLEVEL%
  )
)

for /d %%D in ("%ProgramFiles%\Python*") do (
  if exist "%%D\python.exe" (
    "%%D\python.exe" %*
    exit /b %ERRORLEVEL%
  )
)

exit /b 0
