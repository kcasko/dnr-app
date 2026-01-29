import sys
import time
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\keith\.gemini\antigravity\brain\7d1f2254-9c0e-4efd-9951-2a10ef3e91ba"

def run_qa():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            print("1. Navigating to Login Page...")
            page.goto("http://127.0.0.1:5000/login", timeout=10000)
            print(f"   Page Title: {page.title()}")
            
            print("2. Logging in as Manager...")
            page.fill("input[name='username']", "manager_qa")
            page.fill("input[name='password']", "manager123")
            page.click("button[type='submit']")
            
            # Wait for navigation
            try:
                page.wait_for_url("**/overview", timeout=5000)
                print("   -> Login Successful (Redirected to Overview)")
            except Exception as e:
                print(f"   ERROR: Login timeout or mismatch. Current URL: {page.url}")
                page.screenshot(path=f"{ARTIFACT_DIR}\\login_fail.png")
                print(f"   Page Content: {page.content()[:1000]}...") # Print first 1000 chars
                raise e

            # Verify Dashboard Elements
            print("3. Verifying Dashboard...")
            page.screenshot(path=f"{ARTIFACT_DIR}\\dashboard.png")
            if not page.is_visible("text=Shift Dashboard"):
                print("ERROR: Dashboard 'Shift Dashboard' not found")
                sys.exit(1)
            
            # Verify Schedule
            print("4. Verifying Schedule Page...")
            page.click("a[href='/schedule']")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=f"{ARTIFACT_DIR}\\schedule.png")
            if not page.is_visible("text=Weekly Schedule"):
                 print("ERROR: Schedule page not loaded")
                 sys.exit(1)
            
            # Verify Department Headers (New Layout)
            if not page.is_visible("text=FRONT DESK") or not page.is_visible("text=HOUSEKEEPING"):
                 print("ERROR: Department headers (Front Desk/Housekeeping) not found in new layout")
                 sys.exit(1)
            
            print("   -> Schedule Page Verified (Departments Visible)")
                 
            # Verify Wake-up Calls
            print("5. Verifying Wake-up Calls...")
            page.click("a[href='/wakeup-calls']")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=f"{ARTIFACT_DIR}\\wakeup.png")
            if not page.is_visible("text=Pending Calls"):
                 print("ERROR: Wake-up Call page not loaded")
                 sys.exit(1)
            
            # Verify Settings (Manager Only)
            print("6. Verifying Settings...")
            page.click("a[href='/settings']")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=f"{ARTIFACT_DIR}\\settings.png")
            if not page.is_visible("text=User Management"):
                 print("ERROR: 'User Management' tab not found for Manager")
                 sys.exit(1)

            print("7. Verifying Mobile View...")
            page.goto("http://127.0.0.1:5000/mobile")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=f"{ARTIFACT_DIR}\\mobile.png")
            if not page.is_visible("text=Mobile Dashboard"):
                 print("ERROR: Mobile dashboard not loaded")
                 sys.exit(1)
            
            print("SUCCESS: All sanity checks passed!")
            
        except Exception as e:
            print(f"FATAL ERROR: {e}")
            page.screenshot(path=f"{ARTIFACT_DIR}\\fatal_error.png")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run_qa()
