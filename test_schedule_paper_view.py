"""
Playwright test to diagnose paper schedule view issues.
"""
from playwright.sync_api import sync_playwright
import time

def test_schedule_paper_view():
    with sync_playwright() as p:
        # Launch browser in headed mode to see what's happening
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()

        print("=" * 60)
        print("TESTING SCHEDULE PAPER VIEW")
        print("=" * 60)

        # Navigate to login page
        print("\n[1/6] Navigating to login page...")
        page.goto("http://localhost:5000/login")
        page.wait_for_load_state("networkidle")

        # Login as manager
        print("[2/6] Logging in as manager...")
        page.fill("input[name='username']", "manager_qa")
        page.fill("input[name='password']", "TestPass123")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # Navigate to schedule page
        print("[3/6] Navigating to schedule page...")
        page.goto("http://localhost:5000/schedule")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Check if view toggle exists
        print("\n[4/6] Checking for view toggle buttons...")
        shift_view_btn = page.query_selector("button:has-text('Shift View')")
        paper_view_btn = page.query_selector("button:has-text('Paper View')")

        if shift_view_btn and paper_view_btn:
            print("  ✓ View toggle buttons found")
        else:
            print("  ✗ View toggle buttons NOT found")
            print(f"    Shift View button: {shift_view_btn}")
            print(f"    Paper View button: {paper_view_btn}")

        # Check current view
        print("\n[5/6] Checking current view...")
        shift_view_div = page.query_selector("#shift-view")
        paper_view_div = page.query_selector("#paper-view")

        print(f"  Shift view div exists: {shift_view_div is not None}")
        print(f"  Paper view div exists: {paper_view_div is not None}")

        if shift_view_div:
            shift_visible = shift_view_div.is_visible()
            print(f"  Shift view visible: {shift_visible}")

        if paper_view_div:
            paper_visible = paper_view_div.is_visible()
            print(f"  Paper view visible: {paper_visible}")

            # Check paper view content
            print("\n  Inspecting paper view content...")
            paper_table = paper_view_div.query_selector(".paper-schedule-table")
            if paper_table:
                print("    ✓ Paper schedule table found")

                # Check for department headers
                dept_headers = paper_view_div.query_selector_all(".department-header")
                print(f"    Department headers found: {len(dept_headers)}")
                for i, header in enumerate(dept_headers):
                    print(f"      {i+1}. {header.inner_text()}")

                # Check for staff rows
                staff_rows = paper_view_div.query_selector_all(".staff-row")
                print(f"    Staff rows found: {len(staff_rows)}")

                if len(staff_rows) == 0:
                    print("\n    ⚠ No staff rows found in paper view!")
                    print("    This suggests no schedule data or paper_schedule_data is empty")
            else:
                print("    ✗ Paper schedule table NOT found")

        # Switch to paper view
        print("\n[6/6] Switching to paper view...")
        if paper_view_btn:
            paper_view_btn.click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # Check if URL changed
            current_url = page.url
            print(f"  Current URL: {current_url}")

            if "view=paper" in current_url:
                print("  ✓ URL contains view=paper parameter")
            else:
                print("  ✗ URL does NOT contain view=paper parameter")

            # Recheck visibility after switch
            paper_view_div = page.query_selector("#paper-view")
            if paper_view_div:
                paper_visible = paper_view_div.is_visible()
                print(f"  Paper view now visible: {paper_visible}")

                if paper_visible:
                    # Take screenshot
                    page.screenshot(path="paper_view_screenshot.png")
                    print("  Screenshot saved: paper_view_screenshot.png")

        # Check console errors
        print("\n[DEBUG] Checking for JavaScript errors...")
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))

        # Wait a bit to capture any console messages
        time.sleep(2)

        if console_messages:
            print("  Console messages:")
            for msg in console_messages:
                print(f"    {msg}")
        else:
            print("  No console errors")

        # Keep browser open for inspection
        print("\n" + "=" * 60)
        print("Browser will stay open for 10 seconds for inspection...")
        print("=" * 60)
        time.sleep(10)

        browser.close()

if __name__ == "__main__":
    test_schedule_paper_view()
