"""
UI component tests that don't require the Flask app to be running.
These tests verify Playwright can interact with UI elements using mock HTML.
"""
import pytest
import re
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_housekeeping_form_interactions(page: Page):
    """Test form interactions with mock housekeeping request form."""
    # Create a mock housekeeping form
    page.set_content("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Housekeeping Requests - DNR App</title>
            <style>
                .frequency-mode { border: 2px solid #ddd; padding: 10px; cursor: pointer; }
                .frequency-mode.selected { border-color: #0066cc; background: #e6f2ff; }
                .custom-frequency-input { display: none; }
                .custom-frequency-input.visible { display: block; }
                .char-counter { font-size: 0.9em; color: #666; }
            </style>
        </head>
        <body>
            <h1>Housekeeping Requests</h1>
            <form id="housekeeping-form">
                <input type="text" id="room-number" name="room_number" required placeholder="Room 214">
                <input type="text" id="guest-name" name="guest_name" placeholder="Guest Name">
                <input type="date" id="start-date" name="start_date" required>
                <input type="date" id="end-date" name="end_date" required>

                <div class="frequency-modes">
                    <label class="frequency-mode selected" data-frequency="none">
                        <input type="radio" name="frequency" value="none" checked>
                        No Housekeeping
                    </label>
                    <label class="frequency-mode" data-frequency="daily">
                        <input type="radio" name="frequency" value="daily">
                        Daily Housekeeping
                    </label>
                    <label class="frequency-mode" data-frequency="every_3rd_day">
                        <input type="radio" name="frequency" value="every_3rd_day">
                        Every 3rd Day
                    </label>
                    <label class="frequency-mode" data-frequency="custom">
                        <input type="radio" name="frequency" value="custom">
                        Custom Frequency
                    </label>
                </div>

                <div class="custom-frequency-input" id="custom-frequency-input">
                    <input type="number" id="frequency-days" name="frequency_days" min="1" max="30">
                </div>

                <textarea id="request-notes" name="notes" maxlength="1000"></textarea>
                <small class="char-counter">0 / 1000</small>

                <button type="submit">Add Request</button>
            </form>

            <script>
                // Frequency mode selection
                document.querySelectorAll('.frequency-mode').forEach(function(mode) {
                    mode.addEventListener('click', function() {
                        var radio = this.querySelector('input[type="radio"]');
                        radio.checked = true;

                        document.querySelectorAll('.frequency-mode').forEach(function(m) {
                            m.classList.remove('selected');
                        });
                        this.classList.add('selected');

                        var frequency = this.getAttribute('data-frequency');
                        var customInput = document.getElementById('custom-frequency-input');
                        if (frequency === 'custom') {
                            customInput.classList.add('visible');
                        } else {
                            customInput.classList.remove('visible');
                        }
                    });
                });

                // Character counter
                var textarea = document.getElementById('request-notes');
                var counter = document.querySelector('.char-counter');
                textarea.addEventListener('input', function() {
                    counter.textContent = textarea.value.length + ' / 1000';
                });
            </script>
        </body>
        </html>
    """)

    # Verify page loaded
    expect(page).to_have_title("Housekeeping Requests - DNR App")
    expect(page.locator("h1")).to_contain_text("Housekeeping Requests")

    # Test filling in room number
    page.fill("#room-number", "214")
    expect(page.locator("#room-number")).to_have_value("214")

    # Test filling in guest name
    page.fill("#guest-name", "J. Smith")
    expect(page.locator("#guest-name")).to_have_value("J. Smith")

    # Test date inputs
    page.fill("#start-date", "2026-01-24")
    page.fill("#end-date", "2026-01-27")
    expect(page.locator("#start-date")).to_have_value("2026-01-24")
    expect(page.locator("#end-date")).to_have_value("2026-01-27")


@pytest.mark.e2e
def test_frequency_selection(page: Page):
    """Test frequency mode selection visual feedback."""
    # Create a simple frequency selector
    page.set_content("""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                .frequency-mode { border: 2px solid #ddd; padding: 10px; margin: 5px; }
                .frequency-mode.selected { border-color: #0066cc; background: #e6f2ff; }
            </style>
        </head>
        <body>
            <label class="frequency-mode selected" data-frequency="none" id="mode-none">
                <input type="radio" name="frequency" value="none" checked> No Service
            </label>
            <label class="frequency-mode" data-frequency="daily" id="mode-daily">
                <input type="radio" name="frequency" value="daily"> Daily
            </label>
            <script>
                document.querySelectorAll('.frequency-mode').forEach(function(mode) {
                    mode.addEventListener('click', function() {
                        document.querySelectorAll('.frequency-mode').forEach(m => m.classList.remove('selected'));
                        this.classList.add('selected');
                        this.querySelector('input').checked = true;
                    });
                });
            </script>
        </body>
        </html>
    """)

    # Initially "No Service" should be selected
    no_service = page.locator("#mode-none")
    expect(no_service).to_have_class(re.compile("selected"))

    # Click on "Daily"
    daily = page.locator("#mode-daily")
    daily.click()

    # Daily should now be selected
    expect(daily).to_have_class(re.compile("selected"))

    # No service should no longer be selected
    expect(no_service).not_to_have_class(re.compile("selected"))

    # Verify radio button is checked
    expect(page.locator('input[value="daily"]')).to_be_checked()


@pytest.mark.e2e
def test_custom_frequency_toggle(page: Page):
    """Test that custom frequency input shows/hides correctly."""
    page.set_content("""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                .custom-frequency-input { display: none; }
                .custom-frequency-input.visible { display: block; }
            </style>
        </head>
        <body>
            <label id="custom-mode" data-frequency="custom">
                <input type="radio" name="frequency" value="custom"> Custom
            </label>
            <label id="daily-mode" data-frequency="daily">
                <input type="radio" name="frequency" value="daily"> Daily
            </label>
            <div class="custom-frequency-input" id="custom-input">
                <input type="number" id="frequency-days">
            </div>
            <script>
                document.querySelectorAll('[data-frequency]').forEach(function(mode) {
                    mode.addEventListener('click', function() {
                        var freq = this.getAttribute('data-frequency');
                        var customInput = document.getElementById('custom-input');
                        if (freq === 'custom') {
                            customInput.classList.add('visible');
                        } else {
                            customInput.classList.remove('visible');
                        }
                    });
                });
            </script>
        </body>
        </html>
    """)

    custom_input = page.locator("#custom-input")

    # Initially should not be visible
    expect(custom_input).not_to_have_class(re.compile("visible"))

    # Click custom mode
    page.click("#custom-mode")

    # Should now be visible
    expect(custom_input).to_have_class(re.compile("visible"))

    # Click daily mode
    page.click("#daily-mode")

    # Should be hidden again
    expect(custom_input).not_to_have_class(re.compile("visible"))


@pytest.mark.e2e
def test_character_counter(page: Page):
    """Test character counter updates correctly."""
    page.set_content("""
        <!DOCTYPE html>
        <html>
        <body>
            <textarea id="notes" maxlength="1000"></textarea>
            <small class="char-counter">0 / 1000</small>
            <script>
                var textarea = document.getElementById('notes');
                var counter = document.querySelector('.char-counter');
                textarea.addEventListener('input', function() {
                    counter.textContent = textarea.value.length + ' / 1000';
                });
            </script>
        </body>
        </html>
    """)

    counter = page.locator(".char-counter")

    # Initially should show 0
    expect(counter).to_contain_text("0 / 1000")

    # Type some text
    page.fill("#notes", "Guest prefers afternoon service")

    # Counter should update
    expect(counter).to_contain_text("31 / 1000")

    # Type more text
    page.fill("#notes", "This is a longer note with more details about the housekeeping request")

    # Counter should update again
    expect(counter).to_contain_text("70 / 1000")
