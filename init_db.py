"""
This script is for local development only. Do not run in production.
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
    cursor.execute("DROP TABLE IF EXISTS log_entries")
    cursor.execute("DROP TABLE IF EXISTS maintenance_items")
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

    # Maintenance items table
    cursor.execute("""
        CREATE TABLE maintenance_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT,
            priority TEXT CHECK(priority IN ('low','medium','high','urgent')) DEFAULT 'medium',
            status TEXT CHECK(status IN ('open','in_progress','blocked','completed')) DEFAULT 'open',
            completed_at TIMESTAMP
        )
    """)

    # Log book entries table
    cursor.execute("""
        CREATE TABLE log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            author_name TEXT NOT NULL,
            note TEXT NOT NULL,
            related_record_id INTEGER,
            related_maintenance_id INTEGER,
            is_system_event BOOLEAN DEFAULT 0,
            FOREIGN KEY (related_record_id) REFERENCES records(id),
            FOREIGN KEY (related_maintenance_id) REFERENCES maintenance_items(id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX idx_records_guest_name ON records(guest_name)")
    cursor.execute("CREATE INDEX idx_records_status ON records(status)")
    cursor.execute("CREATE INDEX idx_timeline_record ON timeline_entries(record_id)")
    cursor.execute("CREATE INDEX idx_photos_record ON photos(record_id)")
    cursor.execute("CREATE INDEX idx_log_entries_created_at ON log_entries(created_at)")
    cursor.execute("CREATE INDEX idx_log_entries_record ON log_entries(related_record_id)")
    cursor.execute("CREATE INDEX idx_log_entries_maintenance ON log_entries(related_maintenance_id)")
    cursor.execute("CREATE INDEX idx_maintenance_status ON maintenance_items(status)")

    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")

if __name__ == "__main__":
    init_db()
