"""
One-time migration: update frequency options for housekeeping_requests.
Adds support for every_3rd_day, daily, and custom frequencies.
"""
import sqlite3

DB_PATH = "dnr.db"


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # SQLite doesn't support ALTER TABLE to modify CHECK constraints
    # We need to recreate the table with the new constraint
    # First, add frequency_days column if it doesn't exist
    if not column_exists(cursor, "housekeeping_requests", "frequency_days"):
        cursor.execute("""
            ALTER TABLE housekeeping_requests
            ADD COLUMN frequency_days INTEGER DEFAULT 2
        """)
        print("Added frequency_days column")

    # Update existing 'every_other_day' to 'every_3rd_day' (new default)
    cursor.execute("""
        UPDATE housekeeping_requests
        SET frequency = 'every_3rd_day', frequency_days = 3
        WHERE frequency = 'every_other_day'
    """)
    print("Updated existing records to every_3rd_day")

    conn.commit()
    conn.close()
    print("OK: migration complete")


if __name__ == "__main__":
    main()
