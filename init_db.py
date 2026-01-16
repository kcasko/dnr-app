"""
Database initialization script for Restricted Guests Log (DNR System)
Run this once to create/reset the database schema.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing tables if they exist (for clean reset)
    cursor.execute("DROP TABLE IF EXISTS photos")
    cursor.execute("DROP TABLE IF EXISTS timeline_entries")
    cursor.execute("DROP TABLE IF EXISTS password_attempts")
    cursor.execute("DROP TABLE IF EXISTS records")
    cursor.execute("DROP TABLE IF EXISTS incidents")

    # Main records table
    cursor.execute("""
        CREATE TABLE records (
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
    # status: 'active', 'expired', 'lifted'
    # ban_type: 'temporary', 'permanent'
    # expiration_type: 'date', 'resolved', 'manager_review' (only for temporary)

    # Timeline entries table
    cursor.execute("""
        CREATE TABLE timeline_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            staff_initials TEXT,
            note TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
    """)

    # Photos table
    cursor.execute("""
        CREATE TABLE photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT,
            upload_date TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
    """)

    # Failed password attempts log (silent logging)
    cursor.execute("""
        CREATE TABLE password_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER,
            attempt_date TEXT NOT NULL,
            ip_address TEXT
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX idx_records_guest_name ON records(guest_name)")
    cursor.execute("CREATE INDEX idx_records_status ON records(status)")
    cursor.execute("CREATE INDEX idx_timeline_record ON timeline_entries(record_id)")
    cursor.execute("CREATE INDEX idx_photos_record ON photos(record_id)")

    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")

if __name__ == "__main__":
    init_db()
