"""
Pytest configuration and fixtures for DNR App testing.
"""
import os
import sqlite3
import tempfile
import shutil
import pytest
from playwright.sync_api import Page
import subprocess
import time
import json
import socket


# Test configuration
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass123"
TEST_MANAGER_PASSWORD = "managerpass123"


@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary test database."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_dnr.db")

    # Initialize test database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables (schema subset used by the app)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guest_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            ban_type TEXT NOT NULL,
            reasons TEXT NOT NULL,
            reason_detail TEXT,
            date_added TEXT NOT NULL,
            incident_date TEXT,
            expiration_type TEXT,
            expiration_date TEXT,
            lifted_date TEXT,
            lifted_type TEXT,
            lifted_reason TEXT,
            lifted_initials TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            location TEXT,
            details TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            author_name TEXT NOT NULL,
            note TEXT NOT NULL,
            shift_id INTEGER CHECK(shift_id IN (1, 2, 3)),
            related_record_id INTEGER,
            related_maintenance_id INTEGER,
            is_system_event BOOLEAN DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            status TEXT CHECK(status IN ('out_of_order','use_if_needed')) NOT NULL,
            note TEXT,
            state TEXT CHECK(state IN ('active','resolved')) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            starts_at TIMESTAMP,
            ends_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS important_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            phone TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS in_house_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_name TEXT NOT NULL,
            message_body TEXT NOT NULL,
            author_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            expires_at TIMESTAMP,
            archived INTEGER DEFAULT 0,
            archived_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS housekeeping_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            guest_name TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'none' CHECK(frequency IN ('none', 'every_3rd_day', 'daily', 'custom')),
            frequency_days INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            archived_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS housekeeping_service_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            housekeeping_request_id INTEGER NOT NULL,
            service_date TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS housekeeping_request_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            housekeeping_request_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            note TEXT NOT NULL,
            is_system_event INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="session")
def test_credentials_file():
    """Create a temporary credentials file for testing."""
    temp_dir = tempfile.mkdtemp()
    creds_path = os.path.join(temp_dir, ".credentials")

    # Create test credentials (using bcrypt hashing)
    import bcrypt
    password_hash = bcrypt.hashpw(TEST_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    manager_hash = bcrypt.hashpw(TEST_MANAGER_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    creds = {
        'username': TEST_USERNAME,
        'password_hash': password_hash,
        'manager_password_hash': manager_hash,
        'session_version': 1
    }

    with open(creds_path, 'w') as f:
        json.dump(creds, f)

    yield creds_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="session")
def flask_app(test_db_path, test_credentials_file):
    """Start the Flask application for testing."""
    env = os.environ.copy()
    env['DB_PATH'] = test_db_path
    env['CREDENTIALS_FILE'] = test_credentials_file
    env['SECRET_KEY'] = 'test-secret-key-not-for-production'
    env['FLASK_ENV'] = 'testing'
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env['PORT'] = str(port)

    # Start Flask server on a test port
    proc = subprocess.Popen(
        ['.venv/Scripts/python.exe', 'app.py'],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )

    # Wait for server to start
    base_url = f"http://localhost:{port}"
    deadline = time.time() + 15
    started = False
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                started = True
                break
        except OSError:
            time.sleep(0.2)

    if not started:
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError("Flask test server did not start in time")

    yield base_url

    # Cleanup
    proc.terminate()
    proc.wait(timeout=5)


# Note: browser, context, and page fixtures are provided by pytest-playwright plugin
# We can customize them if needed, but for basic tests they work out of the box


@pytest.fixture(scope="function")
def authenticated_page(page: Page, flask_app):
    """Login and return an authenticated page."""
    # Navigate to login page
    page.goto(f"{flask_app}/login")

    # Fill in login form
    page.fill('input[name="username"]', TEST_USERNAME)
    page.fill('input[name="password"]', TEST_PASSWORD)

    # Submit form
    page.click('button[type="submit"]')

    # Wait for redirect to overview/dashboard
    page.wait_for_url(f"{flask_app}/overview", timeout=5000)

    yield page


@pytest.fixture(scope="function")
def clean_db(test_db_path):
    """Clean the database before each test."""
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM housekeeping_service_dates")
    cursor.execute("DELETE FROM housekeeping_request_events")
    cursor.execute("DELETE FROM housekeeping_requests")
    conn.commit()
    conn.close()
    yield
