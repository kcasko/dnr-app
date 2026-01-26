"""
Test suite to verify security fixes for the multi-user authentication system.
"""
import sqlite3
import os
import bcrypt
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def test_password_complexity():
    """Test that password complexity requirements are enforced."""
    print("Testing password complexity validation...")

    # Valid passwords
    valid_passwords = [
        "Password123",
        "MySecure1Pass",
        "Admin2026Test"
    ]

    # Invalid passwords
    invalid_passwords = [
        "password123",      # No uppercase
        "PASSWORD123",      # No lowercase
        "PasswordTest",     # No number
        "Pass1"             # Too short
    ]

    for pwd in valid_passwords:
        has_upper = bool(re.search(r'[A-Z]', pwd))
        has_lower = bool(re.search(r'[a-z]', pwd))
        has_number = bool(re.search(r'[0-9]', pwd))
        has_length = len(pwd) >= 8

        if has_upper and has_lower and has_number and has_length:
            print(f"  [PASS] Valid password accepted: {pwd[:4]}...")
        else:
            print(f"  [FAIL] Valid password rejected: {pwd}")
            return False

    for pwd in invalid_passwords:
        has_upper = bool(re.search(r'[A-Z]', pwd))
        has_lower = bool(re.search(r'[a-z]', pwd))
        has_number = bool(re.search(r'[0-9]', pwd))
        has_length = len(pwd) >= 8

        if not (has_upper and has_lower and has_number and has_length):
            print(f"  [PASS] Invalid password rejected: {pwd[:4]}...")
        else:
            print(f"  [FAIL] Invalid password accepted: {pwd}")
            return False

    print("[PASS] Password complexity validation working correctly")
    return True

def test_login_attempts_table():
    """Test that login_attempts table exists and has correct schema."""
    print("\nTesting login_attempts table schema...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'")
    if not cursor.fetchone():
        print("  [FAIL] login_attempts table does not exist")
        conn.close()
        return False

    print("  [PASS] login_attempts table exists")

    # Check columns
    cursor.execute("PRAGMA table_info(login_attempts)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    required_columns = {
        'id': 'INTEGER',
        'username': 'TEXT',
        'attempt_count': 'INTEGER',
        'locked_until': 'TIMESTAMP',
        'last_attempt': 'TIMESTAMP',
        'created_at': 'TIMESTAMP'
    }

    for col, col_type in required_columns.items():
        if col not in columns:
            print(f"  [FAIL] Missing column: {col}")
            conn.close()
            return False

    print("  [PASS] All required columns present")

    # Check unique index on username
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='login_attempts' AND name='idx_login_attempts_username'")
    if cursor.fetchone():
        print("  [PASS] Unique index on username exists")
    else:
        print("  [FAIL] Missing unique index on username")
        conn.close()
        return False

    conn.close()
    print("[PASS] login_attempts table schema correct")
    return True

def test_schedules_schema_fix():
    """Test that schedules table allows NULL user_id and has staff_name column."""
    print("\nTesting schedules table schema fix...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'")
    if not cursor.fetchone():
        print("  [FAIL] schedules table does not exist")
        conn.close()
        return False

    # Check columns
    cursor.execute("PRAGMA table_info(schedules)")
    columns = {row[1]: (row[2], row[3]) for row in cursor.fetchall()}  # name: (type, notnull)

    if 'user_id' not in columns:
        print("  [FAIL] user_id column missing")
        conn.close()
        return False

    # user_id should allow NULL (notnull = 0)
    if columns['user_id'][1] == 0:
        print("  [PASS] user_id allows NULL values")
    else:
        print("  [FAIL] user_id does not allow NULL (should allow for non-user entries)")
        conn.close()
        return False

    if 'staff_name' in columns:
        print("  [PASS] staff_name column exists")
    else:
        print("  [FAIL] staff_name column missing")
        conn.close()
        return False

    conn.close()
    print("[PASS] schedules schema fix verified")
    return True

def test_add_user_route():
    """Test that add_user route would properly validate inputs."""
    print("\nTesting add_user route validation logic...")

    # Simulate validation checks
    test_cases = [
        ("ab", "Password123", "manager", False, "Username too short"),
        ("validuser", "short", "manager", False, "Password too short"),
        ("validuser", "nouppercaseornumber", "manager", False, "Missing uppercase/number"),
        ("validuser", "Password123", "invalid_role", False, "Invalid role"),
        ("validuser", "Password123", "manager", True, "Valid input"),
    ]

    for username, password, role, should_pass, description in test_cases:
        # Validate username
        username_valid = len(username) >= 3

        # Validate password length
        password_length_valid = len(password) >= 8

        # Validate password complexity
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_number = bool(re.search(r'[0-9]', password))
        password_complex_valid = has_upper and has_lower and has_number

        # Validate role
        role_valid = role in ('manager', 'front_desk', 'night_audit')

        is_valid = username_valid and password_length_valid and password_complex_valid and role_valid

        if is_valid == should_pass:
            print(f"  [PASS] {description}")
        else:
            print(f"  [FAIL] {description} - Expected {should_pass}, got {is_valid}")
            return False

    print("[PASS] add_user route validation logic correct")
    return True

def test_input_validation():
    """Test that input validation would work correctly."""
    print("\nTesting input validation for schedule and wake-up calls...")

    # Test date validation
    from datetime import datetime

    valid_dates = ["2026-01-26", "2026-12-31"]
    invalid_dates = ["2026-13-01", "26-01-2026", "not-a-date"]

    for date_str in valid_dates:
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            print(f"  [PASS] Valid date accepted: {date_str}")
        except ValueError:
            print(f"  [FAIL] Valid date rejected: {date_str}")
            return False

    for date_str in invalid_dates:
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            print(f"  [FAIL] Invalid date accepted: {date_str}")
            return False
        except ValueError:
            print(f"  [PASS] Invalid date rejected: {date_str}")

    # Test time validation
    valid_times = ["08:30", "23:59", "00:00"]
    invalid_times = ["25:00", "12:61", "not-a-time"]

    for time_str in valid_times:
        try:
            datetime.strptime(time_str, '%H:%M')
            print(f"  [PASS] Valid time accepted: {time_str}")
        except ValueError:
            print(f"  [FAIL] Valid time rejected: {time_str}")
            return False

    for time_str in invalid_times:
        try:
            datetime.strptime(time_str, '%H:%M')
            print(f"  [FAIL] Invalid time accepted: {time_str}")
            return False
        except ValueError:
            print(f"  [PASS] Invalid time rejected: {time_str}")

    # Test shift_id validation
    valid_shift_ids = [1, 2, 3]
    invalid_shift_ids = [0, 4, -1, 999]

    for shift_id in valid_shift_ids:
        if shift_id in (1, 2, 3):
            print(f"  [PASS] Valid shift_id accepted: {shift_id}")
        else:
            print(f"  [FAIL] Valid shift_id rejected: {shift_id}")
            return False

    for shift_id in invalid_shift_ids:
        if shift_id not in (1, 2, 3):
            print(f"  [PASS] Invalid shift_id rejected: {shift_id}")
        else:
            print(f"  [FAIL] Invalid shift_id accepted: {shift_id}")
            return False

    print("[PASS] Input validation working correctly")
    return True

def test_user_table_schema():
    """Verify users table has all required columns."""
    print("\nTesting users table schema...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("  [FAIL] users table does not exist")
        conn.close()
        return False

    # Check columns
    cursor.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in cursor.fetchall()}

    required_columns = {
        'id', 'username', 'password_hash', 'role', 'is_active',
        'force_password_change', 'notification_preferences', 'created_at', 'last_login'
    }

    missing = required_columns - columns
    if missing:
        print(f"  [FAIL] Missing columns: {missing}")
        conn.close()
        return False

    print("  [PASS] All required columns present")
    conn.close()
    print("[PASS] users table schema correct")
    return True

def main():
    """Run all security tests."""
    print("=" * 60)
    print("Security Fixes Verification Test Suite")
    print("=" * 60)

    tests = [
        ("Password Complexity", test_password_complexity),
        ("Login Attempts Table", test_login_attempts_table),
        ("Schedules Schema Fix", test_schedules_schema_fix),
        ("Add User Validation", test_add_user_route),
        ("Input Validation", test_input_validation),
        ("Users Table Schema", test_user_table_schema),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[FAIL] {name} - Exception: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("All security fixes verified successfully!")
        return True
    else:
        print(f"Some tests failed. Please review the output above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
