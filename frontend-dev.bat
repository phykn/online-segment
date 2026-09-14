@echo off
setlocal

pushd "%~dp0frontend"

if not exist "node_modules" (
  echo Frontend dependencies not found. Run npm install in the frontend folder.
  popd
  exit /b 1
)

call npm run dev
set "frontend_exit_code=%errorlevel%"

popd
exit /b %frontend_exit_code%
