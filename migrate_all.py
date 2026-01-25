"""
DNR App – Unified Migration Script (Corrected)
Safe to run multiple times.
"""

import sqlite3
from datetime import datetime, timezone

DB_PATH = "/home/sleepinn/dnr-app/dnr.db"


def table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return column in [row[1] for row in cursor.fetchall()]


def migrate_housekeeping_requests_schema(cursor):
    """Fix housekeeping_requests table - old schema had restrictive CHECK constraint."""
    print("→ Checking housekeeping_requests schema")

    if not table_exists(cursor, "housekeeping_requests"):
        print("⚠ housekeeping_requests table missing, skipping")
        return

    # Check if table has the old restrictive constraint by trying to read table SQL
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='housekeeping_requests'")
    row = cursor.fetchone()
    if row and "CHECK(frequency = 'every_other_day')" in (row[0] or ""):
        print("⚠ Found old restrictive CHECK constraint, recreating table...")

        # Create new table with correct schema
        cursor.execute("""
            CREATE TABLE housekeeping_requests_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT NOT NULL,
                guest_name TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                frequency TEXT NOT NULL DEFAULT 'every_3rd_day' CHECK(frequency IN ('none', 'every_3rd_day', 'daily', 'custom')),
                frequency_days INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                updated_at TIMESTAMP,
                archived_at TIMESTAMP
            )
        """)

        # Copy data, mapping old frequency value to new
        cursor.execute("""
            INSERT INTO housekeeping_requests_new (id, room_number, start_date, end_date, frequency, notes, created_at, updated_at, archived_at)
            SELECT id, room_number, start_date, end_date, 'every_3rd_day', notes, created_at, updated_at, archived_at
            FROM housekeeping_requests
        """)

        # Drop old table and rename new
        cursor.execute("DROP TABLE housekeeping_requests")
        cursor.execute("ALTER TABLE housekeeping_requests_new RENAME TO housekeeping_requests")

        # Recreate indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_requests_room ON housekeeping_requests(room_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_requests_archived ON housekeeping_requests(archived_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_requests_dates ON housekeeping_requests(start_date, end_date)")

        print("✓ migrated to new schema with correct CHECK constraint")
    else:
        # Just add missing columns if needed
        if not column_exists(cursor, "housekeeping_requests", "guest_name"):
            cursor.execute("ALTER TABLE housekeeping_requests ADD COLUMN guest_name TEXT")
            print("✓ added guest_name column")

        if not column_exists(cursor, "housekeeping_requests", "frequency_days"):
            cursor.execute("ALTER TABLE housekeeping_requests ADD COLUMN frequency_days INTEGER")
            print("✓ added frequency_days column")

    print("✓ housekeeping_requests schema ensured")


def migrate_housekeeping(cursor):
    print("→ Checking housekeeping_service_dates")

    # Check if table exists with wrong column name and fix it
    if table_exists(cursor, "housekeeping_service_dates"):
        if column_exists(cursor, "housekeeping_service_dates", "request_id") and not column_exists(cursor, "housekeeping_service_dates", "housekeeping_request_id"):
            print("⚠ Found old column name 'request_id', recreating table with correct schema...")
            cursor.execute("ALTER TABLE housekeeping_service_dates RENAME TO housekeeping_service_dates_old")
            cursor.execute("""
                CREATE TABLE housekeeping_service_dates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    housekeeping_request_id INTEGER NOT NULL,
                    service_date TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (housekeeping_request_id)
                        REFERENCES housekeeping_requests(id)
                        ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                INSERT INTO housekeeping_service_dates (id, housekeeping_request_id, service_date, is_active)
                SELECT id, request_id, service_date, is_active FROM housekeeping_service_dates_old
            """)
            cursor.execute("DROP TABLE housekeeping_service_dates_old")
            print("✓ migrated data to new schema")
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS housekeeping_service_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                housekeeping_request_id INTEGER NOT NULL,
                service_date TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (housekeeping_request_id)
                    REFERENCES housekeeping_requests(id)
                    ON DELETE CASCADE
            )
        """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_service_dates_request ON housekeeping_service_dates(housekeeping_request_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_service_dates_date ON housekeeping_service_dates(service_date, is_active)")

    print("✓ housekeeping_service_dates ensured")


def migrate_in_house_messages(cursor):
    print("→ Checking in_house_messages")

    if not table_exists(cursor, "in_house_messages"):
        print("⚠ in_house_messages table missing, skipping")
        return

    if not column_exists(cursor, "in_house_messages", "archived"):
        cursor.execute("""
            ALTER TABLE in_house_messages
            ADD COLUMN archived INTEGER DEFAULT 0
        """)
        print("✓ added archived")

    if not column_exists(cursor, "in_house_messages", "archived_at"):
        cursor.execute("""
            ALTER TABLE in_house_messages
            ADD COLUMN archived_at TEXT
        """)
        print("✓ added archived_at")

    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")

    cursor.execute("""
        UPDATE in_house_messages
        SET archived = 1,
            archived_at = ?
        WHERE expires_at IS NOT NULL
          AND expires_at <= ?
          AND archived = 0
    """, (now, now))

    print(f"✓ auto-archived {cursor.rowcount} expired messages")


def migrate_log_entries_shift_id(cursor):
    print("→ Checking log_entries.shift_id")

    if not table_exists(cursor, "log_entries"):
        print("⚠ log_entries table missing, skipping")
        return

    if not column_exists(cursor, "log_entries", "shift_id"):
        cursor.execute("""
            ALTER TABLE log_entries
            ADD COLUMN shift_id INTEGER CHECK(shift_id IN (1, 2, 3))
        """)
        print("✓ added shift_id column")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_shift ON log_entries(shift_id)")
    print("✓ log_entries.shift_id ensured")


def migrate_schema_version(cursor):
    print("→ Ensuring schema_version table")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM schema_version")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
            INSERT INTO schema_version (version, applied_at)
            VALUES (?, ?)
        """, (1, datetime.now(timezone.utc).isoformat()))
        print("✓ schema version initialized to 1")
    else:
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        version = cursor.fetchone()[0]
        print(f"✓ schema version already present ({version})")


def main():
    print("=== DNR MIGRATION START ===")

    conn = sqlite3.connect(DB_PATH)
    # Disable foreign keys during migration to allow table recreation
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    migrate_housekeeping_requests_schema(cursor)
    migrate_housekeeping(cursor)
    migrate_in_house_messages(cursor)
    migrate_log_entries_shift_id(cursor)
    migrate_schema_version(cursor)

    conn.commit()

    # Re-enable foreign keys and verify integrity
    conn.execute("PRAGMA foreign_keys = ON")
    result = conn.execute("PRAGMA foreign_key_check").fetchall()
    if result:
        print(f"⚠ Foreign key violations found: {result}")
    else:
        print("✓ Foreign key integrity verified")

    conn.close()

    print("=== MIGRATION COMPLETE ===")


if __name__ == "__main__":
    main()
