"""
Migration script for Phase 2 (User Auth, Schedule, Wake-up Calls).
"""
import sqlite3
import os
import json
import bcrypt
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")
CREDENTIALS_FILE = os.path.join(BASE_DIR, ".credentials")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def migrate_v2():
    print(f"Migrating database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create Users Table
    print("Creating 'users' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('manager', 'front_desk', 'night_audit')),
            is_active INTEGER DEFAULT 1,
            force_password_change INTEGER DEFAULT 0,
            notification_preferences TEXT DEFAULT '{"wakeup_calls": true}',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            last_login TIMESTAMP
        )
    """)

    # 2. Migrate existing Manager credentials if available
    cursor.execute("SELECT count(*) FROM users WHERE role='manager'")
    manager_count = cursor.fetchone()[0]

    if manager_count == 0 and os.path.exists(CREDENTIALS_FILE):
        print("Migrating existing credentials from .credentials file...")
        try:
            with open(CREDENTIALS_FILE, 'r') as f:
                creds = json.load(f)
                
            username = creds.get('username', 'manager')
            pw_hash = creds.get('password_hash')
            manager_pw_hash = creds.get('manager_password_hash') # This was the 'admin' password in V1

            # In V1, 'password_hash' was general access, 'manager_password_hash' was admin.
            # In V2, we will create a 'manager' user with the manager password.
            
            if manager_pw_hash:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role, is_active, force_password_change)
                    VALUES (?, ?, 'manager', 1, 0)
                """, (username, manager_pw_hash))
                print(f"Created Manager user: {username}")
            else:
                print("WARNING: No manager password found in credentials. Please manually create a manager.")

        except Exception as e:
            print(f"Error migrating credentials: {e}")
    elif manager_count == 0:
        print("No .credentials file found. Creating default 'manager' account.")
        # Generate a secure random password
        import secrets
        import string

        # Generate password with at least 1 uppercase, 1 lowercase, 1 number
        alphabet = string.ascii_letters + string.digits
        while True:
            default_pw = ''.join(secrets.choice(alphabet) for i in range(16))
            if (any(c.islower() for c in default_pw)
                    and any(c.isupper() for c in default_pw)
                    and any(c.isdigit() for c in default_pw)):
                break

        default_hash = hash_password(default_pw)
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES ('manager', ?, 'manager', 1, 1)
        """, (default_hash,))
        print("=" * 60)
        print("IMPORTANT: Default manager account created")
        print(f"Username: manager")
        print(f"Password: {default_pw}")
        print("Please log in and change this password immediately!")
        print("=" * 60)


    # 3. Create Schedules Table
    print("Creating 'schedules' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            staff_name TEXT,
            shift_date TEXT NOT NULL,
            shift_id INTEGER NOT NULL CHECK(shift_id IN (1, 2, 3)),
            role TEXT, -- Optional override or display label
            note TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Unique constraint on staff name per shift to prevent accidental dupes (e.g. adding 'John' twice to Shift 1)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_schedules_unique_staff ON schedules(shift_date, shift_id, staff_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(shift_date)")

    # 4. Create Wake-up Calls Table
    print("Creating 'wakeup_calls' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wakeup_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            call_date TEXT NOT NULL, -- YYYY-MM-DD
            call_time TEXT NOT NULL, -- HH:MM (24h)
            frequency TEXT DEFAULT 'once', -- 'once' or 'daily' (scope says manual, but let's keep it simple) -> Actually scope says "Created on desktop". We will assume single instance for now unless "daily" requested.
            request_source TEXT, -- 'guest', 'front_desk', etc.
            status TEXT CHECK(status IN ('pending', 'completed', 'failed', 'cancelled')) DEFAULT 'pending',
            logged_by_user_id INTEGER,
            completed_by_user_id INTEGER,
            outcome_note TEXT,
            is_mobile_entry INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            FOREIGN KEY (logged_by_user_id) REFERENCES users(id),
            FOREIGN KEY (completed_by_user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wakeup_status ON wakeup_calls(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wakeup_date_time ON wakeup_calls(call_date, call_time)")

    # 5. Create Login Attempts Table
    print("Creating 'login_attempts' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            attempt_count INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            last_attempt TIMESTAMP DEFAULT (datetime('now','localtime')),
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    """)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_login_attempts_username ON login_attempts(username)")

    conn.commit()
    conn.close()
    print("Migration V2 (Auth/Schedule/Wakeups) completed successfully.")

if __name__ == "__main__":
    migrate_v2()
