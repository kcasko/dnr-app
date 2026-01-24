# Running Playwright Tests - Quick Start

## ✅ Tests Are Working!

All Playwright tests are set up and working. Here's what you can do:

## Option 1: Run Working Tests Now (Recommended)

These tests work immediately without any additional setup:

```bash
# Run all working tests (7 tests)
.venv\Scripts\pytest tests/test_playwright_setup.py tests/test_ui_components.py -v --headed
```

This will:
- Launch a browser window (visible)
- Run 7 tests in about 3 seconds
- Test Playwright functionality and UI components
- Show you how Playwright works

### What These Tests Cover

✅ **Setup Tests** (3 tests)
- Browser can launch and navigate
- Forms can be filled
- Elements can be clicked

✅ **UI Component Tests** (4 tests)
- Housekeeping form interactions
- Frequency mode selection
- Custom frequency toggle
- Character counter

## Option 2: Run Tests Faster (Headless Mode)

```bash
# Run without showing browser (faster)
.venv\Scripts\pytest tests/test_playwright_setup.py tests/test_ui_components.py -v --headed=false
```

## Option 3: Run Full E2E Tests (Advanced)

The full end-to-end tests require your Flask app to be running. Use two terminals:

**Terminal 1** - Start your Flask app:
```bash
cd e:\Repos\dnr-app
.venv\Scripts\python.exe app.py
```

**Terminal 2** - Run E2E tests:
```bash
cd e:\Repos\dnr-app
.venv\Scripts\pytest tests/test_housekeeping_requests.py -v --headed
```

These tests will:
- Navigate to your running app
- Test complete user workflows
- Interact with the real database
- Verify all functionality end-to-end

## Common Commands

| Command | Description |
|---------|-------------|
| `.venv\Scripts\pytest -v` | Run ALL tests |
| `.venv\Scripts\pytest tests/test_ui_components.py -v` | Run only UI tests |
| `.venv\Scripts\pytest --headed` | Show browser window |
| `.venv\Scripts\pytest --headed=false` | Hide browser (faster) |
| `.venv\Scripts\pytest -k "character"` | Run tests matching "character" |
| `.venv\Scripts\pytest -x` | Stop on first failure |

## Test Results

See [TEST_RESULTS.md](TEST_RESULTS.md) for detailed test results and status.

## More Information

- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Complete testing guide
- [tests/QUICK_REFERENCE.md](tests/QUICK_REFERENCE.md) - Command cheat sheet
- [tests/README.md](tests/README.md) - Detailed documentation

## Quick Examples

### Watch a test run
```bash
# See the browser automation in action
.venv\Scripts\pytest tests/test_ui_components.py::test_frequency_selection -v --headed
```

### Run all tests silently
```bash
# Fast execution, no browser window
.venv\Scripts\pytest tests/test_playwright_setup.py tests/test_ui_components.py --headed=false
```

### Debug a failing test
```bash
# Add page.pause() in your test code, then run
.venv\Scripts\pytest tests/test_ui_components.py::test_character_counter -v --headed
```

---

**Ready to try it?** Run this command to see Playwright in action:

```bash
.venv\Scripts\pytest tests/test_ui_components.py -v --headed
```
