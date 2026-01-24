# Playwright Testing - Quick Reference

## Running Tests

| Command | Description |
|---------|-------------|
| `run_tests.bat` | Run all tests with the batch script |
| `.venv\Scripts\pytest` | Run all tests |
| `.venv\Scripts\pytest -v` | Run tests with verbose output |
| `.venv\Scripts\pytest tests/test_playwright_setup.py` | Run specific test file |
| `.venv\Scripts\pytest tests/test_housekeeping_requests.py::TestHousekeepingRequests::test_add_housekeeping_request_daily` | Run specific test |
| `.venv\Scripts\pytest --headed` | Run with visible browser |
| `.venv\Scripts\pytest --headed=false` | Run in headless mode |
| `.venv\Scripts\pytest -x` | Stop on first failure |
| `.venv\Scripts\pytest -k "daily"` | Run tests matching "daily" |
| `.venv\Scripts\pytest -m "not slow"` | Skip slow tests |
| `.venv\Scripts\pytest --lf` | Run last failed tests |

## Playwright Locators

```python
# By ID
page.locator("#room-number")

# By CSS class
page.locator(".btn-primary")

# By text content
page.locator('button:has-text("Submit")')

# By attribute
page.locator('[name="frequency"]')

# By data attribute
page.locator('[data-frequency="daily"]')

# Nth element
page.locator(".item").nth(0)

# First/Last
page.locator(".item").first
page.locator(".item").last
```

## Common Actions

```python
# Navigate
page.goto("http://localhost:5000/housekeeping-requests")

# Fill input
page.fill("#room-number", "214")

# Click
page.click('button[type="submit"]')

# Select dropdown
page.select_option("#dropdown", "value")

# Check checkbox
page.check("#checkbox")

# Upload file
page.set_input_files("#file-input", "path/to/file.txt")

# Wait for element
page.wait_for_selector("#result")

# Wait for navigation
page.wait_for_load_state("networkidle")

# Wait for URL
page.wait_for_url("http://localhost:5000/overview")
```

## Assertions

```python
from playwright.sync_api import expect

# Text content
expect(page.locator("h1")).to_contain_text("Housekeeping")

# Visibility
expect(page.locator(".error")).to_be_visible()
expect(page.locator(".loading")).not_to_be_visible()

# Value
expect(page.locator("#name")).to_have_value("Test User")

# Title
expect(page).to_have_title("Housekeeping Requests - DNR App")

# URL
expect(page).to_have_url("http://localhost:5000/overview")

# Count
expect(page.locator(".item")).to_have_count(5)

# Class
expect(page.locator(".mode")).to_have_class(/selected/)

# Enabled/Disabled
expect(page.locator("button")).to_be_enabled()
expect(page.locator("button")).to_be_disabled()

# Checked
expect(page.locator("#radio")).to_be_checked()
```

## Debugging

```python
# Pause execution (interactive debugger)
page.pause()

# Take screenshot
page.screenshot(path="screenshot.png")

# Print HTML
print(page.content())

# Get element text
print(page.locator("h1").text_content())

# Check if element exists
if page.locator(".error").count() > 0:
    print("Error found!")
```

## Fixtures (from conftest.py)

```python
def test_example(page):
    """Basic page fixture - browser page instance"""
    pass

def test_with_auth(authenticated_page, flask_app):
    """Pre-authenticated page with Flask app running"""
    pass

def test_with_clean_db(clean_db):
    """Clean database before test"""
    pass
```

## Markers

```python
@pytest.mark.e2e
def test_end_to_end():
    """Mark as end-to-end test"""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Mark as slow test"""
    pass

@pytest.mark.integration
def test_integration():
    """Mark as integration test"""
    pass
```

## Common Test Patterns

### Test form submission
```python
def test_submit_form(authenticated_page, flask_app, clean_db):
    page = authenticated_page
    page.goto(f"{flask_app}/housekeeping-requests")

    page.fill("#room-number", "214")
    page.fill("#start-date", "2026-01-24")
    page.fill("#end-date", "2026-01-27")
    page.click('button[type="submit"]')

    page.wait_for_load_state("networkidle")
    expect(page.locator(".inline-error")).not_to_be_visible()
```

### Test validation errors
```python
def test_validation(authenticated_page, flask_app, clean_db):
    page = authenticated_page
    page.goto(f"{flask_app}/housekeeping-requests")

    # Submit with invalid data
    page.fill("#start-date", "2026-01-30")
    page.fill("#end-date", "2026-01-20")
    page.click('button[type="submit"]')

    # Verify error appears
    error = page.locator(".inline-error")
    expect(error).to_be_visible()
    expect(error).to_contain_text("start date must be on or before")
```

### Test UI state changes
```python
def test_ui_change(authenticated_page, flask_app, clean_db):
    page = authenticated_page
    page.goto(f"{flask_app}/housekeeping-requests")

    # Initially hidden
    custom_input = page.locator("#custom-frequency-input")
    expect(custom_input).not_to_have_class("visible")

    # Click to show
    page.click('label[data-frequency="custom"]')

    # Now visible
    expect(custom_input).to_have_class(/visible/)
```

## Environment Variables

Set in `conftest.py` for Flask app:
- `DB_PATH` - Test database path
- `CREDENTIALS_FILE` - Test credentials file
- `SECRET_KEY` - Test secret key
- `FLASK_ENV` - Set to 'testing'

## Tips

1. **Use specific selectors**: Prefer IDs and data attributes over classes
2. **Auto-waiting**: Playwright waits automatically for elements
3. **Test isolation**: Each test should clean up after itself
4. **Meaningful assertions**: Use specific assertions that explain what you're testing
5. **Page objects**: For complex apps, consider creating page object classes

## Useful Links

- [Playwright Python Docs](https://playwright.dev/python/docs/intro)
- [Locators Guide](https://playwright.dev/python/docs/locators)
- [Assertions](https://playwright.dev/python/docs/test-assertions)
- [Best Practices](https://playwright.dev/python/docs/best-practices)
