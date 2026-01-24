"""
One-time migration: Add explicit service dates table and update housekeeping schema.
This migration implements the requirement that all housekeeping modes resolve to
explicit service dates (no calculated-on-the-fly behavior).
"""
import sqlite3
from datetime import date, timedelta

DB_PATH = "dnr.db"


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Create the service dates table
    if not table_exists(cursor, "housekeeping_service_dates"):
        cursor.execute("""
            CREATE TABLE housekeeping_service_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                housekeeping_request_id INTEGER NOT NULL,
                service_date TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (housekeeping_request_id) REFERENCES housekeeping_requests(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX idx_housekeeping_service_dates_request
            ON housekeeping_service_dates(housekeeping_request_id)
        """)
        cursor.execute("""
            CREATE INDEX idx_housekeeping_service_dates_date
            ON housekeeping_service_dates(service_date, is_active)
        """)
        print("Created housekeeping_service_dates table")

    # Add guest_name column if it doesn't exist
    if not column_exists(cursor, "housekeeping_requests", "guest_name"):
        cursor.execute("""
            ALTER TABLE housekeeping_requests
            ADD COLUMN guest_name TEXT
        """)
        print("Added guest_name column")

    # Update existing records to use new frequency values
    # Map old values to new ones:
    # 'no_housekeeping' -> 'none'
    # 'every_3rd_day' -> 'every_3rd_day' (stays same)
    # 'daily' -> 'daily' (stays same)
    # 'custom: ...' -> 'custom'

    cursor.execute("""
        UPDATE housekeeping_requests
        SET frequency = 'none'
        WHERE frequency = 'no_housekeeping'
    """)

    cursor.execute("""
        UPDATE housekeeping_requests
        SET frequency = 'custom'
        WHERE frequency LIKE 'custom:%'
    """)

    print("Updated existing frequency values")

    # Migrate existing requests to have explicit service dates
    # This generates service dates for all existing active requests
    cursor.execute("""
        SELECT id, start_date, end_date, frequency, frequency_days
        FROM housekeeping_requests
        WHERE archived_at IS NULL
    """)
    existing_requests = cursor.fetchall()

    for request in existing_requests:
        request_id, start_date_str, end_date_str, frequency, frequency_days = request

        # Skip if frequency is 'none' (no housekeeping)
        if frequency == 'none':
            continue

        # Parse dates
        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
        except (ValueError, AttributeError):
            print(f"Skipping request {request_id} - invalid dates")
            continue

        # Generate service dates based on frequency
        service_dates = []

        if frequency == 'daily':
            # Every day from start_date to end_date (excluding checkout)
            current = start_date
            while current < end_date:  # Exclude checkout day
                service_dates.append(current.isoformat())
                current += timedelta(days=1)

        elif frequency == 'every_3rd_day':
            # Every 3rd day starting from start_date
            current = start_date
            while current < end_date:  # Exclude checkout day
                service_dates.append(current.isoformat())
                current += timedelta(days=3)

        elif frequency == 'custom' and frequency_days:
            # Custom interval
            current = start_date
            while current < end_date:  # Exclude checkout day
                service_dates.append(current.isoformat())
                current += timedelta(days=frequency_days)

        # Insert service dates
        for service_date in service_dates:
            cursor.execute("""
                INSERT INTO housekeeping_service_dates
                (housekeeping_request_id, service_date, is_active)
                VALUES (?, ?, 1)
            """, (request_id, service_date))

        if service_dates:
            print(f"Generated {len(service_dates)} service dates for request {request_id}")

    conn.commit()
    conn.close()
    print("OK: migration complete")


if __name__ == "__main__":
    main()
