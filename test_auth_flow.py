import sqlite3
import os
import bcrypt
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def test_auth():
    print("Testing Auth Logic...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1. Verify Manager Exists
    manager = conn.execute("SELECT * FROM users WHERE role = 'manager'").fetchone()
    if manager:
        print(f"[PASS] Manager account exists: {manager['username']}")
    else:
        print("[FAIL] Manager account missing!")
        return

    # 2. Simulate Create User (Manager Action)
    new_user = "test_user"
    new_pass = "temporary123"
    hashed = hash_password(new_pass)
    
    try:
        conn.execute("DELETE FROM users WHERE username = ?", (new_user,)) # Cleanup
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES (?, ?, 'front_desk', 1, 1)
        """, (new_user, hashed))
        conn.commit()
        print(f"[PASS] Created test user: {new_user}")
    except Exception as e:
        print(f"[FAIL] Creating user failed: {e}")

    # 3. Simulate Login Check
    user = conn.execute("SELECT * FROM users WHERE username = ?", (new_user,)).fetchone()
    if user and verify_password(new_pass, user['password_hash']):
        print(f"[PASS] Login credentials verified for {new_user}")
        if user['force_password_change']:
            print(f"[PASS] User is flagged to force password change")
        else:
            print(f"[FAIL] User should be flagged for password change but isn't")
    else:
        print(f"[FAIL] Login check failed")

    # 4. Simulate Password Change
    final_pass = "newpassword123"
    final_hash = hash_password(final_pass)
    conn.execute("UPDATE users SET password_hash = ?, force_password_change = 0 WHERE username = ?", (final_hash, new_user))
    
    updated_user = conn.execute("SELECT * FROM users WHERE username = ?", (new_user,)).fetchone()
    if verify_password(final_pass, updated_user['password_hash']) and not updated_user['force_password_change']:
        print(f"[PASS] Password change successful and force flag cleared")
    else:
        print(f"[FAIL] Password change verification failed")

    conn.close()

if __name__ == "__main__":
    test_auth()
