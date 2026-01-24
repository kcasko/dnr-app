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

    # Create tables (basic schema for testing)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS housekeeping_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            guest_name TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'none',
            frequency_days INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS housekeeping_service_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            service_date TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (request_id) REFERENCES housekeeping_requests(id) ON DELETE CASCADE
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

    # Start Flask server on a test port
    proc = subprocess.Popen(
        ['.venv/Scripts/python.exe', 'app.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )

    # Wait for server to start
    time.sleep(3)

    yield "http://localhost:5000"

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
    cursor.execute("DELETE FROM housekeeping_requests")
    conn.commit()
    conn.close()
    yield
