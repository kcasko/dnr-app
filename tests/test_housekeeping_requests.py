"""
End-to-end tests for the Housekeeping Requests functionality using Playwright.
"""
import pytest
import re
from datetime import date, timedelta
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestHousekeepingRequests:
    """Test suite for housekeeping requests functionality."""

    def test_page_loads_successfully(self, authenticated_page: Page, flask_app, clean_db):
        """Test that the housekeeping requests page loads correctly."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Verify page title
        expect(authenticated_page).to_have_title("Housekeeping Requests - DNR App")

        # Verify main heading
        heading = authenticated_page.locator("h1")
        expect(heading).to_contain_text("Housekeeping Requests")

        # Verify form is present
        form = authenticated_page.locator("#housekeeping-form")
        expect(form).to_be_visible()

    def test_add_housekeeping_request_no_service(self, authenticated_page: Page, flask_app, clean_db):
        """Test adding a housekeeping request with no housekeeping service."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill out the form
        authenticated_page.fill("#room-number", "214")
        authenticated_page.fill("#guest-name", "J. Smith")

        # Set dates
        start_date = date.today().isoformat()
        end_date = (date.today() + timedelta(days=3)).isoformat()
        authenticated_page.fill("#start-date", start_date)
        authenticated_page.fill("#end-date", end_date)

        # Select "No Housekeeping" (already selected by default)
        no_service = authenticated_page.locator('label[data-frequency="none"]')
        no_service.click()

        # Submit the form
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')

        # Wait for page to reload/redirect
        authenticated_page.wait_for_load_state("networkidle")

        # Verify success (no error message)
        error = authenticated_page.locator(".inline-error")
        expect(error).not_to_be_visible()

    def test_add_housekeeping_request_every_3rd_day(self, authenticated_page: Page, flask_app, clean_db):
        """Test adding a housekeeping request with every 3rd day frequency."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill out the form
        authenticated_page.fill("#room-number", "315")
        authenticated_page.fill("#guest-name", "A. Johnson")

        # Set dates
        start_date = date.today().isoformat()
        end_date = (date.today() + timedelta(days=7)).isoformat()
        authenticated_page.fill("#start-date", start_date)
        authenticated_page.fill("#end-date", end_date)

        # Select "Every 3rd Day"
        every_3rd = authenticated_page.locator('label[data-frequency="every_3rd_day"]')
        every_3rd.click()

        # Verify the radio button is checked
        radio = authenticated_page.locator('input[name="frequency"][value="every_3rd_day"]')
        expect(radio).to_be_checked()

        # Add notes
        authenticated_page.fill("#request-notes", "Guest prefers service in afternoon")

        # Submit the form
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')

        # Wait for page to reload
        authenticated_page.wait_for_load_state("networkidle")

        # Verify no error
        error = authenticated_page.locator(".inline-error")
        expect(error).not_to_be_visible()

    def test_add_housekeeping_request_daily(self, authenticated_page: Page, flask_app, clean_db):
        """Test adding a housekeeping request with daily frequency."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill out the form
        authenticated_page.fill("#room-number", "102")
        authenticated_page.fill("#guest-name", "M. Davis")

        # Set dates
        start_date = date.today().isoformat()
        end_date = (date.today() + timedelta(days=5)).isoformat()
        authenticated_page.fill("#start-date", start_date)
        authenticated_page.fill("#end-date", end_date)

        # Select "Daily Housekeeping"
        daily = authenticated_page.locator('label[data-frequency="daily"]')
        daily.click()

        # Verify the radio button is checked
        radio = authenticated_page.locator('input[name="frequency"][value="daily"]')
        expect(radio).to_be_checked()

        # Submit the form
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')

        # Wait for page to reload
        authenticated_page.wait_for_load_state("networkidle")

        # Verify no error
        error = authenticated_page.locator(".inline-error")
        expect(error).not_to_be_visible()

    def test_custom_frequency_shows_input(self, authenticated_page: Page, flask_app, clean_db):
        """Test that selecting custom frequency shows the custom input field."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Initially, custom input should not be visible
        custom_input = authenticated_page.locator("#custom-frequency-input")
        expect(custom_input).not_to_have_class("visible")

        # Select "Custom Frequency"
        custom = authenticated_page.locator('label[data-frequency="custom"]')
        custom.click()

        # Now custom input should be visible
        expect(custom_input).to_have_class(re.compile("visible"))

    def test_custom_frequency_preview(self, authenticated_page: Page, flask_app, clean_db):
        """Test the custom frequency date preview functionality."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill in dates
        start_date = date.today().isoformat()
        end_date = (date.today() + timedelta(days=10)).isoformat()
        authenticated_page.fill("#start-date", start_date)
        authenticated_page.fill("#end-date", end_date)

        # Select custom frequency
        custom = authenticated_page.locator('label[data-frequency="custom"]')
        custom.click()

        # Enter custom frequency days
        authenticated_page.fill("#frequency-days", "4")

        # Click preview button
        authenticated_page.click("#preview-dates-btn")

        # Wait for preview to appear
        preview = authenticated_page.locator("#service-dates-preview")
        authenticated_page.wait_for_selector("#service-dates-preview.visible", timeout=5000)

        # Verify preview is visible
        expect(preview).to_have_class(re.compile("visible"))

        # Verify preview content exists
        preview_content = authenticated_page.locator("#preview-content")
        expect(preview_content).not_to_be_empty()

    def test_add_housekeeping_request_custom_frequency(self, authenticated_page: Page, flask_app, clean_db):
        """Test adding a housekeeping request with custom frequency."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill out the form
        authenticated_page.fill("#room-number", "220")
        authenticated_page.fill("#guest-name", "R. Williams")

        # Set dates
        start_date = date.today().isoformat()
        end_date = (date.today() + timedelta(days=12)).isoformat()
        authenticated_page.fill("#start-date", start_date)
        authenticated_page.fill("#end-date", end_date)

        # Select custom frequency
        custom = authenticated_page.locator('label[data-frequency="custom"]')
        custom.click()

        # Enter custom frequency days
        authenticated_page.fill("#frequency-days", "5")

        # Submit the form
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')

        # Wait for page to reload
        authenticated_page.wait_for_load_state("networkidle")

        # Verify no error
        error = authenticated_page.locator(".inline-error")
        expect(error).not_to_be_visible()

    def test_form_validation_missing_fields(self, authenticated_page: Page, flask_app, clean_db):
        """Test form validation when required fields are missing."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Try to submit without filling in room number
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')

        # HTML5 validation should prevent submission
        # Check that we're still on the same page
        expect(authenticated_page).to_have_url(f"{flask_app}/housekeeping-requests")

    def test_character_counter_for_notes(self, authenticated_page: Page, flask_app, clean_db):
        """Test that the character counter updates when typing notes."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Initially counter should show 0 / 1000
        counter = authenticated_page.locator(".char-counter").first
        expect(counter).to_contain_text("0 / 1000")

        # Type some text
        notes_field = authenticated_page.locator("#request-notes")
        test_text = "Guest prefers morning service"
        notes_field.fill(test_text)

        # Counter should update
        expected_count = len(test_text)
        expect(counter).to_contain_text(f"{expected_count} / 1000")

    def test_frequency_mode_selection_visual_feedback(self, authenticated_page: Page, flask_app, clean_db):
        """Test that selecting a frequency mode shows visual feedback."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Initially "No Housekeeping" should be selected
        no_service = authenticated_page.locator('label[data-frequency="none"]')
        expect(no_service).to_have_class(re.compile("selected"))

        # Click on "Daily Housekeeping"
        daily = authenticated_page.locator('label[data-frequency="daily"]')
        daily.click()

        # Daily should now be selected
        expect(daily).to_have_class(re.compile("selected"))

        # No service should no longer be selected
        expect(no_service).not_to_have_class(re.compile("selected"))

    def test_date_validation(self, authenticated_page: Page, flask_app, clean_db):
        """Test that end date must be after start date."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill in the form with invalid dates
        authenticated_page.fill("#room-number", "101")

        # Set end date before start date
        start_date = (date.today() + timedelta(days=5)).isoformat()
        end_date = date.today().isoformat()
        authenticated_page.fill("#start-date", start_date)
        authenticated_page.fill("#end-date", end_date)

        # Select a frequency
        daily = authenticated_page.locator('label[data-frequency="daily"]')
        daily.click()

        # Submit the form
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')

        # Wait for page to reload
        authenticated_page.wait_for_load_state("networkidle")

        # Should see an error message
        error = authenticated_page.locator(".inline-error")
        expect(error).to_be_visible()
        expect(error).to_contain_text("start date must be on or before the end date")

    def test_print_functionality(self, authenticated_page: Page, flask_app, clean_db):
        """Test that the print button exists."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Verify print button exists
        print_button = authenticated_page.locator('button:has-text("Print Today\'s Requests")')
        expect(print_button).to_be_visible()

    def test_navigation_links(self, authenticated_page: Page, flask_app, clean_db):
        """Test that navigation links are present and functional."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Check for navigation links in header
        overview_link = authenticated_page.locator('a[href="/overview"]')
        expect(overview_link).to_be_visible()

        dnr_link = authenticated_page.locator('a[href="/dnr"]')
        expect(dnr_link).to_be_visible()

        # Click on overview link
        overview_link.click()

        # Should navigate to overview page
        authenticated_page.wait_for_url(f"{flask_app}/overview")
        expect(authenticated_page).to_have_url(f"{flask_app}/overview")

    def test_empty_state_message(self, authenticated_page: Page, flask_app, clean_db):
        """Test that an empty state message is shown when no requests are due today."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Look for empty state message
        empty_state = authenticated_page.locator(".empty-state")

        # If no requests are due today, empty state should be visible
        # Note: This test assumes clean database with no requests due today
        if empty_state.count() > 0:
            expect(empty_state).to_be_visible()
            expect(empty_state).to_contain_text("No housekeeping requests due today")

    @pytest.mark.slow
    def test_add_multiple_requests(self, authenticated_page: Page, flask_app, clean_db):
        """Test adding multiple housekeeping requests."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Add first request
        authenticated_page.fill("#room-number", "201")
        authenticated_page.fill("#start-date", date.today().isoformat())
        authenticated_page.fill("#end-date", (date.today() + timedelta(days=3)).isoformat())
        authenticated_page.locator('label[data-frequency="daily"]').click()
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')
        authenticated_page.wait_for_load_state("networkidle")

        # Add second request
        authenticated_page.fill("#room-number", "202")
        authenticated_page.fill("#start-date", date.today().isoformat())
        authenticated_page.fill("#end-date", (date.today() + timedelta(days=5)).isoformat())
        authenticated_page.locator('label[data-frequency="every_3rd_day"]').click()
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')
        authenticated_page.wait_for_load_state("networkidle")

        # Verify no errors
        error = authenticated_page.locator(".inline-error")
        expect(error).not_to_be_visible()

    def test_custom_frequency_validation(self, authenticated_page: Page, flask_app, clean_db):
        """Test validation for custom frequency days."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill basic info
        authenticated_page.fill("#room-number", "305")
        authenticated_page.fill("#start-date", date.today().isoformat())
        authenticated_page.fill("#end-date", (date.today() + timedelta(days=10)).isoformat())

        # Select custom frequency
        custom = authenticated_page.locator('label[data-frequency="custom"]')
        custom.click()

        # Try to submit without entering frequency days
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')

        # Should still be on the same page (HTML5 validation)
        expect(authenticated_page).to_have_url(f"{flask_app}/housekeeping-requests")

    def test_guest_name_optional(self, authenticated_page: Page, flask_app, clean_db):
        """Test that guest name field is optional."""
        authenticated_page.goto(f"{flask_app}/housekeeping-requests")

        # Fill out form without guest name
        authenticated_page.fill("#room-number", "404")
        authenticated_page.fill("#start-date", date.today().isoformat())
        authenticated_page.fill("#end-date", (date.today() + timedelta(days=2)).isoformat())
        authenticated_page.locator('label[data-frequency="daily"]').click()

        # Submit the form
        authenticated_page.click('button[type="submit"]:has-text("Add Request")')
        authenticated_page.wait_for_load_state("networkidle")

        # Should succeed without error
        error = authenticated_page.locator(".inline-error")
        expect(error).not_to_be_visible()
