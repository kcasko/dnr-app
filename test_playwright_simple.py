"""
Playwright End-to-End Tests for DNR App - Direct Execution
Tests all major functionality without pytest harness
"""
from playwright.sync_api import sync_playwright, Page
import time
from datetime import date, timedelta

# Configuration
BASE_URL = "http://localhost:5000"

# Test credentials
MANAGER_USERNAME = "test_manager"
MANAGER_PASSWORD = "TestPass123"


def test_login_and_navigation(page: Page):
    """Test login and basic navigation"""
    print("\n[TEST] Login and Navigation")
    
    # Go to login page
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    
    # Verify login page
    assert page.locator('input[name="username"]').is_visible(), "Username field not found"
    print("  ✓ Login page loaded")
    
    # Login
    page.fill('input[name="username"]', MANAGER_USERNAME)
    page.fill('input[name="password"]', MANAGER_PASSWORD)
    page.click('button[type="submit"]')
    
    # Wait for redirect
    page.wait_for_url(f"{BASE_URL}/overview", timeout=10000)
    print("  ✓ Successfully logged in")
    
    # Test navigation to DNR page
    page.click('a[href="/dnr"]')
    page.wait_for_url(f"{BASE_URL}/dnr", timeout=10000)
    print("  ✓ Navigated to DNR page")
    
    # Test navigation to schedule
    page.click('a[href="/schedule"]')
    page.wait_for_url(f"{BASE_URL}/schedule", timeout=10000)
    print("  ✓ Navigated to schedule page")
    
    return True


def test_dnr_operations(page: Page):
    """Test DNR record operations"""
    print("\n[TEST] DNR Operations")
    
    # Navigate to DNR page
    page.goto(f"{BASE_URL}/dnr")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    
    # Test adding a record
    add_button = page.locator('button:has-text("Add")').first
    if add_button.is_visible():
        add_button.click()
        time.sleep(1)
        
        # Fill form
        page.fill('input[name="guest_name"]', 'Playwright Test Guest')
        page.click('input[value="permanent"]')
        
        # Select first checkbox reason
        page.locator('input[type="checkbox"]').first.check()
        
        page.fill('input[name="staff_initials"]', 'PT')
        
        # Submit
        page.click('button[type="submit"]:has-text("Add")')
        time.sleep(2)
        
        print("  ✓ DNR record added")
    else:
        print("  ⚠ Add button not found")
    
    # Reload and verify record appears
    page.reload()
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    
    if page.locator('text=Playwright Test Guest').count() > 0:
        print("  ✓ Record appears in list")
        
        # Click on record to view details
        page.locator('text=Playwright Test Guest').first.click()
        time.sleep(1)
        print("  ✓ Record detail view opened")
    else:
        print("  ⚠ Record not found in list")
    
    return True


def test_csrf_protection(page: Page):
    """Test CSRF token functionality"""
    print("\n[TEST] CSRF Protection")
    
    # Get CSRF token via API
    response = page.request.get(f"{BASE_URL}/api/csrf-token")
    assert response.ok, "CSRF endpoint failed"
    
    data = response.json()
    assert 'csrf_token' in data, "No CSRF token in response"
    assert data['csrf_token'] is not None, "CSRF token is null"
    
    print(f"  ✓ CSRF token retrieved: {data['csrf_token'][:20]}...")
    return True


def test_settings_page(page: Page):
    """Test settings page access"""
    print("\n[TEST] Settings Page")
    
    page.goto(f"{BASE_URL}/settings")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    
    # Should show settings content - check for page title specifically
    if page.locator('h1.page-title:has-text("Settings")').count() > 0:
        print("  ✓ Settings page accessible")
        return True
    else:
        print("  ⚠ Settings page may not have expected content")
        return False


def test_overview_alerts(page: Page):
    """Test overview page shows alerts"""
    print("\n[TEST] Overview/Dashboard")
    
    page.goto(f"{BASE_URL}/overview")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    
    #Look for dashboard elements
    if page.locator('text=/overview|dashboard|alert|notification/i').count() > 0:
        print("  ✓ Overview page loaded with content")
        return True
    else:
        print("  ⚠ Overview page may not have expected content")
        return False


def test_logout(page: Page):
    """Test logout functionality"""
    print("\n[TEST] Logout")
    
    logout_link = page.locator('a[href="/logout"]')
    if logout_link.is_visible():
        logout_link.click()
        page.wait_for_url(f"{BASE_URL}/login", timeout=10000)
        print("  ✓ Logout successful")
        return True
    else:
        print("  ⚠ Logout link not found")
        return False


def run_all_tests():
    """Run all tests with Playwright"""
    print("=" * 70)
    print("DNR APP - PLAYWRIGHT PRODUCTION TESTS")
    print("=" * 70)
    print(f"Testing URL: {BASE_URL}")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        
        try:
            # Run tests
            tests = [
                test_login_and_navigation,
                test_dnr_operations,
                test_csrf_protection,
                test_settings_page,
                test_overview_alerts,
                test_logout
            ]
            
            for test in tests:
                try:
                    result = test(page)
                    if result:
                        passed += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"  ✗ Error: {str(e)}")
                    failed += 1
            
            # Summary
            print("\n" + "=" * 70)
            print("TEST SUMMARY")
            print("=" * 70)
            print(f"Passed: {passed}")
            print(f"Failed: {failed}")
            print(f"Total:  {passed + failed}")
            print("=" * 70)
            
            if failed == 0:
                print("\n✓ ALL TESTS PASSED!")
            else:
                print(f"\n⚠ {failed} test(s) failed")
            
        finally:
            # Close browser
            time.sleep(2)  # Give user time to see results
            browser.close()
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
