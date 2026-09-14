@echo off
setlocal

pushd "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo Backend virtual environment not found: backend\.venv
  popd
  exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn src.main:app --reload --reload-include "*.yaml" --host 127.0.0.1 --port 8000
set "backend_exit_code=%errorlevel%"

popd
exit /b %backend_exit_code%
