"""
Migration script to add login_attempts table for existing V2 databases.
Run this if you already ran migrate_v2_auth_schedule.py but it didn't create the login_attempts table.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def migrate():
    print(f"Adding login_attempts table to: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'")
    if cursor.fetchone():
        print("login_attempts table already exists. No action needed.")
        conn.close()
        return

    # Create Login Attempts Table
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
    print("Migration completed: login_attempts table created successfully.")

if __name__ == "__main__":
    migrate()
