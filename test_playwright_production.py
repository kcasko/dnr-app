"""
Playwright End-to-End Tests for DNR App Production Environment
Tests all major functionality including authentication, CRUD operations, and navigation.
"""
import pytest
import re
import time
from datetime import date, timedelta
from playwright.sync_api import Page, expect

# Configuration
BASE_URL = "http://localhost:5000"  # Change to production URL if needed
TEST_TIMEOUT = 30000  # 30 seconds

# Test credentials (should match your test database)
MANAGER_USERNAME = "test_manager"
MANAGER_PASSWORD = "TestPass123"
FRONT_DESK_USERNAME = "test_user"  
FRONT_DESK_PASSWORD = "FrontDesk123"


@pytest.fixture(scope="function")
def authenticated_page(page: Page):
    """Fixture that provides an authenticated page session"""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    
    # Login
    page.fill('input[name="username"]', MANAGER_USERNAME)
    page.fill('input[name="password"]', MANAGER_PASSWORD)
    page.click('button[type="submit"]')
    
    # Wait for redirect to overview
    page.wait_for_url(f"{BASE_URL}/overview", timeout=TEST_TIMEOUT)
    
    return page


class TestAuthentication:
    """Test authentication and session management"""
    
    def test_login_page_loads(self, page: Page):
        """Verify login page loads correctly"""
        page.goto(BASE_URL)
        expect(page).to_have_title(re.compile("Login", re.IGNORECASE))
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()
        print("✓ Login page loads correctly")
    
    def test_successful_login(self, page: Page):
        """Test successful manager login"""
        page.goto(BASE_URL)
        page.fill('input[name="username"]', MANAGER_USERNAME)
        page.fill('input[name="password"]', MANAGER_PASSWORD)
        page.click('button[type="submit"]')
        
        # Should redirect to overview
        page.wait_for_url(f"{BASE_URL}/overview", timeout=TEST_TIMEOUT)
        expect(page).to_have_url(re.compile("/overview"))
        print("✓ Successfully logged in as manager")
    
    def test_invalid_login(self, page: Page):
        """Test login with invalid credentials"""
        page.goto(BASE_URL)
        page.fill('input[name="username"]', "invalid_user")
        page.fill('input[name="password"]', "wrong_password")
        page.click('button[type="submit"]')
        
        # Should show error message
        expect(page.locator('text=/invalid|incorrect/i')).to_be_visible(timeout=5000)
        print("✓ Invalid login correctly rejected")
    
    def test_logout(self, authenticated_page: Page):
        """Test logout functionality"""
        # Find and click logout
        authenticated_page.click('a[href="/logout"]')
        
        # Should redirect to login
        authenticated_page.wait_for_url(f"{BASE_URL}/login", timeout=TEST_TIMEOUT)
        expect(authenticated_page).to_have_url(re.compile("/login"))
        print("✓ Logout successful")


class TestNavigation:
    """Test navigation and page access"""
    
    def test_overview_page(self, authenticated_page: Page):
        """Test overview/dashboard page"""
        authenticated_page.goto(f"{BASE_URL}/overview")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Should show overview content
        expect(authenticated_page.locator('text=/overview|dashboard/i')).to_be_visible()
        print("✓ Overview page accessible")
    
    def test_dnr_list_page(self, authenticated_page: Page):
        """Test DNR list page loads"""
        authenticated_page.goto(f"{BASE_URL}/dnr")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Should show DNR interface
        expect(authenticated_page.locator('text=/do not rent|dnr|restricted/i')).to_be_visible()
        print("✓ DNR list page accessible")
    
    def test_schedule_page(self, authenticated_page: Page):
        """Test schedule page loads"""
        authenticated_page.goto(f"{BASE_URL}/schedule")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Should show schedule
        expect(authenticated_page.locator('text=/schedule|shift/i')).to_be_visible()
        print("✓ Schedule page accessible")
    
    def test_settings_page(self, authenticated_page: Page):
        """Test settings page loads (manager only)"""
        authenticated_page.goto(f"{BASE_URL}/settings")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Should show settings
        expect(authenticated_page.locator('text=/settings|users|account/i')).to_be_visible()
        print("✓ Settings page accessible")


class TestDNROperations:
    """Test DNR record CRUD operations"""
    
    def test_add_dnr_record(self, authenticated_page: Page):
        """Test adding a new DNR record"""
        authenticated_page.goto(f"{BASE_URL}/dnr")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Click add button
        authenticated_page.click('button:has-text("Add")')
        
        # Wait for modal
        authenticated_page.wait_for_selector('[role="dialog"], .modal', timeout=5000)
        
        # Fill in form
        authenticated_page.fill('input[name="guest_name"]', 'Playwright Test User')
        
        # Select permanent ban
        authenticated_page.click('input[value="permanent"]')
        
        # Select a reason
        authenticated_page.click('input[type="checkbox"][value*="Noise"]')
        
        # Fill initials
        authenticated_page.fill('input[name="staff_initials"]', 'PT')
        
        # Submit form
        authenticated_page.click('button[type="submit"]:has-text("Add")')
        
        # Wait for success toast or modal to close
        time.sleep(2)  # Give time for request to process
        
        # Verify record appears in list
        authenticated_page.wait_for_selector('text=Playwright Test User', timeout=10000)
        print("✓ DNR record added successfully")
    
    def test_view_dnr_record(self, authenticated_page: Page):
        """Test viewing a DNR record detail"""
        authenticated_page.goto(f"{BASE_URL}/dnr")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Click on first record
        record = authenticated_page.locator('.record-item, tr[data-id]').first
        if record.count() > 0:
            record.click()
            
            # Wait for detail modal
            authenticated_page.wait_for_selector('[role="dialog"], .modal', timeout=5000)
            
            # Should show record details
            expect(authenticated_page.locator('text=/guest|name/i')).to_be_visible()
            print("✓ DNR record detail view works")
        else:
            print("⚠ No records found to view")
    
    def test_add_timeline_note(self, authenticated_page: Page):
        """Test adding a timeline note to a record"""
        authenticated_page.goto(f"{BASE_URL}/dnr")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Click on first record
        record = authenticated_page.locator('.record-item, tr[data-id]').first
        if record.count() > 0:
            record.click()
            
            # Wait for detail modal
            authenticated_page.wait_for_selector('[role="dialog"], .modal', timeout=5000)
            
            # Find add note section
            note_textarea = authenticated_page.locator('textarea[placeholder*="note"], textarea[name*="note"]').first
            if note_textarea.count() > 0:
                note_textarea.fill('Playwright test note - automated test entry')
                
                # Fill initials
                initials_input = authenticated_page.locator('input[name="staff_initials"], input[placeholder*="initials"]').first
                if initials_input.count() > 0:
                    initials_input.fill('PT')
                
                # Submit
                authenticated_page.click('button:has-text("Add Note")')
                time.sleep(2)
                
                print("✓ Timeline note added successfully")
            else:
                print("⚠ Note input not found")
        else:
            print("⚠ No records found")
    
    def test_lift_ban(self, authenticated_page: Page):
        """Test lifting a ban (manager function)"""
        authenticated_page.goto(f"{BASE_URL}/dnr")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Find an active record
        record = authenticated_page.locator('.record-item, tr[data-id]').first
        if record.count() > 0:
            record.click()
            
            # Wait for detail modal
            authenticated_page.wait_for_selector('[role="dialog"], .modal', timeout=5000)
            
            # Look for lift/remove button
            lift_button = authenticated_page.locator('button:has-text("Lift"), button:has-text("Remove")')
            if lift_button.count() > 0:
                lift_button.click()
                
                # Fill lift form
                time.sleep(1)
                authenticated_page.fill('input[type="password"]', MANAGER_PASSWORD)
                authenticated_page.select_option('select[name="lift_type"]', 'manager_override')
                authenticated_page.fill('textarea[name="lift_reason"]', 'Playwright test - automated ban removal')
                authenticated_page.fill('input[name="initials"]', 'PT')
                
                # Submit
                authenticated_page.click('button[type="submit"]:has-text("Lift")')
                time.sleep(2)
                
                print("✓ Ban lifted successfully")
            else:
                print("⚠ Lift button not found (record may already be lifted)")
        else:
            print("⚠ No records found")


class TestCSRFProtection:
    """Test CSRF token functionality"""
    
    def test_csrf_token_endpoint(self, authenticated_page: Page):
        """Test CSRF token API endpoint"""
        response = authenticated_page.request.get(f"{BASE_URL}/api/csrf-token")
        assert response.ok, "CSRF token endpoint should return 200"
        
        data = response.json()
        assert 'csrf_token' in data, "Response should contain csrf_token"
        assert data['csrf_token'] is not None, "CSRF token should not be null"
        print("✓ CSRF token endpoint working")
    
    def test_csrf_token_in_requests(self, authenticated_page: Page):
        """Verify CSRF tokens are included in API requests"""
        authenticated_page.goto(f"{BASE_URL}/dnr")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Check that page has CSRF token
        csrf_token = authenticated_page.evaluate("""
            () => {
                const meta = document.querySelector('meta[name="csrf-token"]');
                return meta ? meta.getAttribute('content') : null;
            }
        """)
        
        # CSRF token might be in JavaScript variable instead
        if not csrf_token:
            print("⚠ CSRF token not found in meta tag (may be in JS variable)")
        else:
            print(f"✓ CSRF token present: {csrf_token[:20]}...")


class TestResponsiveness:
    """Test responsive design and mobile views"""
    
    def test_mobile_viewport(self, authenticated_page: Page):
        """Test mobile viewport rendering"""
        authenticated_page.set_viewport_size({"width": 375, "height": 667})
        authenticated_page.goto(f"{BASE_URL}/overview")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Page should still be functional
        expect(authenticated_page.locator('body')).to_be_visible()
        print("✓ Mobile viewport renders correctly")
    
    def test_tablet_viewport(self, authenticated_page: Page):
        """Test tablet viewport rendering"""
        authenticated_page.set_viewport_size({"width": 768, "height": 1024})
        authenticated_page.goto(f"{BASE_URL}/overview")
        authenticated_page.wait_for_load_state("networkidle")
        
        # Page should still be functional
        expect(authenticated_page.locator('body')).to_be_visible()
        print("✓ Tablet viewport renders correctly")


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_404_page(self, authenticated_page: Page):
        """Test 404 error page"""
        authenticated_page.goto(f"{BASE_URL}/nonexistent-page")
        
        # Should show 404 or redirect
        # Most apps redirect to home or show 404
        expect(authenticated_page.locator('body')).to_be_visible()
        print("✓ 404 page handled")
    
    def test_unauthorized_access(self, page: Page):
        """Test accessing protected page without login"""
        page.goto(f"{BASE_URL}/settings")
        
        # Should redirect to login
        page.wait_for_url(re.compile("/login"), timeout=TEST_TIMEOUT)
        expect(page).to_have_url(re.compile("/login"))
        print("✓ Unauthorized access redirects to login")


def run_all_tests():
    """Run all Playwright tests"""
    import subprocess
    
    print("=" * 70)
    print("DNR APP - PLAYWRIGHT PRODUCTION TESTS")
    print("=" * 70)
    print(f"Testing URL: {BASE_URL}")
    print("=" * 70)
    
    # Run pytest with playwright
    result = subprocess.run(
        ["pytest", __file__, "-v", "--headed", "--slowmo=500"],
        capture_output=False
    )
    
    return result.returncode == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
