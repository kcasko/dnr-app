# DNR App - Playwright Tests

This directory contains end-to-end tests for the DNR App using Playwright.

## Prerequisites

- Python 3.10+
- Virtual environment activated
- Playwright installed with browsers

## Installation

Install test dependencies:

```bash
.venv\Scripts\python.exe -m pip install pytest playwright pytest-playwright
.venv\Scripts\playwright.exe install chromium
```

## Running Tests

### Run all tests

```bash
.venv\Scripts\pytest
```

### Run specific test file

```bash
.venv\Scripts\pytest tests/test_housekeeping_requests.py
```

### Run specific test

```bash
.venv\Scripts\pytest tests/test_housekeeping_requests.py::TestHousekeepingRequests::test_add_housekeeping_request_daily
```

### Run tests in headless mode

```bash
.venv\Scripts\pytest --headed=false
```

### Run tests with specific browser

```bash
.venv\Scripts\pytest --browser chromium
.venv\Scripts\pytest --browser firefox
.venv\Scripts\pytest --browser webkit
```

### Run only fast tests (skip slow tests)

```bash
.venv\Scripts\pytest -m "not slow"
```

### Run with verbose output

```bash
.venv\Scripts\pytest -v
```

### Generate HTML report

```bash
.venv\Scripts\pytest --html=report.html --self-contained-html
```

## Test Structure

- `conftest.py` - Pytest fixtures and configuration
  - `test_db_path` - Creates temporary test database
  - `test_credentials_file` - Creates test credentials
  - `flask_app` - Starts Flask app for testing
  - `browser` - Playwright browser instance
  - `context` - Browser context
  - `page` - Browser page
  - `authenticated_page` - Pre-authenticated page
  - `clean_db` - Cleans database before each test

- `test_housekeeping_requests.py` - Housekeeping request tests
  - Page loading
  - Adding requests with different frequencies
  - Form validation
  - Custom frequency preview
  - Character counter
  - Navigation

## Test Coverage

The test suite covers:

1. **Basic Functionality**
   - Page loads successfully
   - Form submission
   - Navigation links

2. **Frequency Modes**
   - No housekeeping
   - Daily housekeeping
   - Every 3rd day
   - Custom frequency

3. **Form Validation**
   - Required fields
   - Date validation (end date after start date)
   - Custom frequency validation

4. **UI Features**
   - Character counter for notes
   - Frequency mode visual selection
   - Custom frequency input visibility
   - Service date preview

5. **Edge Cases**
   - Guest name optional
   - Multiple requests
   - Empty state message

## Writing New Tests

To add new tests:

1. Create a new test file in the `tests/` directory with the prefix `test_`
2. Import necessary fixtures from `conftest.py`
3. Use the `authenticated_page` fixture for tests requiring login
4. Use the `clean_db` fixture to ensure a clean database state
5. Mark tests with appropriate markers (e.g., `@pytest.mark.e2e`, `@pytest.mark.slow`)

Example:

```python
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.e2e
def test_my_feature(authenticated_page: Page, flask_app, clean_db):
    authenticated_page.goto(f"{flask_app}/my-page")
    expect(authenticated_page).to_have_title("My Page")
```

## Troubleshooting

### Tests fail to start Flask app

- Ensure Flask app runs manually: `.venv\Scripts\python.exe app.py`
- Check that port 5000 is not in use
- Verify test database path is writable

### Browser doesn't launch

- Reinstall browsers: `.venv\Scripts\playwright.exe install chromium`
- Try headless mode: `pytest --headed=false`

### Tests are too slow

- Run in headless mode
- Reduce `slow_mo` parameter in conftest.py
- Skip slow tests: `pytest -m "not slow"`

## CI/CD Integration

For CI/CD pipelines, run tests in headless mode:

```bash
.venv\Scripts\pytest --headed=false --browser chromium
```

Ensure Playwright browsers are installed in your CI environment:

```bash
.venv\Scripts\playwright.exe install --with-deps chromium
```
