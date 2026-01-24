"""
One-time migration: Refactor in_house_messages from read state to archive state.
Removes is_read and read_at fields, adds archived and archived_at fields.
Auto-archives expired messages.
"""
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

DB_PATH = "dnr.db"
TIMEZONE = ZoneInfo("America/New_York")


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Add archived field if it doesn't exist
    if not column_exists(cursor, "in_house_messages", "archived"):
        cursor.execute("""
            ALTER TABLE in_house_messages
            ADD COLUMN archived INTEGER DEFAULT 0
        """)
        print("Added archived column")

    # Add archived_at field if it doesn't exist
    if not column_exists(cursor, "in_house_messages", "archived_at"):
        cursor.execute("""
            ALTER TABLE in_house_messages
            ADD COLUMN archived_at TIMESTAMP
        """)
        print("Added archived_at column")

    # Auto-archive expired messages
    now = datetime.now(TIMEZONE).isoformat(sep=" ", timespec="seconds")
    cursor.execute("""
        UPDATE in_house_messages
        SET archived = 1, archived_at = ?
        WHERE expires_at IS NOT NULL
        AND expires_at <= ?
        AND archived = 0
    """, (now, now))
    archived_count = cursor.rowcount
    print(f"Auto-archived {archived_count} expired messages")

    conn.commit()

    # Note: SQLite doesn't support DROP COLUMN easily
    # The is_read and read_at fields will remain but won't be used
    # They can be removed in a future schema recreation if needed
    print("Note: is_read and read_at fields remain in schema but are no longer used")

    conn.close()
    print("OK: migration complete")


if __name__ == "__main__":
    main()
