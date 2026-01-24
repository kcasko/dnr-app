@echo off
REM DNR App - Test Runner Script
REM This script runs Playwright tests for the DNR application

echo ===================================
echo DNR App - Playwright Test Runner
echo ===================================
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check if pytest is installed
python -c "import pytest" 2>NUL
if errorlevel 1 (
    echo ERROR: pytest is not installed
    echo Installing test dependencies...
    python -m pip install -r requirements.txt
)

REM Check if playwright is installed
python -c "import playwright" 2>NUL
if errorlevel 1 (
    echo ERROR: playwright is not installed
    echo Installing playwright...
    python -m pip install playwright pytest-playwright
    playwright install chromium
)

echo.
echo Running tests...
echo.

REM Run pytest with arguments passed to this script
pytest %*

echo.
echo ===================================
echo Tests completed
echo ===================================
