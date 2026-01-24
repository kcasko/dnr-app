"""
Simple test to verify Playwright is set up correctly.
This test doesn't require the Flask app to be running.
"""
import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_playwright_browser_launches(page):
    """Verify that Playwright can launch a browser and navigate."""
    # Navigate to a simple page
    page.goto("https://example.com")

    # Verify page loaded
    expect(page).to_have_title("Example Domain")

    # Verify we can interact with elements
    heading = page.locator("h1")
    expect(heading).to_be_visible()
    expect(heading).to_contain_text("Example Domain")


@pytest.mark.e2e
def test_playwright_can_fill_forms(page):
    """Verify Playwright can interact with form elements."""
    # Create a simple HTML page with a form
    page.set_content("""
        <!DOCTYPE html>
        <html>
        <head><title>Test Form</title></head>
        <body>
            <form id="test-form">
                <input type="text" id="name" name="name" />
                <input type="date" id="date" name="date" />
                <textarea id="notes" name="notes"></textarea>
                <button type="submit">Submit</button>
            </form>
        </body>
        </html>
    """)

    # Fill in the form
    page.fill("#name", "Test User")
    page.fill("#date", "2026-01-24")
    page.fill("#notes", "Test notes")

    # Verify values were filled
    expect(page.locator("#name")).to_have_value("Test User")
    expect(page.locator("#date")).to_have_value("2026-01-24")
    expect(page.locator("#notes")).to_have_value("Test notes")


@pytest.mark.e2e
def test_playwright_can_click_elements(page):
    """Verify Playwright can click elements and handle events."""
    page.set_content("""
        <!DOCTYPE html>
        <html>
        <head><title>Click Test</title></head>
        <body>
            <button id="test-btn">Click Me</button>
            <div id="result" style="display:none;">Clicked!</div>
            <script>
                document.getElementById('test-btn').addEventListener('click', function() {
                    document.getElementById('result').style.display = 'block';
                });
            </script>
        </body>
        </html>
    """)

    # Initially result should not be visible
    result = page.locator("#result")
    expect(result).not_to_be_visible()

    # Click the button
    page.click("#test-btn")

    # Result should now be visible
    expect(result).to_be_visible()
    expect(result).to_contain_text("Clicked!")
