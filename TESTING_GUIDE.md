# Playwright Testing Guide for DNR App

This guide will help you get started with automated testing using Playwright for the DNR application.

## What is Playwright?

Playwright is a modern end-to-end testing framework that allows you to:
- Test your web application in real browsers (Chromium, Firefox, WebKit)
- Automate user interactions like clicking, typing, and navigation
- Verify UI behavior and content
- Take screenshots and videos of test runs
- Run tests in headed (visible browser) or headless mode

## Setup Complete! ✅

The Playwright testing environment has been set up for your DNR app with:
- ✅ Playwright and pytest installed
- ✅ Chromium browser installed
- ✅ Test directory structure created
- ✅ Configuration files ready
- ✅ Test fixtures for authentication and database
- ✅ Comprehensive housekeeping requests tests
- ✅ Basic verification tests

## Quick Start

### 1. Run the verification tests

To verify everything is working:

```bash
.venv\Scripts\pytest tests/test_playwright_setup.py -v
```

This will run basic tests that verify Playwright can:
- Launch a browser
- Fill out forms
- Click elements

### 2. Run all tests

```bash
.venv\Scripts\pytest
```

Or use the convenient batch script:

```bash
run_tests.bat
```

### 3. Run specific tests

Run only housekeeping request tests:
```bash
.venv\Scripts\pytest tests/test_housekeeping_requests.py -v
```

Run a specific test:
```bash
.venv\Scripts\pytest tests/test_housekeeping_requests.py::TestHousekeepingRequests::test_add_housekeeping_request_daily -v
```

### 4. Watch tests run (headed mode)

See the browser window as tests run:
```bash
.venv\Scripts\pytest --headed -v
```

### 5. Run tests faster (headless mode)

Run without showing the browser:
```bash
.venv\Scripts\pytest --headed=false -v
```

## Test Files Overview

### Created Files

1. **[pytest.ini](pytest.ini)** - Pytest configuration
   - Defines test discovery patterns
   - Sets default options
   - Configures markers for test categories

2. **[tests/conftest.py](tests/conftest.py)** - Test fixtures and setup
   - Database fixtures
   - Authentication helpers
   - Browser/page fixtures
   - Flask app startup

3. **[tests/test_playwright_setup.py](tests/test_playwright_setup.py)** - Basic verification tests
   - Browser launch test
   - Form interaction test
   - Element clicking test

4. **[tests/test_housekeeping_requests.py](tests/test_housekeeping_requests.py)** - Housekeeping feature tests
   - Page loading
   - Adding requests with different frequencies
   - Form validation
   - Custom frequency preview
   - UI interactions

5. **[run_tests.bat](run_tests.bat)** - Convenient test runner script
   - Activates virtual environment
   - Checks dependencies
   - Runs pytest

6. **[tests/README.md](tests/README.md)** - Detailed testing documentation

## What Tests Are Included

### Housekeeping Requests Tests (17 tests)

✅ **Basic Functionality**
- `test_page_loads_successfully` - Verifies page loads with correct title and elements
- `test_print_functionality` - Checks print button exists
- `test_navigation_links` - Tests header navigation

✅ **Frequency Modes**
- `test_add_housekeeping_request_no_service` - No housekeeping option
- `test_add_housekeeping_request_daily` - Daily frequency
- `test_add_housekeeping_request_every_3rd_day` - Every 3rd day frequency
- `test_add_housekeeping_request_custom_frequency` - Custom interval

✅ **Custom Frequency Features**
- `test_custom_frequency_shows_input` - Input field visibility toggle
- `test_custom_frequency_preview` - Date preview functionality
- `test_custom_frequency_validation` - Required field validation

✅ **Form Validation**
- `test_form_validation_missing_fields` - Required field validation
- `test_date_validation` - End date must be after start date
- `test_guest_name_optional` - Guest name is not required

✅ **UI Features**
- `test_character_counter_for_notes` - Notes character counter updates
- `test_frequency_mode_selection_visual_feedback` - Visual selection feedback
- `test_empty_state_message` - Empty state when no requests

✅ **Edge Cases**
- `test_add_multiple_requests` - Adding several requests
- `test_guest_name_optional` - Works without guest name

### Setup Verification Tests (3 tests)

✅ `test_playwright_browser_launches` - Browser launch and navigation
✅ `test_playwright_can_fill_forms` - Form input handling
✅ `test_playwright_can_click_elements` - Element interaction

## Common Commands

### Run tests with different options

```bash
# Verbose output
.venv\Scripts\pytest -v

# Stop on first failure
.venv\Scripts\pytest -x

# Show print statements
.venv\Scripts\pytest -s

# Run only fast tests (skip slow ones)
.venv\Scripts\pytest -m "not slow"

# Run only e2e tests
.venv\Scripts\pytest -m e2e

# Run with specific browser
.venv\Scripts\pytest --browser chromium
.venv\Scripts\pytest --browser firefox
.venv\Scripts\pytest --browser webkit
```

### Debugging

```bash
# Run with browser visible and slow motion
.venv\Scripts\pytest --headed --slowmo 1000

# Run a single test for debugging
.venv\Scripts\pytest tests/test_housekeeping_requests.py::TestHousekeepingRequests::test_add_housekeeping_request_daily -v --headed

# Show full error tracebacks
.venv\Scripts\pytest --tb=long
```

## Next Steps

### 1. Run the tests!

Start by running the verification tests to see Playwright in action:

```bash
.venv\Scripts\pytest tests/test_playwright_setup.py --headed -v
```

Watch as the browser launches, navigates, and interacts with pages automatically!

### 2. Customize for your needs

The housekeeping tests in [tests/test_housekeeping_requests.py](tests/test_housekeeping_requests.py) may need adjustments:
- Update the Flask app startup logic in `conftest.py` if your app has specific requirements
- Modify test data (room numbers, dates) as needed
- Add more test cases for edge cases specific to your workflow

### 3. Add more tests

Use the existing tests as templates to test other features:
- DNR list management
- Maintenance issues
- Room issues
- Log book entries
- Settings

### 4. Integrate with CI/CD

For automated testing in CI/CD pipelines:

```bash
# Install with dependencies for CI
.venv\Scripts\playwright.exe install --with-deps chromium

# Run in headless mode for CI
.venv\Scripts\pytest --headed=false --browser chromium
```

## Tips for Writing Tests

1. **Use meaningful test names** - Name tests clearly: `test_user_can_add_daily_housekeeping_request`

2. **Keep tests independent** - Each test should work on its own without depending on others

3. **Use fixtures** - Leverage the `clean_db` and `authenticated_page` fixtures for consistent test state

4. **Wait for elements** - Playwright auto-waits, but you can use `page.wait_for_selector()` for dynamic content

5. **Use locators wisely** - Prefer `data-testid`, IDs, or semantic selectors over CSS classes

6. **Test user workflows** - Test complete user journeys, not just individual clicks

## Troubleshooting

### Tests fail to find elements

- Check that element selectors match your HTML
- Use `--headed` mode to see what's happening
- Add `page.pause()` in your test to debug interactively

### Flask app doesn't start

- Verify your app runs manually: `.venv\Scripts\python.exe app.py`
- Check the port 5000 is not in use
- Review environment variables in `conftest.py`

### Browser doesn't launch

- Reinstall browsers: `.venv\Scripts\playwright.exe install chromium`
- Try headless mode: `pytest --headed=false`
- Check your system supports the browser

### Tests are too slow

- Run in headless mode (faster)
- Remove the `slow_mo` parameter from browser launch
- Use `pytest -n auto` with pytest-xdist for parallel execution

## Learning Resources

- [Playwright Python Documentation](https://playwright.dev/python/docs/intro)
- [Pytest Documentation](https://docs.pytest.org/)
- [Playwright Best Practices](https://playwright.dev/python/docs/best-practices)

## Need Help?

- Check [tests/README.md](tests/README.md) for detailed documentation
- Review example tests in `test_playwright_setup.py` and `test_housekeeping_requests.py`
- Playwright's documentation is excellent: https://playwright.dev/python/

---

Happy Testing! 🎭🧪
